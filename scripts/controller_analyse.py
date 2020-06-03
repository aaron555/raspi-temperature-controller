#!/usr/bin/env python3

# Analyse temperature controller log-files produced by control_temp.py

# Syntax: ./controller_analyse.py [<full filename and path of log> <start time> <end time> <output directory>]

# All arguments are optional
# If <full filename and path of log> is not specified default /var/log/control_temp.log
# If <start time> is not specified default [midnight at end of day on which first switching event occurs]
# If <end time> is not specified default [midnight at start of last day in log]
# If <output directory> is outputs will be written to directory from which script is run

# Note start and end times MUST be either a string in the form YYYY-MM-DD or an integer unix timestamp
# Invalid start or end times will be ignored (default of all available data used)
# Note if the end date is later than end of log, it will be assumed system status is held from end of log to requested end

# Outputs: CSV file with amount of time system on (in hours and %) for each day
# Plot and bar chart of hours on each day

# Changelog
# 2015 - First Version
# 19/04/2020 - Fixed bug with analysis of days after log ends, changed CSV to 2 d.p., added python3 compatibility

# Copyright (C) 2015, 2020 Aaron Lockton

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

print("Importing modules...")

import time
from time import gmtime, strftime
import os
import sys
import calendar
from matplotlib.dates import date2num, DAILY
import datetime as DT
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

print(strftime("%Y-%m-%d-%H:%M:%S: Starting temperature controller log analysis", gmtime()))
# Set defaults
if len(sys.argv) < 2:
  log_file = "/var/log/control_temp.log"
else:
  log_file = sys.argv[1]
  if os.path.isfile(log_file) != 1:
    print("WARNING: Cannot find log file specified - using default")
    log_file = "/var/log/control_temp.log"

if len(sys.argv) < 3:
  requested_start = 0
else:
  requested_start_raw = sys.argv[2]
  if str.isdigit(requested_start_raw):
    requested_start = int(requested_start_raw)
  else:
    try:
      requested_start = calendar.timegm(time.strptime(requested_start_raw, "%Y-%m-%d"))
    except ValueError:
      print("WARNING: Invalid start date specified - using default (all available data)")
      requested_start = 0
#print(strftime("%Y-%m-%d-%H:%M:%S", gmtime(requested_start)))

# Read in log file
print("Analysing log file:  %s" % log_file)
with open(log_file, "r") as f:
  raw_log = list(f)

# Find first switch in log (and hence earliest start time) and  end time of log
start_time=None
for line in raw_log:
  if "Switching system" in line:
    start_time = calendar.timegm(time.strptime(line[0:10], "%Y-%m-%d")) + 86400
    break
end_time = calendar.timegm(time.strptime(raw_log[-1][0:10], "%Y-%m-%d"))
if not start_time or not end_time:
  print("ERROR: logfile does not appear to contain at least one valid switch on and switch off event" )
  sys.exit(1)
print("Log file covers %s to %s" % (raw_log[0][0:19], raw_log[-1][0:19]))
print("Log file can be analysed from from %s to %s" % (strftime("%Y-%m-%d_%H:%M:%S", gmtime(start_time)), strftime("%Y-%m-%d-%H:%M:%S", gmtime(end_time))))
num_days = int((end_time - start_time) / 86400)
if num_days < 1:
  print("ERROR: logfile contains insufficient data - require at least one full day of data, including two midnight crossings at start and end" )
  sys.exit(1)
end_time_log = end_time
print("Total %s log lines, %d full days in log" % (len(raw_log), num_days))

# Check requested end time, and set default
if len(sys.argv) < 4:
  requested_end = end_time
else:
  requested_end_raw = sys.argv[3]
  if str.isdigit(requested_end_raw):
    requested_end = int(requested_end_raw)
  else:
    try:
      requested_end = calendar.timegm(time.strptime(requested_end_raw, "%Y-%m-%d"))
    except ValueError:
      print("WARNING: Invalid end date specified - using default (all available data)")
      requested_end = end_time
#print(strftime("%Y-%m-%d-%H:%M:%S", gmtime(requested_end)))

# Check if output directory is specified
if len(sys.argv) < 5:
  output_dir=""
else:
  output_dir = sys.argv[4]
  # Ensure logfile path ends with a trailing slash
  if output_dir[-1] != "/":
    output_dir = output_dir + "/"

