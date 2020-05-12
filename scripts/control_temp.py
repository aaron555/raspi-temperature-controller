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
# 05/2020 - Removed hard-coded inputs and changed to arguments, changed default logging to CSV, added python3 compatibility, added optional continuous mode with configurable cycle interval, added support for multiple temperature sensors, added support for coolers

# Copyright (C) 2014, 2020 Aaron Lockton

import sys
import os
import glob
from time import sleep, gmtime, strftime, time
import argparse

# Debug messages (verbose mode)
def verbose_print(message):
  if args.verbose:
    print("%s: DEBUG: %s" % (strftime("%Y-%m-%d-%H:%M:%S", gmtime()), message))

def format_print(message):
  print("%s: %s" % (strftime("%Y-%m-%d-%H:%M:%S", gmtime()), message))

# Configure GPIO specified and set direction specified, if not already configured
def configure_gpio(gpionum,direction):
  if direction != "in" and direction != "out":
    return None
  gpionum = str(gpionum)
  # Export GPIO to allow it to be used
  if not os.path.exists('/sys/class/gpio/gpio'+gpionum+'/'):
    verbose_print("GPIO "+gpionum+" is not configured - exporting")
    export_status = os.WEXITSTATUS(os.system('echo '+gpionum+' > /sys/class/gpio/export 2>/dev/null'))
    if export_status != 0:
      format_print("ERROR: Cannot configure GPIO "+gpionum+" is this a valid GPIO number?")
      sys.exit(1)
  # Set GPIO direction
  with open('/sys/class/gpio/gpio'+gpionum+'/direction', 'r') as f:
    current_direction = f.readline().rstrip()
    verbose_print("Current GPIO "+gpionum+" setting: " + current_direction)
  if current_direction != direction:
    # If direction is not correct, may have only just been exported, need delay to prevent failure due to first-run permissions issue in Raspbian
    sleep(1)
    verbose_print("Setting GPIO "+gpionum+" direction to "+direction)
    direction_status = os.WEXITSTATUS(os.system('echo '+direction+' > /sys/class/gpio/gpio'+gpionum+'/direction 2>/dev/null'))
    if direction_status != 0:
      format_print("ERROR: Cannot set direction of GPIO "+gpionum)
      sys.exit(1)

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
  os.system('echo '+value+' > /sys/class/gpio/gpio'+gpionum+'/value')

# Read temperature from 1-wire sensor on GPIO7 -returns None on error, or the temperature as a float
def get_temp(devicefile):
  try:
    with open(devicefile, 'r') as f:
      lines = f.readlines()
  except:
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
  help='1-wire temperature sensor ID(s) e.g. "28-xxxx" (default: first of /sys/bus/w1/devices/28-*/w1_slave detected) - NOTE if multiple temperature sensors specified, first sensor in list will be used for control')
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
parser.add_argument('--interval', '-i', type=float, metavar='SECONDS',
  help='Interval between control cycle (s) - specify to enable continuous mode - default: run once and exit')
parser.add_argument('--verbose', '-v', action='store_true',
  help='Verbose mode - if this flag is set additional messages of control process sent to STDOUT - useful for debugging')
args = parser.parse_args()

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
    sys.exit(1)

hysteresis = args.hysteresis
if hysteresis < 0:
  format_print("ERROR: hysteresis cannot be negative!")
  sys.exit(1)

if args.sensorid:
  # set temp_sensor(s) to specified list - handle errors later when list iterated
  temp_sensors = args.sensorid
else:
  # Find list of /sys/bus/w1/devices/28-*/w1_slave and select first
  sensor_list = glob.glob('/sys/devices/w1_bus_master1/28*/w1_slave')
  if not sensor_list:
    format_print("ERROR: Cannot find any 1-wire temperature sensors on 1-wire bus, ensure temperature sensor(s) are properly connected")
    sys.exit(1)
  temp_sensors = [sensor_list[0].split('/')[4]]

if args.label:
  temp_labels = args.label
else:
  if len(temp_sensors) == 1:
    temp_labels = ["Current"]
  else:
    temp_labels=temp_sensors

if len(temp_labels) != len(temp_sensors):
  format_print("ERROR: Number of label(s) (--label) must match number of sensor(s) (--sensorid) if both arguments are specified")
  sys.exit(1)

gpio_output = args.gpioout

if args.gpiofeedback:
  gpio_feedback = args.gpiofeedback
else:
  gpio_feedback = gpio_output

logfile_fullpath = args.logfile

cycle_interval = args.interval
if cycle_interval and cycle_interval < 0:
  format_print("ERROR: interval cannot be negative!")
  sys.exit(1)

verbose_print("Setpoint: "+str(setpoint)+"  Hysteresis: "+str(hysteresis)+"  Temperature sensor(s): "+','.join(temp_sensors)+"  Channel label(s): "+','.join(temp_labels))

# Prepare CSV file header for data log
CSV_header = "Timestamp,Setpoint (C),"
for temp_label in temp_labels:
  CSV_header += temp_label+" Temperature (C),"
CSV_header += "Demand Status (0/1)\n"
verbose_print("CSV header: "+CSV_header)

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
  verbose_print("Current Temperature(s): "+''.join(str(current_temps)))
  # If multiple sensors, note first sensor specified is always used for control
  current_temp = current_temps[0]
  if current_temp == "":
  # If error occurs on control channel it is critical error, otherwise ignore
    format_print("ERROR: Cannot get current temperature from control channel, cannot run control cycle")
    if cycle_interval:
      # In continuous mode, wait for next cycle and try again
      sleep(cycle_interval)
      continue
    else:
      sys.exit(1)

  # Compare temperature with setpoint, set heating/cooling demand signal accordingly
  # Note empirically switch on below setpoint and off at setpoint works best for many heating systems, since reaction to demand on tends to be faster than off
  verbose_print("Comparing measured temperature and setpoint")
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
    verbose_print("Demand required, checking if system is on")
    if status == 0:
      print("%s: Setpoint=%s, Actual=%s - Switching system on" % (strftime("%Y-%m-%d-%H:%M:%S", gmtime()), setpoint, current_temp))
      set_gpio(gpio_output,"1")
      status = 1
  elif below:
    verbose_print("Demand not required, checking if system is on")
    if status == 1:
      print("%s: Setpoint=%s, Actual=%s - Switching system off" % (strftime("%Y-%m-%d-%H:%M:%S", gmtime()), setpoint, current_temp))
      set_gpio(gpio_output,"0")
      status = 0
  else:
    verbose_print("Temperature OK")
    pass

  # Read back demand signal - if spare relay contacts (DP), can test here if relay has actually switched
  # Else if additional GPIO for feedback not specified, check status of GPIO output matches demand
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
    sleep(cycle_interval)
  else:
    break
