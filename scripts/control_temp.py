#!/usr/bin/env python3

# Simple binary temperature controller for Raspberry Pi with configurable hysteresis and logging of control and data

# INPUTS:
# <Setpoint> must be specified - may be either a Temperature in (C) or a string containing path to a file containing this value
# All other input arguments are optional
# ./control_temp.py -h for a list of supported input arguments

# OUTPUTS:
# Demand signal set on selected GPIO pin
# All changes in status with inputs to STDOUT. This can be stored in log and analysed with controller_analyse.py to create daily plots of demand/stats
# (STDOUT messages are tagged with WARNING:/ERROR: for non-critical/critical exceptions respectively, and DEBUG: for additional messages in --verbose mode)
# Timestamped logfile with setpoint, measured temperature and status.  Default is Excel friendly CSV.  Includes all measured temperatures, and optionally user specified channel labels in header

# EXAMPLE CALLS
# ./control_temp.py 27 >> /home/aaron/control_temp.log
# ./control_temp.py setpoint --verbose --logfile mylog.csv -s 28-0300a2796e9e 28-0300a279f011 -n "Channel 1" "Channel 2" -i 10 -t 0.2

# NOTE if multiple temperature sensors (--sensorid) are specified, the first sensor in the list will always be used for control, but all will be read and logged
# If labels (--label) are also specified, the number of labels specified must match the number of sensors (--sensorid)
# For multi-channel temperature control (multiple outputs), run a separate instance of this script for each channel, specifying appropriate temperature sensor input and GPIO output, logfile (optionally channel name) for each

# Changelog
# 04/11/4014 - First Version
# 06/2020 - Removed hard-coded inputs and changed to arguments, changed default logging to CSV, added python3 compatibility, added optional continuous mode with configurable cycle interval, added support for multiple temperature sensors, added support for coolers

# Copyright (C) 2014, 2020 Aaron Lockton

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

import sys
import os
import glob
from time import sleep, gmtime, strftime, time
import argparse

# Allow all group users to write to files created by this script
oldmask = os.umask(0o002)

# Exit if an error occurs, attempt to switch off demand signal
def exit_on_error():
  set_gpio(gpio_output,"0")
  # Put back umask
  os.umask(oldmask)
  sys.exit(1)

# Format and print/log message
def format_print(message,verbose=None):
  if not verbose:
    # Messages always printed - status changes, ERROR/WARNING
    message_print=("%s: %s" % (strftime("%Y-%m-%d-%H:%M:%S", gmtime()), message))
  elif args.verbose:
    # Only print DEBUG messages in verbose mode
    message_print=("%s: DEBUG: %s" % (strftime("%Y-%m-%d-%H:%M:%S", gmtime()), message))
  else:
    # Ignore DEBUG messages unless in verbose mode
    return 0
  print(message_print)
  # Optionally write all messages to file as well as STDOUT
  if args.messagelog:
    try:
      with open(args.messagelog, 'a') as f:
        f.write(message_print+"\n")
    except:
      print("%s: WARNING: Cannot write to specified logfile %s - check correct path/filename and permissions" % (strftime("%Y-%m-%d-%H:%M:%S", gmtime()), args.messagelog))

