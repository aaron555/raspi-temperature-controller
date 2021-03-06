#! /bin/bash

# Wrapper process around various Raspberry Pi temperature controller scripts to enable convenient control of controller and logs

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

# CHANGELOG
# 06/2020 - First Version

# Copyright (C) 2020 Aaron Lockton

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# Allow all group users to write to files created by this script
umask 002

# Source config, ENV always takes precedence
if [[ -s ${CONFIG_FILE} ]]; then
  source ${CONFIG_FILE}
elif [[ -s /etc/controller.conf ]]; then
  # IF no config in ENV, /etc/ takes precedence
  source "/etc/controller.conf"
elif [[ -s config/controller.conf ]]; then
  # Try relative path if being run straight from repo -only works if running from repo root
  source "config/controller.conf"
else
  echo "ERROR: Configuration file cannot be found at /etc/controller.conf or config/controller.conf"
  exit 1
fi

function switch_off_and_exit {
  echo "Temperature controller terminated/failed - checking demand is off and exiting wrapper process"
  if [[ -f /sys/class/gpio/gpio${GPIO_OUTPUT}/value ]] && [[ $(cat /sys/class/gpio/gpio${GPIO_OUTPUT}/value) = "1" ]]; then
    if [[ -s ${CONTROLLER_LOGFILE} ]]; then
      # If logfile exists and already has content, ensure switch-off is not missed - note this will not be logged by controller as it was terminated
      echo "$(date -u +"%F-%T"): Temperature controller exiting - Switching system off" >> ${CONTROLLER_LOGFILE}
    fi
    echo 0 > /sys/class/gpio/gpio${GPIO_OUTPUT}/value
  fi
  exit 1
}

