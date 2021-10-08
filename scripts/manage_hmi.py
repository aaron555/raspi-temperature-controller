#!/usr/bin/env python3
import os
from luma.core.interface.serial import spi, noop
from luma.core.virtual import sevensegment
from luma.led_matrix.device import max7219
import RPi.GPIO as GPIO
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime, timedelta

# *** To-do - process command line argument for config file and use <argument> instead of /etc/controller-setpoints/setpoint hardcoded + check all hardcoded paths!

GPIO_UP=23
GPIO_DOWN=24
# Temperature to reset to if both buttons pressed
RESET_TEMP=25

## LED DISPLAY AND BUTTONS

# Define seven segment device on SPI interface
serial = spi(port=0, device=0, gpio=noop())
device = max7219(serial, cascaded=1)
seg = sevensegment(device)

# Setup GPIO for up,down buttons - DIR: input, pulled down (HW + SW), pulled to 3V3 on button press
GPIO.setmode(GPIO.BCM)
GPIO.setup(GPIO_UP, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(GPIO_DOWN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Define threaded callback functions to run when button press event occurs
def button_callback(channel):
  # *** To-do These threads should run so they fully complete before next int is handled - ignore both buttons during this time - note this currently defeats both buttons to reset
  # *** To-do - pause observers to prevent multiple display updates, and observer interrupting while button held
  print("DEBUG: Rising edge detected on GPIO "+str(channel))
  print(GPIO.input(GPIO_UP),GPIO.input(GPIO_DOWN))
  if GPIO.input(GPIO_UP) == 1 and GPIO.input(GPIO_DOWN) == 1:
    # Reset temperature if both buttons pressed
    new_setpoint = RESET_TEMP
    display_setpoint = LED_value(new_setpoint)
    if display_setpoint != 99999:
      update_display(display_setpoint,"")
  else:
    # Handle UP or DOWN request if single button pressed
    if channel == GPIO_UP:
      GPIO_PUSHED = GPIO_UP
      TEMP_INC = 0.5
    elif channel == GPIO_DOWN:
      GPIO_PUSHED = GPIO_DOWN
      TEMP_INC = -0.5
    else:
      # Should never get to this case
      return None
    with open("/etc/controller-setpoints/setpoint", "r") as f:
      old_setpoint = float(f.readline().strip())
      new_setpoint = old_setpoint + TEMP_INC
      display_setpoint = LED_value(new_setpoint)
      if display_setpoint != 99999:
        update_display(display_setpoint,"")
    # Check if button held
    if GPIO.input(GPIO_PUSHED) == 1:
      while GPIO.input(GPIO_PUSHED) == 1 and new_setpoint <= 9999 and new_setpoint >= -999:
        time.sleep(0.5)
        if GPIO.input(GPIO_PUSHED) == 1:
          # Button held foe 0.5 s - keep incrementing
          new_setpoint = new_setpoint + TEMP_INC
          display_setpoint = LED_value(new_setpoint)
          if display_setpoint != 99999:
            update_display(display_setpoint,"")

  # Update Stored setpoint in file for use by controller
  update_cmd = "/opt/scripts/temperature-controller/temperature_controller.sh set {}".format(new_setpoint)
  # *** BUG - ensure multiple button presses are handled correctly - probably need to handle multiple button presses together - sometimes setpoint in file can differ from controller value after multiple presses / controller restarts
  os.system(update_cmd)
  # *** To-do - restart observers after completion of task here

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
  #print(processed_value)
  return processed_value

# Update LED display - optional arguments to specify setpoint and current (actual), else reads from files
def update_display(setpoint,current):
  print("DEBUG: Update display called - args: "+setpoint+current)
  # Use setpoint from filesystem if not specified
  if setpoint == "":
    try:
      with open("/etc/controller-setpoints/setpoint", "r") as f:
        setpoint=f.readline()
      # *** Note this sometimes reads empty setpoint causing error in LED_value - seems mainly if setpoint changed from command line (NOT buttons)
      print("DEBUG: Read setpoint: "+setpoint)
      display_setpoint = LED_value(setpoint)
      if display_setpoint != 99999:
        setpoint = display_setpoint
    except:
      setpoint = ""
  # Use current from filesystem if not specified
  if current == "":
    try:
      with open("/tmp/temperature-controller-latest", "r") as f:
        current=f.readline()
      print("DEBUG: Read actual: "+current)
      display_currrent = LED_value(current)
      if display_currrent != 99999:
        current = display_currrent
    except:
      current = ""
  # Write values to display
  seg.text = ""
  print(setpoint,current)
  seg.text[1:4] = setpoint
  seg.text[5:8] = current
  # *** handle errors and restart script if cannot update display

## MONITOR LATEST SETPOINT AND ACTUAL STORED ON DISK
class Handler(FileSystemEventHandler):
  def __init__(self, path):
    self.last_modified = datetime.now()
    super().__init__()
    self.path = path

  def on_modified(self, event):
    if event.is_directory:
      return None
    elif datetime.now() - self.last_modified < timedelta(seconds=1):
      return None
    else:
      self.last_modified = datetime.now()
      if event.src_path == self.path:
        # Note observer triggers on file change, and often reacts before file is updated and closed leading to empty read, hence wait 0.1 s
        time.sleep(0.1)
        update_display("","")

if __name__ == "__main__":
  # Setup monitoring of files storing actual and setpoint
  setpoint_handler = Handler("/etc/controller-setpoints/setpoint")
  actual_handler = Handler("/tmp/temperature-controller-latest")
  setpoint_observer = Observer()
  actual_observer = Observer()
  setpoint_observer.schedule(setpoint_handler, path='/etc/controller-setpoints/', recursive=False)
  actual_observer.schedule(actual_handler, path='/tmp/', recursive=False)

  # Start by updating display - note can display welcome message here and wait to complete before enabling functionality
  update_display("","")

  # Start monintoring actual and setpoint files
  setpoint_observer.start()
  actual_observer.start()

  # Setup monitoring of buttons
  GPIO.add_event_detect(GPIO_UP, GPIO.RISING, callback=button_callback, bouncetime=300)
  GPIO.add_event_detect(GPIO_DOWN, GPIO.RISING, callback=button_callback, bouncetime=300)

  try:
    while True:
      time.sleep(1)
  # Or SIGINT, SIGHUP, etc...
  except KeyboardInterrupt:
    setpoint_observer.stop()
    actual_observer.stop()
  # Cleanup
  setpoint_observer.join()
  actual_observer.join()
  GPIO.cleanup()

# Note when this script exits display will be switched off