# Configure GPIO specified and set direction specified, if not already configured
def configure_gpio(gpionum,direction):
  if direction != "in" and direction != "out":
    return None
  gpionum = str(gpionum)
  # Export GPIO to allow it to be used
  if not os.path.exists('/sys/class/gpio/gpio'+gpionum+'/'):
    format_print("GPIO "+gpionum+" is not configured - exporting", "verbose")
    export_status = os.WEXITSTATUS(os.system('echo '+gpionum+' > /sys/class/gpio/export 2>/dev/null'))
    if export_status != 0:
      format_print("ERROR: Cannot configure GPIO "+gpionum+" is this a valid GPIO number?")
      # If error occurs, still attempt to switch off - GPIO out may already be configured if failure is setting GPIO feedback
      exit_on_error()
  # Set GPIO direction
  with open('/sys/class/gpio/gpio'+gpionum+'/direction', 'r') as f:
    current_direction = f.readline().rstrip()
    format_print("Current GPIO "+gpionum+" setting: " + current_direction, "verbose")
  if current_direction != direction:
    # If direction is not correct, may have only just been exported, need delay to prevent failure due to first-run permissions issue in Raspbian
    sleep(1)
    format_print("Setting GPIO "+gpionum+" direction to "+direction, "verbose")
    direction_status = os.WEXITSTATUS(os.system('echo '+direction+' > /sys/class/gpio/gpio'+gpionum+'/direction 2>/dev/null'))
    if direction_status != 0:
      format_print("ERROR: Cannot set direction of GPIO "+gpionum)
      # If error occurs, still attempt to switch off - GPIO out may already be configured if failure is setting GPIO feedback
      exit_on_error()

# Read GPIO value from specified GPIO
def get_gpio(gpionum):
  gpionum = str(gpionum)
  with open('/sys/class/gpio/gpio'+gpionum+'/value', 'r') as f:
    status = int(f.readline())
    return status

# Set specified GPIO to specified value
def set_gpio(gpionum,value):
  gpionum = str(gpionum)
  if value != "0" and value != "1":
    return None
  try:
    os.system('echo '+value+' > /sys/class/gpio/gpio'+gpionum+'/value')
  except:
    format_print("ERROR: Failed to set GPIO "+gpionum+" to value "+value+" - check GPIO is exported and user has permissions (in gpio group)")

# Read temperature from 1-wire sensor on GPIO7 -returns None on error, or the temperature as a float
def get_temp(devicefile):
  try:
    with open(devicefile, 'r') as f:
      lines = f.readlines()
  except:
    return None

  if len(lines) != 2:
    return None

  # Occasionally after sensors are unplugged status can be YES but all values zero
  null_response = "00 00 00 00 00 00 00 00 00"
  # Null response is never valid even if temp and thresholds are zero - but eg config register always ends 'f'
  if lines[0][0:26] == null_response or lines[1][0:26] == null_response:
    return None

  # get the status from the end of line 1
  status = lines[0][-4:-1]

   # is the status is ok, get the temperature from line 2
  if status=="YES":
    tempstr =  lines[1].rsplit("t=")[1]
    tempvalue=float(tempstr)/1000
    return tempvalue
  else:
    return None

# Parse input arguments
parser = argparse.ArgumentParser(description='Simple Temperature Controller.')
parser.add_argument('setpoint', type=str,
  help='Setpoint Temperature (C) or path to file containing setpoint')
parser.add_argument('--hysteresis', '-t', type=float, default=0.1, metavar='TEMPERATURE',
  help='Hystersis between switch-off and switch on (C) - default: 0.1')
parser.add_argument('--cooler', '-c', action='store_true',
  help='By default assume controlling heater - set this flag for cooler (invert output / move hysteresis above setpoint)')
parser.add_argument('--sensorid', '-s', type=str, nargs='+', metavar='STRING',
  help='1-wire temperature sensor ID(s) e.g. "28-xxxx" (default: all available 1-wire sensors) - NOTE if multiple temperature sensors specified/found, first sensor in list will be used for control')
parser.add_argument('--label', '-n', type=str, nargs='+', metavar='STRING',
  help='Channel label(s)/name(s) used as prefix in data log header column header(s) - default: "Current"')
parser.add_argument('--gpioout', '-g', type=int, default=17, metavar='GPIO',
  help='GPIO pin for output demand signal - default: GPIO17 / Pin 11 (integer)')
parser.add_argument('--gpiofeedback', '-f', type=int, metavar='GPIO',
  help='GPIO pin for optional feedback signal from relay or system under control - default same as --gpioout (integer)')
parser.add_argument('--logfile', '-l', type=str, metavar='FILENAME', default="temperature_data.csv",
  help='Full path and filename of output logfile for temperature and setpoint data - default: "temperature_data.csv" (string)')
