#!/usr/bin/env python3

# Simple binary temperature controller with configurable hysterisis and control and data loggins

# INPUTS:
# <Setpoint> must be specified - may be either a value or a string containing path to a file containing the required value
# All other input arguments are optional
# ./control_temp.py -h for a list of supported input arguments

# OUTPUTS: Demand signal to GPIO; Summary of system status and any change in status to STDOUT; timestamped logfile with setpoint, measured temperature and status

# EXAMPLE CALL
# ./control_temp.py 27 >> /home/aaron/control_temp.log

# NOTE if multiple temperature sensors (--sensorid) are specified, the first sensor in the list will always be used for control, the others will just be read and logged
# If labels (--label) are also specified, the number of labels specified must match the number of sensors (--sensorid)
# For multi-channel temperature control, run a separate instance of this script for each channel, specifying appropriate temperature sensor input and GPIO output, logfile (optionally channel name) for each

# Changelog
# 04/11/4014 - First Version
# 05/2020 - Removed hard-coded inputs and changed to arguments, changed default logging to CSV, added python3 compatibility, added optional continuous mode with configurable cycle interval

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
    os.system('echo '+gpionum+' > /sys/class/gpio/export')
  # Set GPIO direction
  with open('/sys/class/gpio/gpio'+gpionum+'/direction', 'r') as f:
    current_direction = f.readline().rstrip()
    verbose_print("Current GPIO "+gpionum+" setting: " + current_direction)
  if current_direction != direction:
    # If direction is not correct, may have only just been exported, need delay to prevent failure due to first-run permissions issue in Raspbian
    sleep(1)
    verbose_print("Setting GPIO "+gpionum+" direction to "+direction)
    os.system('echo '+direction+' > /sys/class/gpio/gpio'+gpionum+'/direction')

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
parser.add_argument('--hysteresis', '-t', type=float, default=0.1, metavar='FLOAT',
  help='Hystersis between switch-off and switch on (C) - default: 0.1')
parser.add_argument('--cooler', '-c', action='store_true',
  help='By default assume controlling heater - set this flag for cooler (invert output / move hysteresis above setpoint)')
parser.add_argument('--sensorid', '-s', type=str, nargs='+', metavar='STRING',
  help='1-wire temperature sensor ID e.g. "28-xxxx" (default: first of /sys/bus/w1/devices/28-*/w1_slave detected) - NOTE if multiple temperature sensors specified, first sensor in list will be used for control')
parser.add_argument('--label', '-n', type=str, nargs='+', metavar='STRING',
  help='Channel label/name prefix for temperature sensor(s) in log header - default: "Current"')
parser.add_argument('--gpioout', '-g', type=int, default=17, metavar='GPIO',
  help='GPIO pin for output heating demand signal - default: GPIO17 / Pin 11 (integer)')
parser.add_argument('--gpiofeedback', '-f', type=int, metavar='GPIO',
  help='GPIO pin for feedback signal from heater - default same as --gpioout (integer)')
parser.add_argument('--logfile', '-l', type=str, metavar='FILENAME', default="temperature_data.csv",
  help='Full path and filename of output logfile for temperature and setpoint data - default: "temperature_data.csv" (string)')
parser.add_argument('--legacylog', '-y', action='store_true',
  help='Legacy logging mode - if this flag is set uses legacy logfile format instead of default: Excel-friendly CSV')
parser.add_argument('--interval', '-i', type=float, metavar='SECONDS',
  help='Interval between control cycle (s) - specify to enable continuous mode - default: run once and exit')
parser.add_argument('--verbose', '-v', action='store_true',
  help='Verbose mode - if this flag is set additional messages of control process sent to STDOUT - useful for debugging')
args = parser.parse_args()

# Check input argumants, set defaults where necessaru and validate
setarg = args.setpoint
if str.isdigit(setarg[0]):
  # If first character of specified setpoint is a number, use directly
  setpoint = float(setarg)
else:
  # If first character of specified setpoint is not a number, assume it is a file path
  with open(setarg, 'r') as f:
    setpoint = float(f.readline())

hysteresis = args.hysteresis

if args.sensorid:
  # set temp_sensor(s) to specified list - handle errors later when list iterated
  temp_sensors = args.sensorid
else:
  # Find list of /sys/bus/w1/devices/28-*/w1_slave and select first
  sensor_list = glob.glob('/sys/devices/w1_bus_master1/28*/w1_slave')
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
  sys.exit()

gpio_output = args.gpioout

if args.gpiofeedback:
  gpio_feedback = args.gpiofeedback
else:
  gpio_feedback = gpio_output

logfile_fullpath = args.logfile

cycle_interval = args.interval

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
      format_print("ERROR: Cannot get current temperature from sensor "+temp_sensor+" - check 1-wire driver enabled, sensor is connected correctly and (if set) --sensorid is correct")
      current_temps[-1] = ""
  verbose_print("Current Temperatures: "+''.join(str(current_temps)))
  # If multiple sensors, note first sensor specified is always used for control
  current_temp = current_temps[0]
  if current_temp == "":
  # If error occurs on control channel it is critical error, otherwise ignore
    if cycle_interval:
      # In continuous mode, wait for next cycle and try again
      sleep(cycle_interval)
      continue
    else:
      sys.exit()

  # Compare temperature with setpoint, set heating demand signal accordingly
  # Note switch on below setpoint and off at setpoint works best for most heater controllers, since reaction to demand on tends to be faster than off
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

  # Check if one-shot mode or continuous - if interval argument is set use continuous
  if cycle_interval:
    sleep(cycle_interval)
  else:
    break

#   check all inputs have correct datatype validation and defaults
#   document outputs - log for controller_analyse (STDOUT), errors/warning (STDOUT), temperature to Excel-friendly CSV (or optional legacy message log for backwards compat)
#   testing including ALL input argument combinations (set/not set/multiple/etc) to ensure correct state set (log analysis), data logged(CSV), excel plots, multi channel, clean reboot, fresh image, etc