function sync_to_s3 {
  # If enabled in config, sync outputs to S3
  if [[ "${ENABLE_S3_SYNC,,}" = "1" ]] || [[ "${ENABLE_S3_SYNC,,}" = "enabled" ]] || [[ "${ENABLE_S3_SYNC,,}" = "yes" ]]; then
    # sync to s3, if error is aws cli installed, is path correct, check permissions IAM, etc
    if [[ "${S3_PUBLIC_ACCESS,,}" = "1" ]] || [[ "${S3_PUBLIC_ACCESS,,}" = "enabled" ]] || [[ "${S3_PUBLIC_ACCESS,,}" = "yes" ]]; then
      ACL_ARG="--acl public-read"
    else
      ACL_ARG=
    fi
    echo "Attempting to sync logfiles and data to specified AWS S3 location ${S3_DESTINATION_PATH}"
    ERROR_COUNTER=0
    # Avoid double-copying logs if they are in same dir as analysis outputs
    if [[ $(dirname "${DATA_LOGFILE}") != "${ANALYSIS_OUTDIR%/}" ]]; then
      # Use sync rather than copy although clunky for a single file to prevent unecessary PUT if file not changed
      aws s3 sync ${ACL_ARG} --exclude "*" --include $(basename "${DATA_LOGFILE}") $(dirname "${DATA_LOGFILE}") "${S3_DESTINATION_PATH}"
      if [[ $? -ne 0 ]];then
        ((ERROR_COUNTER+=1))
      fi
    fi
    if [[ $(dirname "${CONTROLLER_LOGFILE}") != "${ANALYSIS_OUTDIR%/}" ]]; then
      # Use sync rather than copy although clunky for a single file to prevent unecessary PUT if file not changed
      aws s3 sync ${ACL_ARG} --exclude "*" --include $(basename "${CONTROLLER_LOGFILE}") $(dirname "${CONTROLLER_LOGFILE}") "${S3_DESTINATION_PATH}"
      if [[ $? -ne 0 ]];then
        ((ERROR_COUNTER+=1))
      fi
    fi
    aws s3 sync ${ACL_ARG} "${ANALYSIS_OUTDIR}" "${S3_DESTINATION_PATH}"
    if [[ $? -ne 0 ]];then
      ((ERROR_COUNTER+=1))
    fi
    if [[ ${ERROR_COUNTER} -ne 0 ]]; then
      echo "ERROR: AWS S3 sync did not complete successfully - check internet connection, AWS CLI is installed, configured path to destination bucket (${S3_DESTINATION_PATH}) is correct and there are rw permissions for controller on this location in AWS IAM"
    else
      echo "AWS S3 sync completed"
    fi
  else
    echo "AWS S3 sync is not enabled - it is only carried out if enabled in system config"
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
  ARG_STRING+="${SETPOINT_FILE}"
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
    trap "switch_off_and_exit" SIGHUP SIGINT # SIGTERM
    # Note safest is to switch off on all exits, but systemctl restart sends SIGTERM which leads to annoying brief dropout in demand every time config updated
  fi
  # Call controller with configured options
  if [[ ! -z ${WIRED_SENSOR_LABELS} ]]; then
    # In order to deal with channel labels with spaces, label array argument processed directly
    "${SCRIPTDIR}/control_temp.py" ${ARG_STRING} -n "${WIRED_SENSOR_LABELS[@]}"
  else
    "${SCRIPTDIR}/control_temp.py" ${ARG_STRING}
  fi
  if [[ $? -ne 0 ]]; then
    # If controller exited on error, switch off
    switch_off_and_exit
  fi
elif [[ "${1,,}" = "analyse" ]]; then
  # Control mode - run control_temp.py
  if [[ ! -d ${ANALYSIS_OUTDIR} ]]; then
    echo "ERROR: Specified output directory for log analysis ${ANALYSIS_OUTDIR} does not exist"
    exit 1
  fi
  if [[ ! -s  ${CONTROLLER_LOGFILE} ]]; then
    echo "ERROR: Specified log to analyse ${ANALYSIS_OUTDIR} does not exist or is empty - nothing to analyse"
    exit 1
  fi
  START_ARG=$(date -u +%s -d "${START_DATE}")
  if [[ ${?} -ne 0 ]]; then
    echo "ERROR: Cannot parse specified start date ${START_DATE} - must be readable by GNU date - using default ('2020-01-01' - i.e. all available data)"
    START_ARG=$(date -u +%s -d "2020-01-01")
  fi
  END_ARG=$(date -u +%s -d "${END_DATE}")
  if [[ ${?} -ne 0 ]]; then
    echo "ERROR: Cannot parse specified end date ${END_DATE} - must be readable by GNU date - using default ('now' - i.e. all available data)"
    START_ARG=$(date -u +%s -d "now")
  fi
  ARG_STRING="${CONTROLLER_LOGFILE} ${START_ARG} ${END_ARG} ${ANALYSIS_OUTDIR}"
  # Call controller analysis script with configured options
  "${SCRIPTDIR}/controller_analyse.py" ${ARG_STRING}
  if [[ ${?} -eq 0 ]]; then
    # Copy latest data to consistent static filenames (no timestamps) so can easily link if published on web (e.g. via S3)
    LATEST_CSV=$(find "${ANALYSIS_OUTDIR}" -name "????????_??????_controller_analysis.csv" | sort -n | tail -n1)
    cp "${LATEST_CSV}" "${ANALYSIS_OUTDIR}"/controller_analysis.csv
    LATEST_BAR=$(find "${ANALYSIS_OUTDIR}" -name "????????_??????_controller_log_plot_bar.png" | sort -n | tail -n1)
    cp "${LATEST_BAR}" "${ANALYSIS_OUTDIR}"/controller_log_plot_bar.png
    LATEST_CHART=$(find "${ANALYSIS_OUTDIR}" -name "????????_??????_controller_log_plot.png" | sort -n | tail -n1)
    cp "${LATEST_CHART}" "${ANALYSIS_OUTDIR}"/controller_log_plot.png
    # Push data to AWS -if configured
  else
    # Analysis did not complete successfully, no outputs to copy
    echo "WARNING: controller analysis did not complete successfully, ignoring outputs"
  fi
  sync_to_s3
elif [[ "${1,,}" = "sync" ]]; then
  sync_to_s3
else
  echo "ERROR: Unrecognised/missing function ${1} - valid arguments are 'set', 'get', 'control', 'analyse', 'sync'"
  exit 1
fi
