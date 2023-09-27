import matplotlib.pyplot as plt
import numpy as np
import time

lines_read = 1

interval = 5

# each element is tuple (med, avg, 90, 95, 99)
perf = [[0, 0, 0, 0, 0] for i in range(20)]

curr_ylim = 1000

plt.ion()
fig = plt.figure()
ax = fig.add_subplot(111)
ax.set_ylim([0, curr_ylim])
x = [i for i in range(20)]
avg_line, = ax.plot(x, [perf[i][0] for i in range(20)], color='green', label='Median')
med_line, = ax.plot(x, [perf[i][1] for i in range(20)], color='black', label='Avg')
p90_line, = ax.plot(x, [perf[i][2] for i in range(20)], color='blue', label='p90')
p95_line, = ax.plot(x, [perf[i][3] for i in range(20)], color='orange', label='p95')
target_line, = ax.plot(x, [1000 for i in range(20)], color='red', linestyle='dashed')
#p99_line, = ax.plot(x, [perf[i][4] for i in range(20)], color='red', label='p99')
#ax.legend(handles=[avg_line, med_line, p90_line, p95_line, p99_line])
ax.legend(handles=[avg_line, med_line, p90_line, p95_line])
ax.set_title("Response Time Percentiles Over Time")



while True:
  count = 0
  
  f = open("../Res/test_parse1.csv", "r")
  
  min_point = 1000000
  max_point = 0
  data_points = []
  for line in f:
    if count < lines_read:
      count += 1
      continue
    
    parts = line.split(",")
    if len(parts) < 7:
      break
      
    if parts[6] != "text":
      count += 1
      continue
    
    try:
      data_points.append([ int(parts[0]), int(parts[1])])
      min_point = min(min_point, int(parts[1]))
      max_point = max(max_point, int(parts[1]))
    except:
      tmp = 3
      
    count += 1
  
  f.close()
  
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
  
  if len(perf) > 20:
    perf = perf[1:]
  
  lines_read = count
  

  avg_line.set_ydata(np.array([e[1] for e in perf]))
  med_line.set_ydata(np.array([e[0] for e in perf]))
  p90_line.set_ydata(np.array([e[2] for e in perf]))
  p95_line.set_ydata(np.array([e[3] for e in perf]))
  #p99_line.set_ydata(np.array([e[4] for e in perf]))
  
  #max_p99 = perf[0][4]
  #for el in perf:
  #  max_p99 = max(max_p99, el[4])
  
  max_p95 = perf[0][3]
  for el in perf:
    max_p95 = max(max_p95, el[3])
  
  
  if max_p95 < 0.66 * curr_ylim:
    curr_ylim = curr_ylim * 0.75
  
  if max_p95 > curr_ylim:
    curr_ylim = max_p95 * 1.25
    
  ax.set_ylim([0, curr_ylim])
  
  fig.canvas.draw()
  fig.canvas.flush_events()
  

  time.sleep(interval)