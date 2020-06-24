# raspi-temperature-controller
Simple binary ("bang-bang") temperature controller, based on Raspberry Pi and 1-wire sensors, with relay outputs, data and status logging, and cloud data push

## Description

This simple temperature controller is based on low-cost and easy-to-build raspberry Pi hardware, with 1-wire temperature sensor(s), and outputs via relay(s) that provide on/off control with hysteresis to the heating (or cooling) load(s).

This project includes both the software and a description of the hardware, including schematic and parts list. A simple example circuit is provided that uses an LED co-located with the temperature sensor for demonstration.

The controller software is configurable and flexible, capable of storing temperature from multiple sensors, and it stores data to a CSV datafile and controller operations to a logfile.  The controller can be run as a systemd service, or periodically from cron.  Using cron it is also easy to automate scheduled setpoint changes, log analysis and data upload to cloud.  Service files and crontab examples are provided.

This project is the basis of the system that has been controlling the central heating system in my flat since 2014 :) (https://aaronlockton.com/)

## Quick Start Guide

### Run direct from repo

### Install and run as a service

*** describe installer and what it does to enable cron/systemctl vs from repo as user, note installing dependencies can take some time depwnding on update status and will run apt-get update + notes from installer stdout etc

### Hardware

### Software

## Software

Separate scripts are provided to control setpoint from the command line, show latest readings and status, analyse the output from the controller to plot PNG graph of daily usage and upload to cloud.  A wrapper script can be used to access all these scripts, using settings in config file, or they can be called directly using command line arguments.  An overview of each script, including inputs and outputs can be found in the headers.

*** userspace gpio-groups and CPU temp-older distro/to allow other users add to tempctl group, DT overlay 1-wire in update,

## Hardware

## Example outputs

## Requirements

- Raspberry Pi with Raspbian OS and suitable hardware as described above
- Raspbian OS (may work with other operating systems, particularly Debian based, but this is untested)
- _bc_ and _awscli_ packages installed
- Python3 (will run on Python2 if headers in Python scripts changed), with Python3 module _matplotlib_ (must be installed for all users)
- Write access to an Amazon AWS S3 bucket (if S3 data sync is enabled) for _tempctl_ user and any interactive users

All required dependencies that are not present on the current Raspbian image will be installed by _install.sh_.  Note there may be conflicts if _matplotlib_ is already installed for the user only.

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



  *** S3 IAM access for tempctl user and any interactive users of controller - lots of ways of managing AWS permissions and IAM (and lots of pitfalls and mistakes made!) well beyond scope of this - one way to achieve add to controller.conf "export AWS_ACCESS_KEY_ID= / export AWS_SECRET_ACCESS_KEY=" BUT SECURITY WISE NOT IDEAL!! ), 
  *** note aliases require login shell
  *** note assume tz UTC on controller OS - internally controller uses UTC in all logs etc but OS features such as cron of course depend on OS time 
  *** to enable multiple control channels simply run multiple processes (requires multiple config files-hence ENSURE NO /etc/controller.conf and use relative path config/controller.conf wrt each instance of script/note hard coded paths eg aliases OR edit scripts to point to reqd config)

