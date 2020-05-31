#! /bin/bash

# Wrapper process around various temperature controller scripts to enable convenient control of controller and logs

# SYNTAX: ./temperature_controller.sh <function> [<function argument>]

# EXAMPLE CALLS
# ./temperature_controller.sh get
# ./temperature_controller.sh set 25
# ./temperature_controller.sh control continuous

# INPUTS
# Configuration file must be present at either /etc/controller.conf or config/controller.conf (former takes precedence)
# <function> must be specified:
#       'set' to set temperature setpoint (in file)
#       'get' to get current temperature(s) (to STDOUT)
#       'control' to run temperature controller
#       'analyse' to analyse logfile (and push data to AWS S3 if configured)
#       'sync' Push data to AWS S3 if configured
# <function argument> is optional:
#       (in 'set' mode) - a setpoint temperature in (C) to write to setpoint file (float) - if omitted read current setpoint
#       (in 'control' mode) - string 'continuous' to run controller in continuous mode, otherwise run-once and exit

# OUTPUTS
# (See individual scripts called for full details of outputs)

# Changelog
# 05/2020 - First Version

# Copyright (C) 2020 Aaron Lockton

# Source config - /etc always takes precedence
if [[ -s /etc/controller.conf ]]; then
  source "/etc/controller.conf"
elif [[ -s config/controller.conf ]]; then
  # Try relative path if being run straight from repo -only works if running from repo root
  source "config/controller.conf"
else
  echo "ERROR: Configuration file cannot be found at /etc/controller.conf or config/controller.conf"
  exit 1
fi

function switch_off_and_exit {
  echo "Temperature controller terminated - checking demand is off and exiting wrapper process"
  if [[ -f /sys/class/gpio/gpio${GPIO_OUTPUT}/value ]] && [[ $(cat /sys/class/gpio/gpio${GPIO_OUTPUT}/value) = "1" ]]; then
    if [[ -s ${CONTROLLER_LOGFILE} ]]; then
      # If logfile exists and already has content, ensure switch-off is not missed - note this will not be logged by controller as it was terminated
      echo "$(date +"%F-%T"): Temperature controller stopping or restarting - Switching system off" >> ${CONTROLLER_LOGFILE}
    fi
    echo 0 > /sys/class/gpio/gpio${GPIO_OUTPUT}/value
  fi
  exit 1
}

function sync_to_s3 {
  # If enabled in config, sync outputs to S3
  if [[ ${ENABLE_S3_SYNC,,} = "1" ]] || [[ ${ENABLE_S3_SYNC,,} = "enabled" ]] || [[ ${ENABLE_S3_SYNC,,} = "yes" ]]; then
    # sync to s3, if error is aws cli installed, is path correct, check permissions IAM, etc
    ERROR_COUNTER=0
    aws s3 sync --exclude "*" --include $(basename ${DATA_LOGFILE}) --include $(basename ${CONTROLLER_LOGFILE}) $(dirname ${CONTROLLER_LOGFILE}) ${S3_DESTINATION_PATH}
    if [[ $? -ne 0 ]];then
      ((ERROR_COUNTER+=1))
    fi
    aws s3 sync ${ANALYSIS_OUTDIR} ${S3_DESTINATION_PATH}
    if [[ $? -ne 0 ]];then
      ((ERROR_COUNTER+=1))
    fi
    if [[ ${ERROR_COUNTER} -ne 0 ]]; then
      echo "EROR: AWS S3 sync did not complete successfully - check AWS CLI is installed, configured path to destination bucket (${S3_DESTINATION_PATH}) is correct and there are rw permissions for controller on this location in AWS IAM"
    fi
  fi
}

# Operating mode
if [[ "${1,,}" = "set" ]]; then
  # Set mode - run settemp
  "${SCRIPTDIR}"/settemp ${2}
elif [[ "${1,,}" = "get" ]]; then
  # Get mode - run temprt
  "${SCRIPTDIR}"/temprt
elif [[ "${1,,}" = "control" ]]; then
  # Control mode - run control_temp.py
  ARG_STRING=
  ARG_STRING+="${WORKING_DIR}/setpoint"
  if [[ ! -z ${HYTERESIS} ]]; then
    ARG_STRING+=" -t ${HYTERESIS}"
  fi
  if [[ ${COOLERMODE,,} = "1" ]] || [[ ${COOLERMODE,,} = "enabled" ]] || [[ ${COOLERMODE,,} = "yes" ]]; then
    ARG_STRING+=" -c"
  fi
  if [[ ${VERBOSE,,} = "1" ]] || [[ ${VERBOSE,,} = "enabled" ]] || [[ ${VERBOSE,,} = "yes" ]]; then
    ARG_STRING+=" -v"
  fi
  if [[ ! -z ${WIRED_SENSORS} ]]; then
    ARG_STRING+=" -s ${WIRED_SENSORS[@]}"
  fi
  if [[ ! -z ${WIRED_SENSOR_LABELS} ]]; then
    ARG_STRING+=" -n ${WIRED_SENSOR_LABELS[@]}"
  fi
  if [[ ! -z ${GPIO_OUTPUT} ]]; then
    ARG_STRING+=" -g ${GPIO_OUTPUT}"
  fi
  if [[ ! -z ${GPIO_FEEDBACK} ]]; then
    ARG_STRING+=" -f ${GPIO_FEEDBACK}"
  fi
  if [[ ! -z ${DATA_LOGFILE} ]]; then
    ARG_STRING+=" -l ${DATA_LOGFILE}"
  fi
  if [[ ${LEGACYLOG,,} = "1" ]] || [[ ${LEGACYLOG,,} = "enabled" ]] || [[ ${LEGACYLOG,,} = "yes" ]]; then
    ARG_STRING+=" -y"
  fi
  if [[ ! -z ${CONTROLLER_LOGFILE} ]]; then
    ARG_STRING+=" -m ${CONTROLLER_LOGFILE}"
  fi
  if [[ ${2,,} = "continuous" ]] && [[ ! -z ${INTERVAL} ]]; then
    ARG_STRING+=" -i ${INTERVAL}"
    # In continuous mode, need to catch CTRL-C and switch off GPIO
    echo "Starting temperature controller in continuous mode - CTRL-C to exit"
    trap "switch_off_and_exit" SIGHUP SIGINT SIGTERM
  fi
  # Call controller with configured options
  "${SCRIPTDIR}/control_temp.py" ${ARG_STRING}
elif [[ "${1,,}" = "analyse" ]]; then
  # Control mode - run control_temp.py
  if [[ ! -d ${ANALYSIS_OUTDIR} ]]; then
    echo "ERROR: Specified output directory for log analysis ${ANALYSIS_OUTDIR} does not exist"
    exit 1
  fi
  ARG_STRING="${CONTROLLER_LOGFILE} $(date +%s -d ${START_DATE}) $(date +%s -d ${END_DATE}) ${ANALYSIS_OUTDIR}"
  # Call controller analysis script with configured options
  "${SCRIPTDIR}/controller_analyse.py" ${ARG_STRING}
  # Push data to AWS -if configured
  sync_to_s3
elif [[ "${1,,}" = "sync" ]]; then
  sync_to_s3
else
  echo "ERROR: Unrecognised/missing function ${1} - valid arguments are 'set', 'get', 'control', 'analyse', 'sync'"
  exit 1
fi