parser.add_argument('--legacylog', '-y', action='store_true',
  help='Legacy logging mode - if this flag is set uses legacy logfile format - default: Excel-friendly CSV')
parser.add_argument('--messagelog', '-m', type=str, metavar='FILENAME',
  help='Full path and filename of optional output logfile for controller messages - if not specified messages sent to STDOUT only (string)')
parser.add_argument('--interval', '-i', type=float, metavar='SECONDS',
  help='Interval between control cycle (s) - specify to enable continuous mode - default: run once and exit')
parser.add_argument('--verbose', '-v', action='store_true',
  help='Verbose mode - if this flag is set additional messages of control process sent to STDOUT - useful for debugging')
args = parser.parse_args()

# Deal with GPIO out for demand first, since it is used in all error handling
gpio_output = args.gpioout

# Check input argumants, set defaults where necessary and validate
setarg = args.setpoint
try:
  # If we can convert to float use directly...
  setpoint = float(setarg)
except:
  # ...Otherwise assume it is path of setpoint file
  try:
    with open(setarg, 'r') as f:
      setpoint = float(f.readline())
  except:
    format_print("ERROR: "+setarg+" cannot be found/opened or does not contain a valid setpoint")
    exit_on_error()

hysteresis = args.hysteresis
if hysteresis < 0:
  format_print("ERROR: hysteresis cannot be negative!")
  exit_on_error()

if args.sensorid:
  # set temp_sensor(s) to specified list - handle errors later when list iterated
  temp_sensors = args.sensorid
else:
  # Find list of /sys/bus/w1/devices/28-*/w1_slave and select first
  sensor_list = glob.glob('/sys/devices/w1_bus_master1/28*/w1_slave')
  if not sensor_list:
    format_print("ERROR: Cannot find any 1-wire temperature sensors on 1-wire bus, ensure temperature sensor(s) are properly connected")
    exit_on_error()
  temp_sensors = [ele.split('/')[4] for ele in sensor_list]

if args.label:
  temp_labels = args.label
else:
  if len(temp_sensors) == 1:
    temp_labels = ["Current"]
  else:
    temp_labels=temp_sensors

if len(temp_labels) != len(temp_sensors):
  format_print("ERROR: Number of label(s) (--label) must match number of sensor(s) (--sensorid) if both arguments are specified")
  exit_on_error()

if args.gpiofeedback:
  gpio_feedback = args.gpiofeedback
else:
  gpio_feedback = gpio_output

logfile_fullpath = args.logfile

cycle_interval = args.interval
if cycle_interval and cycle_interval < 0:
  format_print("ERROR: interval cannot be negative!")
  exit_on_error()

format_print("Setpoint: "+str(setpoint)+"  Hysteresis: "+str(hysteresis)+"  Temperature sensor(s): "+','.join(temp_sensors)+"  Channel label(s): "+','.join(temp_labels), "verbose")

# Prepare CSV file header for data log
CSV_header = "Timestamp,Setpoint (C),"
for temp_label in temp_labels:
  CSV_header += temp_label+" Temperature (C),"
CSV_header += "Demand Status (0/1)\n"
format_print("CSV header: "+CSV_header, "verbose")

# Set up GPIOs
configure_gpio(gpio_output,"out")
if gpio_output != gpio_feedback:
  configure_gpio(gpio_feedback,"in")

