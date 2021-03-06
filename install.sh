#! /bin/bash

# Installs Raspberry Pi Temperature controller and dependencies, sets up baseline config, services, aliases and working directories

# SYNTAX: ./install.sh [-y]

# EXAMPLE CALLS
# sudo ./install.sh -y

# INPUTS
# Optionally give argument '-y' to run without user confirmation to proceed with install
# Requires root permissions
# If an existing config file exists /etc/controller.conf it will not be overwritten, however contents will be ignored and default paths used
# Similarly, no existing files in /var/log/temperature-controller will be overwritten, and example lines not added to crontab if already present

# OUTPUTS
# Summary to STDOUT, including if all tasks completed successfully or if warnings occured
# If a warning occurs, script continues, whereas errors are fatal the script exits immediately

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

## Define functions
# Exit on error
function exit_on_error {
  if [[ $1 -ne 0 ]]; then
    # Fatal error has occured
    echo "ERROR: ${2}"
    echo "Installation DID NOT complete - exiting..."
    exit $1
  fi
}

# Store warnings to display at end
WARNING_LIST=
function handle_warning {
  if [[ $1 -ne 0 ]]; then
    # non-fatal error has occured
    echo "WARNING: ${2}"
    WARNING_LIST+="WARNING: ${2} (code ${1})"$'\n'
  fi
}

## Handle CTRL-C etc termination and confirm proceed with install
trap "exit_on_error 1 'Installation cancelled by user - NOTE INSTALL WAS NOT COMPLETED'" SIGHUP SIGINT SIGTERM

echo "---------------------------------------------------------------------------"
echo "Starting 'raspi-temperature-controller' install process"
if [[ "${1}" != "-y" ]]; then
  echo "Do you wish to install Raspberry Pi Simple Temperature Controller? (y/n)"
  read USER_INPUT
  if [[ ! "${USER_INPUT}" =~ ^[Yy]$ ]]; then
      exit_on_error 1 "Operation cancelled"
  fi
fi

## Check system
# check run as root
exit_on_error "${EUID}" "This installer script must be run by root user or using sudo"

# check raspbian->if not warn
if ! grep -i raspbian /etc/os-release >/dev/null 2>&1; then
  handle_warning "1" "raspi-temperature-controller is only tested on Raspbian OS, but found a different distribution - please note this may lead to unexpected behaviour"
fi

## Install dependencies
echo "Installing dependencies - this requires an internet connection and may take some time..."
apt-get update
handle_warning $? "Could not update apt repo"
# Note libatlas-base-dev required to solve missing dependency with matplotlib installed using pip on Raspberry Pi - https://numpy.org/devdocs/user/troubleshooting-importerror.html
apt-get install -y bc python3-pip libatlas-base-dev awscli
handle_warning $? "Could not install dependencies: bc python3-pip awscli"
# Note it is acceptable to install legit modules such as matplotlib as root with pip - it must be available for all users
pip3 install matplotlib
handle_warning $? "Could not install dependencies: Python module matplotlib"

## Set up users and groups
echo "Setting up users and groups"
useradd -r tempctl
handle_warning $? "Could not create system user 'tempctl'"
# Add controller and interactive user to gpio group to allow setting demand signal
adduser tempctl gpio
handle_warning $? "Could not add user 'tempctl' to 'gpio' group to allow controller to set demand signal"
adduser "$(logname)" gpio
handle_warning $? "Could not add user $(logname) to 'gpio' group to allow interactive running of controller"
# Add controller and interactive user to video group to allow getting CPU temperature
adduser tempctl video
handle_warning $? "Could not add user 'tempctl' to 'video' group to allow controller to set demand signal"
adduser "$(logname)" video
handle_warning $? "Could not add user $(logname) to 'video' group to allow interactive running of controller"
# Add interactive user to controller group to allow access to setpoint, logfiles etc for running controller functions from command line
adduser "$(logname)" tempctl
handle_warning $? "Could not add user $(logname) to 'tempctl' group to allow interactive running of controller"
# Add controller user to interactive user group to allow both to run analysis and overwrite each others analysis outputs
adduser tempctl "$(logname)"
handle_warning $? "Could not add user 'tempctl' to group $(logname) to allow both user and syatem to run analysis"

