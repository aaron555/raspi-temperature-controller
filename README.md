# raspi-temperature-controller
Simple binary temperature controller, based on Raspberry Pi and 1-wire hardware, with data logging

This simple temperature controller is based on low-cost and easy to build raspberry Pi hardware, with 1-wire temperature sensor(s), and outputs via relay(s) that can control and heating (or cooling) loads.  Includes description of the hardware with schematics and Bill-of-materials (BOM), including a simple example circuit that uses an LED co-located with the temperature sensor for demonstration.  The controller is flexible, capable of multi-channel operation, and stores data to a CSV logfile.  The controller can be run as a service, or periodically from cron, and when using cron it is possible to schedule setpoint changes in cron automatically.  Separate scripts are provided to control setpoint from the command line, and analyse the output from the controller to plot PNG graph of daily usage.  This is the basis of the system that has been controlling the central heating in my flat since 2014.