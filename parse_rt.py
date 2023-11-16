import matplotlib.pyplot as plt
import numpy as np
import time

import os

lines_read_loadtester = 1
lines_read_service = 0

interval = 1.5

# each element is tuple (med, avg, 90, 95, 99)

curr_ylim = 1000

curr_ylim2 = 1000

max_rt = 7
max_service = 40

plt.ion()
fig = plt.figure()
fig.tight_layout(pad=10.0)
ax = fig.add_subplot(231)
ax2 = fig.add_subplot(2,3,(3,3))
ax3 = fig.add_subplot(2,3,(5,5))

ax.set_ylim([0, curr_ylim])
ax.set_xlabel("Time Intervals (2s)")
ax.set_ylabel("Response Time (ms)")
x = [i for i in range(max_rt)]
perf = [[0, 0, 0, 0, 0] for i in range(max_rt)]

avg_line, = ax.plot(x, [perf[i][0] for i in range(max_rt)], color='green', label='Median')
med_line, = ax.plot(x, [perf[i][1] for i in range(max_rt)], color='black', label='Avg')
p90_line, = ax.plot(x, [perf[i][2] for i in range(max_rt)], color='blue', label='p90')
p95_line, = ax.plot(x, [perf[i][3] for i in range(max_rt)], color='orange', label='p95')
target_line, = ax.plot(x, [1000 for i in range(max_rt)], color='red', linestyle='dashed')
#p99_line, = ax.plot(x, [perf[i][4] for i in range(20)], color='red', label='p99')
#ax.legend(handles=[avg_line, med_line, p90_line, p95_line, p99_line])
ax.legend(handles=[avg_line, med_line, p90_line, p95_line])
ax.set_title("Response Time Percentiles Over Time")


ax2.set_ylim([0, curr_ylim])
ax2.set_xlabel("Time Intervals (4s)")
ax2.set_ylabel("Number of Requests")
x = [i for i in range(max_service)]
dist = [[0, 0] for i in range(max_service)]
h_line, = ax2.plot(x, [e[0] for e in dist], color='blue', label='Heavyweight')
l_line, = ax2.plot(x, [e[1] for e in dist], color='red', label='Lightweight')
ax2.legend(handles=[h_line, l_line])
ax2.set_title("Number of Requests Recieved (per Interval)")

ax3.set_ylim([0, 110])
ax3.set_xlabel("Time Intervals (4s)")
ax3.set_ylabel("% of Requests")
perc = [0 for i in range (max_service)]
perc_line, = ax3.plot(x, [val for val in perc], color='black')
ax3.set_title("Percentage of Requests to Heavyweight")

while True:
  count_loadtester = 0
  
  f = open("../Res/test_parse1.csv", "r")
  
  min_point = 1000000
  max_point = 0
  data_points = []
  for line in f:
    if count_loadtester < lines_read_loadtester:
      count_loadtester += 1
      continue
    
    parts = line.split(",")
    if len(parts) < 7:
      break
      
    if parts[6] != "text":
      count_loadtester += 1
      continue
    
    try:
      data_points.append([ int(parts[0]), int(parts[1])])
      min_point = min(min_point, int(parts[1]))
      max_point = max(max_point, int(parts[1]))
    except:
      tmp = 3
      
    count_loadtester += 1
  
  f.close()
  
  os.system("sudo docker cp my_znn:/var/log/nginx/usage.csv ./usage_data.csv")
  f = open("./usage_data.csv")
  count_service = 0
  
  service_data = []
  
  for line in f:
    if count_service < lines_read_service:
      count_service += 1
      continue
    
    parts = line.split(",")
    if len(parts) < 4:
      break
    
    service_data.append([int(parts[1]), int(parts[2]), int(parts[3])])
    count_service += 1
  
  f.close()
  print(service_data)
  
  for data_part in service_data:
    dist.append([data_part[0], data_part[1]])
    perc.append(data_part[2])
  
  while len(dist) > max_service:
    dist = dist[1:]  
    perc = perc[1:]
  
  med, avg, p90, p95, p99 = 0, 0, 0, 0, 0
  if len(data_points) != 0:
    rts = [point[1] for point in data_points]
    rts.sort()
    med = rts[len(rts)//2]
    p90 = rts[int(len(rts)*0.9)]
    p95 = rts[int(len(rts)*0.95)]
    p99 = rts[int(len(rts)*0.99)]
      
    elapsed = data_points[-1][0] - data_points[0][0]
    rt_sum = 0
    for point in data_points:
      rt_sum += point[1]
    
    avg = rt_sum / len(data_points)
    
    #print(elapsed, avg, len(data_points))
    #print(min_point, max_point)
    #print(med, p90, p95, p99)
    #print(count)
    
  perf.append([med, avg, p90, p95, p99])
  
  if len(perf) > max_rt:
    perf = perf[1:]
  
  lines_read_loadtester = count_loadtester
  lines_read_service = count_service
  

  avg_line.set_ydata(np.array([e[1] for e in perf]))
  med_line.set_ydata(np.array([e[0] for e in perf]))
  p90_line.set_ydata(np.array([e[2] for e in perf]))
  p95_line.set_ydata(np.array([e[3] for e in perf]))
  
  print(len(dist), len(perc))
  h_line.set_ydata(np.array([e[0] for e in dist]))
  l_line.set_ydata(np.array([e[1] for e in dist]))
  
  perc_line.set_ydata(np.array([e for e in perc]))
  #p99_line.set_ydata(np.array([e[4] for e in perf]))
  
  #max_p99 = perf[0][4]
  #for el in perf:
  #  max_p99 = max(max_p99, el[4])
  
  max_p95 = perf[0][3]
  for el in perf:
    max_p95 = max(max_p95, el[3])
    
  max_req = max(dist[0][0], dist[0][1])
  for el in dist:
    max_req = max(max_req, el[0])
    max_req = max(max_req, el[1]) 
  
  
  if max_p95 < 0.66 * curr_ylim:
    curr_ylim = curr_ylim * 0.75
  
  if 0.9 * max_p95 > curr_ylim:
    curr_ylim = max_p95 * 1.25
    
  if max_req < 0.66 * curr_ylim2:
    curr_ylim2 = curr_ylim2 * 0.75
  
  if 0.9 * max_req > curr_ylim2:
    curr_ylim2 = max_req * 1.25
    
  ax.set_ylim([0, curr_ylim])
  ax2.set_ylim([0, curr_ylim2])
  
  fig.canvas.draw()
  fig.canvas.flush_events()
  

  time.sleep(interval)