# Determine if shorter timescale for analysis has been specified
if requested_start > start_time and requested_start < end_time:
  start_time = calendar.timegm(time.strptime(strftime("%Y-%m-%d", gmtime(requested_start)), "%Y-%m-%d"))
print("Analysis start date %s" % strftime("%Y-%m-%d_%H:%M:%S", gmtime(start_time)))
if requested_end > start_time:
  end_time = calendar.timegm(time.strptime(strftime("%Y-%m-%d", gmtime(requested_end)), "%Y-%m-%d"))
print("Analysis end date %s" % strftime("%Y-%m-%d_%H:%M:%S", gmtime(end_time)))

# Create list of datestamps of days being analysed
num_days_log = num_days
num_days = int((end_time - start_time) / 86400)
print("Analysing %d full days" % (num_days))
if end_time > end_time_log:
  print("WARNING: Requested analysis period ends after last log line - assuming no changes in status between these times")
current_day = start_time
datestamps = []
timestamps = []
for ii in range(0, num_days):
  # print(ii,strftime("%Y-%m-%d-%H:%M:%S", gmtime(current_day)))
  datestamps.append(strftime("%Y%m%d", gmtime(current_day)))
  timestamps.append(current_day)
  current_day += 86400
datestamps_extra = datestamps[:]
datestamps_extra.append(strftime("%Y%m%d", gmtime(current_day)))
timestamps.append(current_day)
# datestamps: list of every day analysed (string)
# timestamps: list of day boundary of every day analysed-including start and end (unix timestamp)
# datestamps_extra-list of every day boundary-including start and end (string)
# print(datestamps, datestamps_extra, timestamps[0], len(timestamps))

# Create status list, showing status at midnight every day
status_list = []
current_status = -1
for line in datestamps_extra:
  status_list.append("-1")
prev_time = calendar.timegm(time.strptime(raw_log[0][0:10], "%Y-%m-%d"))
for line in raw_log:
  try:
    line_time = calendar.timegm(time.strptime(line[0:19], "%Y-%m-%d-%H:%M:%S"))
  except ValueError:
    try:
      line_time = calendar.timegm(time.strptime(line[0:19], "%Y-%m-%d-%H-%M-%S"))
    except ValueError:
      # Line does not contain valid data - ignore it
      # print("Invalid line:  %s" % repr(line))
      continue
  line_day = strftime("%Y%m%d", gmtime(line_time))
  if line_day != strftime("%Y%m%d", gmtime(prev_time)):
    # Day rollower has occurred
    if line_time > start_time and prev_time < start_time:
      status_start_analysis = current_status
      #print(status_start_analysis)
    try:
      start_day_index = datestamps_extra.index(strftime("%Y%m%d", gmtime(prev_time+86400)))
      end_day_index = datestamps_extra.index(line_day)
      for ii in range(start_day_index,end_day_index+1):
        status_list[ii] = current_status
    except ValueError:
      pass
      # print(strftime("%Y%m%d", gmtime(prev_time+86400)), line_day)
  if "Switching system on" in line:
    current_status = 1
  if "Switching system off" in line:
    current_status = 0
  prev_time = line_time
# If last day(s) in analysis have no data in log, pad with last known status
indices = [jj for jj, s in enumerate(raw_log) if 'Switching system' in s]
last_status_change_line = raw_log[indices[-1]]
if "Switching system on" in last_status_change_line:
  status_end_analysis = 1
elif "Switching system off" in last_status_change_line:
  status_end_analysis = 0
else:
  print("ERROR: invalid last switching line: " + last_status_change_line)
  sys.exit(1)
if status_list[-1] == "-1":
  index = ii+1
  for line in status_list[ii+1:]:
    status_list[index] = status_end_analysis
    index += 1
# # If first day(s) in analysis have no data in log, pad with known start status
# first_status_change_line = raw_log[indices[0]]
# # Inverted logic here - if first line is switching on, then assume off in all time before log
# if "Switching system on" in first_status_change_line:
#   status_start_analysis = 0
# elif "Switching system off" in first_status_change_line:
#   status_start_analysis = 1
# else:
#   print("ERROR: invalid first switching line: " + first_status_change_line)
#   sys.exit(1)
# if status_list[0] == "-1":
#   index = 0
#   for line in status_list:
#     if line == "-1":
#       status_list[index] = status_start_analysis
#     else:
#       break
#     index += 1
# print(status_list)