# Main loop - continues once per --interval seconds or if --interval is not set execcutes one cycle and exits
while True:
  # Get current temperature from sensor
  current_temps = []
  for temp_sensor in temp_sensors:
    current_temps.append(get_temp('/sys/bus/w1/devices/'+temp_sensor+'/w1_slave'))
    if current_temps[-1] == None:
      format_print("WARNING: Cannot get current temperature from sensor "+temp_sensor+" - check 1-wire driver enabled, sensor is connected correctly and (if set) --sensorid is correct")
      current_temps[-1] = ""
  format_print("Current Temperature(s): "+''.join(str(current_temps)), "verbose")
  # If multiple sensors, note first sensor specified is always used for control
  current_temp = current_temps[0]
  if current_temp == "":
  # If error occurs on control channel it is critical error, otherwise ignore
    format_print("ERROR: Cannot get current temperature from control channel, cannot run control cycle")
    if cycle_interval:
      # In continuous mode, wait for next cycle and try again
      try:
        # Note for controller analyse must contain exact string "Switching system off"
        format_print("Switching system off and wating for retry next cycle")
        set_gpio(gpio_output,"0")
        sleep(cycle_interval)
      except KeyboardInterrupt:
        # Note for controller analyse must contain exact string "Switching system off"
        format_print("Keyboard interrupt - Switching system off demand and exiting temperature controller")
        exit_on_error()
      continue
    else:
      # in one-shot mode, exit if temperature cannont be found
      exit_on_error()

  # Compare temperature with setpoint, set heating/cooling demand signal accordingly
  # Note empirically switch on below setpoint and off at setpoint works best for many heating systems, since reaction to demand on tends to be faster than off
  format_print("Comparing measured temperature and setpoint", "verbose")
  if args.cooler:
    # For cooler, switch on at hysteresis above setpoint and off at setpoint
    above = (current_temp - hysteresis) > setpoint
    below = current_temp < setpoint
  else:
    # For heater, switch on hysteresis below setpoint and off at setpoint
    above = (current_temp + hysteresis) < setpoint
    below = current_temp > setpoint
  status = get_gpio(gpio_output)
  if above:
    format_print("Demand required, checking if system is on", "verbose")
    if status == 0:
      # Note for controller analyse must contain exact string "Switching system on"
      status_message=("Setpoint=%s, Actual=%s - Switching system on" % (setpoint, current_temp))
      format_print(status_message)
      set_gpio(gpio_output,"1")
      status = 1
  elif below:
    format_print("Demand not required, checking if system is on", "verbose")
    if status == 1:
      # Note for controller analyse must contain exact string "Switching system off"
      status_message=("Setpoint=%s, Actual=%s - Switching system off" % (setpoint, current_temp))
      format_print(status_message)
      set_gpio(gpio_output,"0")
      status = 0
  else:
    format_print("Temperature OK", "verbose")
    pass

  # Read back demand signal - if spare relay contacts (DP), can test here if relay has actually switched
  # Else if additional GPIO for feedback not specified, check status of GPIO output matches demand
  sleep(0.1)
  # Need to allow time for mechanical relay to switch (if in use)
  actual_status = get_gpio(gpio_feedback)

  if actual_status != status:
    format_print("ERROR: Requested demand status "+str(status)+" but actual status "+str(actual_status)+" - failed to set demand signal!")

  try:
    # Write temperature, setpoint and actual status to log - Note all all timestamps in UTC
    with open(logfile_fullpath,"a") as f:
      if args.legacylog:
        # Backwards compatibilty - Use previous message-style log - note does not support multiple temperature sensors
        f.write("%s %d Setpoint: %s Actual: %s Status: %s \n" % (strftime("%Y-%m-%d-%H-%M-%S", gmtime()), time(), setpoint, current_temp, actual_status))
      else:
        # Write CSV file with Excel-friendly timestamp.  For CSV mode, write header if file does not exist
        if os.stat(logfile_fullpath).st_size == 0:
          f.write(CSV_header)
        f.write("%s,%s,%s,%s\n" % (strftime("%Y-%m-%d %H:%M:%S", gmtime()), setpoint, ','.join(map(str, current_temps)), actual_status))
  except:
    format_print("WARNING: Cannot open / write to logfile "+logfile_fullpath+" - check filename is correct and permissions?")

  # Check if one-shot mode or continuous - if interval argument is set use continuous
  if cycle_interval:
      try:
        sleep(cycle_interval)
      except KeyboardInterrupt:
        # Note for controller analyse must contain exact string "Switching system off"
        format_print("Keyboard interrupt - Switching system off and exiting")
        exit_on_error()
      continue
  else:
    break

# Put back umask
os.umask(oldmask)