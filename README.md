# raspi-temperature-controller
Simple binary ("bang-bang") temperature controller, based on Raspberry Pi and 1-wire sensor(s), with relay output, data and status logging, and cloud data push

## Description

This simple temperature controller is based on low-cost and easy-to-build raspberry Pi hardware, with 1-wire temperature sensor(s), and outputs via relay(s) that provide on/off control with hysteresis to the heating (or cooling) load(s).

This project includes both the software and a description of the hardware, including schematic and parts list. A simple example circuit is provided that uses an LED co-located with the temperature sensor for demonstration.

The controller software is configurable and flexible, capable of storing temperature from multiple sensors, and it stores data to a CSV datafile and controller operations to a logfile.  The controller can be run as a systemd service, or periodically from cron.  Using cron it is also easy to automate scheduled setpoint changes, log analysis and data upload to cloud.  Service files and crontab examples are provided.

This project is the basis of the system that has been controlling the central heating system in my flat since 2014 :) (https://aaronlockton.com/)

## Quick Start Guide

### Run direct from repo

- Clone git repo
- Run scripts using wrapper _temperature_controller.sh_ as shown below
- If required edit config file at _config/controller.conf_ (note _/etc/controller.conf_ will always take precedence if it exists

```
./temperature_controller.sh get - return current temperatures, setpoint and status to STDOUT
./temperature_controller.sh set [<temperature] - with argument set setpoint specified, with no argument get setpoint
./temperature_controller.sh control - run a single controller cycle and exit
./temperature_controller.sh control continuous - run control cycles continuously with wait interval specified in config
./temperature_controller.sh analyse - run controller log analysis to generate daily stats and plots (requires at least one full days data in controller log)
./temperature_controller.sh sync - sync data in output directory if enabled in config file (this is also run after 'analyse'
```

### Install and run as a service

- Clone git repo
- Run installer

```
sudo ./install.sh
```

- If 1-wire driver not previously installed, reboot to apply changes, otherwise log out and back in to enable aliases
- use aliases _s_, _g_, _a_, _s3_ to run set, get, analyse and sync described above
- edit _/etc/controller.conf_ to configure system as required
- edit _/etc/crontab_, uncomment required lines and set times and setpoints to automate setting setpoint, running analysis and syncing data to AWS S3
- Note installer will update apt repos and install required dependencies

## Software

Separate scripts are provided in _scripts_ directory to control setpoint from the command line, show latest readings and status, analyse the output from the controller to plot PNG graph of daily usage and upload to cloud.  A wrapper script _temperature_controller.sh_ can be used to access all these scripts, using settings in config file, or they can be called directly using command line arguments.  An overview of each script, including inputs and outputs can be found in the headers.

The controller itself can be found at _scripts/control_temp.py_ and details of input arguments can be found by running _scripts/control_temp.py -h_. The basic control strategy is based on control cycles which can be triggered manually or in continuous mode will be run repeatedly with a specified wait interval in seconds between cycles. Each cycle, temperature will be read from all available/configured sensors, and the setpoint and control temperature sensor reading are compared. If a list of sensor IDs is supplied, the first on the list will be used as the control sensor.

The installer _install.sh_ updates apt repo and installs dependencies (note this can take some time depending on when repo was last updated and what is already installed), sets.up users and groups, and copies all scripts and files to their respective locations. It sets up service files and starts and enables them on boot. It also adds example lines to /etc/crontab but these are commented to allow user to edit and enable as required. Note if an existing installation exists the existing controller config file, output directory and crontab lines will not be overwritten (however any custom paths/directories set in config will be ignored and defaults used. At the end, a summary of the install, any warnings (non-fatal errors) that occured and next steps to get started. If a fatal error occurs it will abandon the installation and exit immediately. If not already present, the device-tree overlay for 1-wire devices will be enabled, and this requires a reboot to apply changes. Note the very early Raspbian distributions do not use device tree.

Note in order to control GPIO the user must be in 'gpio' group and for _g_ or _temprt_ to return CPU temperature the user must be in 'video' group. To allow both use of command line tools and automated running via cron/services, user(s) must be in 'tempctl' group, and vice versa. This is set up by _install.sh_, which first creates 'tempctl' user.  This allows all controller functions to be used from command line without sudo/root. Similarly, all the controller service and cron tasks are all run as 'tempctl' user, since it is better practice for security to avoid running processes as root where possible.  For example, running the controller process with mimumum possible priviliges reduces the harm that could be done by an attacher attempting to inject malicioous code into the system configuration file.  The only script that requires sudo/root priviliges is _install.sh_ which is only run once.

  *** S3 IAM access for tempctl user and any interactive users of controller - lots of ways of managing AWS permissions and IAM (and lots of pitfalls and mistakes made!) well beyond scope of this - one way to achieve add to controller.conf "export AWS_ACCESS_KEY_ID= / export AWS_SECRET_ACCESS_KEY=" BUT SECURITY WISE NOT IDEAL!! ),
  *** note aliases require login shell
  *** note assume tz UTC on controller OS - internally controller uses UTC in all logs etc but OS features such as cron of course depend on OS time

### Control strategy

### Configuration file

### Multi-channel control

  *** to enable multiple control channels simply run multiple processes - systemctl syntax / run indivual scripts with ENV / limitations-run from wrapper only not aliases etc.  Note any changes to setpoint from any processes will result in all controller services being restarted. Also note on possible issues with multiple processes all reading all sensors?

## Hardware

## Example outputs

## Requirements

- Raspberry Pi with Raspbian OS and suitable hardware as described above
- Raspbian OS (may work with other operating systems, particularly Debian based, but this is untested)
- _bc_ and _awscli_ packages installed
- Python3 (will run on Python2 if headers in Python scripts changed), with Python3 module _matplotlib_ (must be installed for all users)
- Write access to an Amazon AWS S3 bucket (if S3 data sync is enabled) for _tempctl_ user and any interactive users

All required dependencies that are not present on the current Raspbian image will be installed by _install.sh_.  Note there may be conflicts if _matplotlib_ is already installed for the user only.
s
## IMPORTANT SAFETY INFORMATION

The example circuits given in this project do not contain any voltages above 5 Volts.  If being used to control a real heating/cooling load there are several *VITAL* safety considerations which *MUST* be adhered to:

- Heater or cooler must have over/under-temperature protection and be safe to leave "ON" permanently. It must have automatic and manual E-stop circuitry (independent to this controller) to shut it down in the event of any controller or heater/cooler malfunction, over/under temperature, etc.  The hardware and software described above *CANNOT* be relied upon to switch the load off under all circustances (e.g. running periodically in cron the line may be removed/commented; if system is misconfigured or service is stopped - note to prevent brief interruption to demand signal stopping/restarting service does *NOT* switch off demand; or if any failure occurs in the controller hardware or software)
- Any wiring or circuitry that includes potentials above 50 V should be built (or at minimum checked and approved by) a qualified electrician
- It is recommended to use suitably certified commercial-off-the-shelf parts to wire up any voltages exceeding 50 V (e.g. relay boards, terminals, wiring to load, etc).  *NEVER* use prototyping boards such as breadboard or veroboard to handle mains voltages under any circumstances!
- Ensure proper circuit protection is in place (MCBs for overcurrent, RCD protection for Earth/ground leaks, etc)
- Ensure proper Earthing/grounding of all supplies to and from all system components, ensure all metal parts and enclosures are properly bonded to Earth/ground
- Ensure all voltages above 50 V are carried using properly insulated wires and cable rated for the voltage and current in use.  Ensure no exposed voltages are present or can be accessed when the system is powered on, and all voltages above 50 V are only present inside properly designed enclosures.
- Ensure all system components are completely isolated from all supplies before being worked on in any any way or removing any covers.

Use of the hardware and software in raspi-temperature-controller is entirely at your own risk!
