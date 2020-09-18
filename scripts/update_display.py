#!/usr/bin/env python3

import sys

if len(sys.argv) < 3:
  print("ERROR: Specify 2 numeric arguments, first setpoint, second current temperature")
  sys.exit(1)
else:
  setpoint = format(float(sys.argv[1]), '0.4g')
  current = format(float(sys.argv[2]), '0.4g')

# *** to-do - handle errors gracefully if cannot convert to float, pad with trailing zeros/deal with issues with seg.text[5:8] over-writing initial digits;

from luma.core.interface.serial import spi, noop
from luma.core.render import canvas
from luma.core.virtual import sevensegment
from luma.led_matrix.device import max7219
import time

def do_nothing(obj):
    pass

serial = spi(port=0, device=0, gpio=noop())
device = max7219(serial, cascaded=1)
seg = sevensegment(device)

device.cleanup = do_nothing

# Top display is char 1-4 (setpoint), bottom display is digit 5-8 (current)
seg.text[1:4] = setpoint
seg.text[5:8] = current
