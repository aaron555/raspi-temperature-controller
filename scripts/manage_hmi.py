#!/usr/bin/env python3
import os
from luma.core.interface.serial import spi, noop
from luma.core.virtual import sevensegment
from luma.led_matrix.device import max7219
import RPi.GPIO as GPIO
from time import sleep

# *** To-do - process command line argument for config file and use <argument> instead of /etc/controller-setpoints/setpoint hardcoded

# Define seven segment device on SPI interface
serial = spi(port=0, device=0, gpio=noop())
device = max7219(serial, cascaded=1)
seg = sevensegment(device)

# Setup GPIO 23,24 for buttons - DIR: input, pulled down (HW + SW), pulled to 3V3 on button press
GPIO.setmode(GPIO.BCM)
GPIO.setup(23, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(24, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Define threaded callback functions to run when button press event occurs
def up_callback(channel):
  # *** To-do These threads should run so they fully complete before next int is handled
  print("Rising edge detected on 23 - UP+")
  # *** To-do wait to see if button pressed or held
  # Read setpoint and increment 0.5 C
  with open("/etc/controller-setpoints/setpoint", "r") as f:
    old_setpoint = float(f.readline().strip())
  new_setpoint = old_setpoint + 0.5
  # Update display
  display_setpoint = LED_value(new_setpoint)
  if display_setpoint != 99999:
    update_display(display_setpoint,"")
  # Update Stored setpoint in file for use by controller
  update_cmd = "/opt/scripts/temperature-controller/temperature_controller.sh set {}".format(new_setpoint)
  os.system(update_cmd)

def down_callback(channel):
  # *** To-do These threads should run so they fully complete before next int is handled
  print("Rising edge detected on 24 - DOWN-")
  # *** To-do wait to see if button pressed or held
  # Read setpoint and decrement 0.5 C
  with open("/etc/controller-setpoints/setpoint", "r") as f:
    old_setpoint = float(f.readline().strip())
  new_setpoint = old_setpoint - 0.5
  # Update display
  display_setpoint = LED_value(new_setpoint)
  if display_setpoint != 99999:
    update_display(display_setpoint,"")
  # Update Stored setpoint in file for use by controller
  update_cmd = "/opt/scripts/temperature-controller/temperature_controller.sh set {}".format(new_setpoint)
  os.system(update_cmd)

# Filter value for use with LED display
def LED_value(raw_value):
  try:
    # Check can be interpreted as 4 s.f. float
    processed_value = format(float(raw_value), '.4g')
  except:
    print("ERROR: setpoint must be a valid number")
    return 99999
  if float(processed_value) > 9999 or float(processed_value) < -999.0:
    print("ERROR: cannot display values above 9999 or below -999")
    return 99999
  # Append decimal pount if not present
  if not "." in processed_value:
    processed_value+="."
  # Zero pad to ensure total length 5 inc ".
  # (this will perfectly fill 4 seven-segment digits)
  while len(processed_value) < 5:
    processed_value+="0"
    # As long as number contains dp this won't alter value
  return processed_value

# Update LED display
def update_display(setpoint,current):
  seg.text = ""
  seg.text[1:4] = setpoint
  seg.text[5:8] = current
  # *** handle errors and restart script if cannot update display

GPIO.add_event_detect(23, GPIO.RISING, callback=up_callback, bouncetime=300)
GPIO.add_event_detect(24, GPIO.RISING, callback=down_callback, bouncetime=300)

while 1:
  sleep(1)

GPIO.cleanup()

# Note when this script exits display will be switched off