# Step through days, reading log lines and calculating time on each day
counter = 0
time_on = []
for line in datestamps:
  todays_lines = [s for s in raw_log if (line[0:4]+"-"+line[4:6]+"-"+line[6:8]) in s]
  #print(line,todays_lines,line[0:4]+"-"+line[4:6]+"-"+line[6:8])
  if todays_lines:
    current_status = status_list[counter]
    todays_total = 0
    if current_status == 1:
      last_on = timestamps[counter]
    for line in todays_lines:
      try:
        line_time = calendar.timegm(time.strptime(line[0:19], "%Y-%m-%d-%H:%M:%S"))
      except ValueError:
        try:
          line_time = calendar.timegm(time.strptime(line[0:19], "%Y-%m-%d-%H-%M-%S"))
        except ValueError:
          # Line does not contain valid data - ignore it
          continue
      if "Switching system on" in line and current_status == 0:
        current_status = 1
        last_on = line_time
      if "Switching system off" in line and current_status == 1:
        current_status = 0
        todays_total += line_time - last_on
    if current_status != status_list[counter+1]:
      print("ERROR! inconsistency between status from log lines and expected midnight status!")
      print(current_status, status_list[counter+1], last_on, todays_total)
    if current_status == 1:
      todays_total += timestamps[counter+1] - last_on
    time_on.append(todays_total)
  else:
    # If no data, status for entire day same as at start of day
    time_on.append(status_list[counter] * 86400)
  counter += 1
#print(datestamps,time_on)
time_on_hours = [float(x)/3600 for x in time_on]
duty_cycle = [float(x)/864 for x in time_on]

# Summary
summary_string = "Total of %.1f hours on in %d days (mean %.2f hours/day)" %(sum(time_on_hours), num_days, sum(time_on_hours)/num_days)
print(summary_string)
max_hours = max(time_on_hours)
max_index = time_on_hours.index(max_hours)
print("Max %.1f hours in a day (on %s) and min %.1f hours in a day" %(max_hours, datestamps[max_index], min(time_on_hours)))
file_timestamp = output_dir + strftime("%Y%m%d_%H%M%S", gmtime())
data_filename = file_timestamp + "_controller_analysis.csv"
print("Saving csv of results to %s" %data_filename)
with open(data_filename, "w") as f:
  counter = 0
  f.write("Standard Date,Date,Time ON (hours),Time ON (%)\n")
  for line in datestamps:
    f.write("%s,%s/%s/%s,%s,%s\n" %(line, line[6:8],line[4:6],line[0:4], "{:.2f}".format(time_on_hours[counter]), "{:.2f}".format(duty_cycle[counter])))
    counter += 1
print("Saving plots of results")

# Create datenums for date ticks on plots
DT_datestamps = [DT.datetime.strptime(x, "%Y%m%d") for x in datestamps]
datenums = [date2num(x) for x in DT_datestamps]

# Plot hours on bar chart
fig, ax = plt.subplots(1)
plt.bar(datenums, time_on_hours)
ax.xaxis_date()
loc = ax.xaxis.get_major_locator()
loc.maxticks[DAILY] = 12
plt.title(summary_string)
plt.ylabel('Time ON each day (hours)')
fig = matplotlib.pyplot.gcf()
fig.set_size_inches(8,6)
fig.autofmt_xdate(bottom=0.15)
dateFmt = matplotlib.dates.DateFormatter('%Y-%m-%d')
ax.xaxis.set_major_formatter(dateFmt)
plt.savefig(file_timestamp+"_controller_log_plot_bar.png", format='png', dpi=300)

# Plotting on chart
plt.close('all')
fig, ax = plt.subplots(1)
plt.plot_date(datenums,time_on_hours, 'r-o')
loc = ax.xaxis.get_major_locator()
loc.maxticks[DAILY] = 12
plt.title(summary_string)
plt.ylabel('Time ON each day (hours)')
fig.autofmt_xdate(bottom=0.15)
dateFmt = matplotlib.dates.DateFormatter('%Y-%m-%d')
ax.xaxis.set_major_formatter(dateFmt)
plt.savefig(file_timestamp+"_controller_log_plot.png", format='png', dpi=300)

print(strftime("%Y-%m-%d-%H:%M:%S: Completed temperature controller log analysis", gmtime()))
