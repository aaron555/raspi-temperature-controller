#!/usr/bin/env python3

import sys

# Process and check input arguments
if len(sys.argv) < 3:
  print("ERROR: Specify 2 numeric arguments, first setpoint, second current temperature")
  sys.exit(1)
else:
  try:
    setpoint = format(float(sys.argv[1]), '.4g')
  except:
    print("ERROR: setpoint must be a valid number")
    sys.exit(1)
  try:
    current = format(float(sys.argv[2]), '.4g')
  except:
    print("ERROR: current temperature must be a valid number")
    sys.exit(1)

if float(setpoint) > 9999 or float(setpoint) < -999.0 or float(current) > 9999 or float(current) < -999.0:
    print("ERROR: cannot display values above 9999 or below -999")
    sys.exit(1)

# *** Note to dependencies for this script "sudo -H pip3 install --upgrade luma.led_matrix", enable SPI, add all users to SPI group, (should not need Luma LED repo?)

from luma.core.interface.serial import spi, noop
from luma.core.virtual import sevensegment
from luma.led_matrix.device import max7219

def do_nothing(obj):
    pass

# Define seven segment device
serial = spi(port=0, device=0, gpio=noop())
device = max7219(serial, cascaded=1)
seg = sevensegment(device)
# Do not switch off display on script exit
device.cleanup = do_nothing

# Append decimal pount if not present
if not "." in setpoint:
  setpoint+="."
if not "." in current:
  current+="."

# *** to-do - trim negative numbers with full 4 s.f. as these are > (4 characters + d.p.) and can cause device overflow.

# Zero pad to ensure total length 5 inc "."
# (this will perfectly fill 4 seven-segment digits)
while len(setpoint) < 5:
  setpoint+="0"
  # As long as number contains dp this won't alter value
while len(current) < 5:
  current+="0"
  # As long as number contains dp this won't alter value

# Top display is char 1-4 (setpoint), bottom display is digit 5-8 (current)
# Note writing to device with indexing only appears to work if each variable has correct number of digits
seg.text[1:4] = setpoint
seg.text[5:8] = current