## Create directories and move files from repo
echo "Copying scripts and setting up system"
mkdir -p /opt/scripts/temperature-controller/
exit_on_error $? "Couldn't create script dir /opt/scripts/temperature-controller/"
cp scripts/* /opt/scripts/temperature-controller/
exit_on_error $? "Couldn't copy scripts to /opt/scripts/temperature-controller/"
cp temperature_controller.sh /opt/scripts/temperature-controller/
exit_on_error $? "Couldn't copy scripts to /opt/scripts/temperature-controller/"
chown -R tempctl:tempctl /opt/scripts/temperature-controller/
handle_warning $? "Couldn't set ownership of scripts"
chmod -R 755 /opt/scripts/temperature-controller/
handle_warning $? "Couldn't set file modes (permissions) of scripts"
cp services/temperature-controller* /lib/systemd/system/
exit_on_error $? "Couldn't copy service files to /lib/systemd/system/"
chown root:root /lib/systemd/system/temperature-controller*
handle_warning $? "Couldn't set ownership of service files"
chmod 644 /lib/systemd/system/temperature-controller*
handle_warning $? "Couldn't set file modes (permissions) of service files"
cp services/aliases-temperature-controller.sh /etc/profile.d/
handle_warning $? "Couldn't copy alias definitions to /etc/profile.d/ - commands s,g,a,s3 may not work"
chown root:root /etc/profile.d/aliases-temperature-controller.sh
handle_warning $? "Couldn't set ownership of alias file"
chmod 644 /etc/profile.d/aliases-temperature-controller.sh
handle_warning $? "Couldn't set file modes (permissions) of alias files"

## Setup controller config
# Check if conf exists (/etc/controller.conf) - this is warning as changes installer behaviour (don't clobber old, but ignore any modified paths)
echo "Setting up controller config file"
if [[ -f /etc/controller.conf ]]; then
  handle_warning "1" "Found existing config file at /etc/controller.conf - note this file will NOT be edited, but this installer will use standard locations for all files"
  handle_warning "1" "For a clean install with defaults set in /etc/controller.conf, move/delete/rename existing file and run again"
else
  # For clean install only, set up default config file
  cp config/controller.conf /etc
  handle_warning $? "Couldn't copy config file to /etc"
  sed -i -e "/SETPOINT_FILE=/c\SETPOINT_FILE=\/etc\/controller-setpoints\/setpoint" /etc/controller.conf
  handle_warning $? "Couldn't edit config file"
  sed -i -e "/SCRIPTDIR=/c\SCRIPTDIR=\/opt\/scripts\/temperature-controller" /etc/controller.conf
  handle_warning $? "Couldn't edit config file"
  sed -i -e "/CONTROLLER_LOGFILE=/c\CONTROLLER_LOGFILE=\/var\/log\/temperature-controller\/control_temp.log" /etc/controller.conf
  handle_warning $? "Couldn't edit config file"
  sed -i -e "/DATA_LOGFILE=/c\DATA_LOGFILE=\/var\/log\/temperature-controller\/temperature_data.csv" /etc/controller.conf
  handle_warning $? "Couldn't edit config file"
  sed -i -e "/ANALYSIS_OUTDIR=/c\ANALYSIS_OUTDIR=\/var\/log\/temperature-controller" /etc/controller.conf
  handle_warning $? "Couldn't edit config file"
fi
# Ensure correct owner and permissions whether or not file already existed
chown tempctl:tempctl /etc/controller.conf
handle_warning $? "Couldn't set owner of config file"
chmod 664 /etc/controller.conf
handle_warning $? "Couldn't set mode (permissions) of config file"

## Create files and directories for outputs, logs and setpoint - mainly to ensure they have correct owner and permissions
# Note these paths may not match values of SETPOINT_FILE, CONTROLLER_LOGFILE, DATA_LOGFILE and ANALYSIS_OUTDIR if existing controller config is present and has been modified
echo "Setting up output directory for logs, analysis and S3 web example"
mkdir -p /var/log/temperature-controller
handle_warning $? "Couldn't create output dir"
chown tempctl:tempctl /var/log/temperature-controller
handle_warning $? "Couldn't set owner of output dir"
chmod 775 /var/log/temperature-controller
handle_warning $? "Couldn't set mode (permissions) of output dir"
# Check if there's any existing files in output directory
if [[ $(ls -A /var/log/temperature-controller) ]]; then
  handle_warning "1" "Output directory /var/log/temperature-controller contains files - these will not be overwritten - For a clean install remove all existing files"
fi
cp -n outputs/* /var/log/temperature-controller
handle_warning $? "Couldn't copy content to output dir"
chown tempctl:tempctl /var/log/temperature-controller/*
handle_warning $? "Couldn't set owner of output dir contents"
chmod  664 /var/log/temperature-controller/*
handle_warning $? "Couldn't set mode (permissions) output dir contents"
rm /var/log/temperature-controller/readme.txt
mkdir -p /etc/controller-setpoints
handle_warning $? "Couldn't create setpoints dir"
chown tempctl:tempctl /etc/controller-setpoints
handle_warning $? "Couldn't set owner of setpoints dir"
chmod 775 /etc/controller-setpoints
handle_warning $? "Couldn't set mode (permissions) of setpoints dir"
touch /etc/controller-setpoints/setpoint
handle_warning $? "Couldn't crete setpoint file"
chown tempctl:tempctl /etc/controller-setpoints/setpoint
handle_warning $? "Couldn't set owner of setpoint file"
chmod 664 /etc/controller-setpoints/setpoint
handle_warning $? "Couldn't set mode (permissions) setpoint file"

## Setup crontab and logging - note lines are added but commented for user to uncomment / modify as required
echo "Adding example lines to crontab for automation (commented - edit and uncomment to enable) and associated logging"
# Check if lines already exist in crontab - in which case do not copy anything to prevent bloating crontab
if grep temperature_controller.sh /etc/crontab 2>&1 >/dev/null; then
  handle_warning "1" "/etc/crontab already contains lines relating to temperature_controller.sh - not adding.  For a clean install remove all existing lines first"
else
  sed -e "0,/# m h dom mon dow user/d" services/crontab-example-lines | sed -e "s/^\([^#].*\)/# \1/g" >> /etc/crontab
  handle_warning $? "Couldn't add example lines to crontab"
fi
touch /var/log/controller-status.log
handle_warning $? "Couldn't create controller status log"
chown tempctl:tempctl /var/log/controller-status.log
handle_warning $? "Couldn't set owner of controller status log"
chmod 644 /var/log/controller-status.log
handle_warning $? "Couldn't set mode (permissions) of controller status log"
cp services/logrotate-controller-status /etc/logrotate.d/
handle_warning $? "Couldn't set up logrotate for controller status log"
chown root:root /etc/logrotate.d/logrotate-controller-status
handle_warning $? "Couldn't set owner of logrotate for controller status log"
chmod 644 /etc/logrotate.d/logrotate-controller-status
handle_warning $? "Couldn't set mode (permissions) of logrotate for controller status log"

## Enable and start services - note will be in error state until setpoint exists
echo "Starting and enabling at boot time services for controller - may take some time..."
systemctl daemon-reload
handle_warning $? "Couldn't set up services with systemctl"
systemctl restart temperature-controller@controller.conf.service
handle_warning $? "Couldn't set up services with systemctl"
systemctl restart temperature-controller-restarter@controller.conf.path
handle_warning $? "Couldn't set up services with systemctl"
systemctl enable temperature-controller@controller.conf.service
handle_warning $? "Couldn't set up services with systemctl"
systemctl enable temperature-controller-restarter@controller.conf.path
handle_warning $? "Couldn't set up services with systemctl"

## Setup 1-wire DT overlay if not already and prompt to reboot if not already set (warn if no /boot/config.txt - note already checked raspbian above)
if [[ -f /boot/config.txt ]]; then
  if ! grep "^dtoverlay=w1-gpio" /boot/config.txt 2>&1 >/dev/null; then
    echo "Enabling 1-wire interface driver (device tree overlay) on default GPIO4 / header pin 7"
    echo "NOTE: REBOOT WILL BE REQUIRED AFTER THIS INSTALLATION COMPLETES IN ORDER TO ENABLE 1-WIRE TEMPERATURE SENSORS"
    # Note - optionally can specify different pin x here by using: dtoverlay=w1-gpio,gpiopin=x
    echo "dtoverlay=w1-gpio" >> /boot/config.txt
  else
    echo "1-wire interface driver (device tree overlay) already enabled"
  fi
else
  # This is a warning state - warn and continue (should never occur is raspbian check passes so reference this too? - move to warning function
  handle_warning "1" "Failed to enable 1-wire driver - cannot find /boot/config.txt"
fi

## Clean up, feedback summary to user, print all warnings, describe current service status / crontab and next steps
echo "---------------------------------------------------------------------------"
if [[ -z ${WARNING_LIST}  ]]; then
  echo "Completed installation successfully"
else
  echo "Finished install but the following warnings occured:"
  echo ""
  echo "${WARNING_LIST}"
  echo "NOTE: system may not be in a functioning / fully functioning state"
fi
echo ""
echo "To get started:"
echo " -  Edit settings in /etc/controller.conf"
echo " -  To get current temperatures use 'g' command"
echo " -  Set setpoint temperature using 's' command"
echo " -  Run log analysis with 'a' (after at least 1 full day running) and s3 sync (if enabled in config) with 's3'"
echo " -  (Note it will be necesary to log out and back in to enable commands (aliases) and apply user/group changes)"
echo " -  Edit and uncomment lines in /etc/crontab as required to automate setpoint, analysis, S3 push"
echo ""
echo "Installer completed"
