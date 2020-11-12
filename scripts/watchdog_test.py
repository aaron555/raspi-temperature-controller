#!/usr/bin/env python3

# Proof-of-concept to monitor actual and setpoint files for changes - not used in final controller

import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime, timedelta
#import subprocess

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
          print("New Setpoint/actual")

if __name__ == "__main__":
    setpoint_handler = Handler("/etc/controller-setpoints/setpoint")
    actual_handler = Handler("/tmp/temperature-controller-latest")
    setpoint_observer = Observer()
    actual_observer = Observer()
    setpoint_observer.schedule(setpoint_handler, path='/etc/controller-setpoints/', recursive=False)
    actual_observer.schedule(actual_handler, path='/tmp/', recursive=False)
    setpoint_observer.start()
    actual_observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        setpoint_observer.stop()
        actual_observer.stop()
    setpoint_observer.join()
    actual_observer.join()
