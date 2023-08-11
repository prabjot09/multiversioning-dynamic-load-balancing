import matplotlib.pyplot as plt
import pandas
import time

x = []
rep_h = []
rep_l = []
load = []

bar_width = 0.5
y_height1 = 0
y_height2 = 0

interval = -1
start = -1
curr = 1

f = open("./deployments.csv", "r")
for line in f:
    line = line[:-1]
    data = line.split(",")
    
    if start != -1 and interval == -1:
        h, m, s = data[0].split(":")
        now = int(h)*60*60 + int(m)*60 + int(s)
        interval = now - start
        
        if interval < 0:
            interval += 24*60*60
    
    elif start == -1:
        h, m, s = data[0].split(":")
        start = int(h)*60*60 + int(m)*60 + int(s)
        
    x.append(curr)
    curr += 1
    rep_h.append(int(data[1]))
    rep_l.append(int(data[2]))
    load.append(int(data[3]))

    y_height1 = max(y_height1, int(data[1]))
    y_height1 = max(y_height1, int(data[2]))
    y_height2 = max(y_height2, int(data[3]))
f.close()

m1_t = pandas.DataFrame({
    'heavy': rep_h,
    'light': rep_l,
    'load': load})

m1_t[['heavy', 'light']].plot(kind='bar', width=bar_width)
plt.ylabel("Replicas Deployed")
plt.ylim([0,y_height1*1.1])
plt.xlabel("Time (interval = {} seconds)".format(interval))

m1_t['load'].plot(secondary_y=True, cmap='inferno')
plt.ylabel("Maximum Concurrent Requests")
plt.ylim([0,y_height2*1.1])

ax = plt.gca()
plt.xlim([-bar_width, len(m1_t['light'])-bar_width])
ax.set_xticklabels(x, rotation = 45)

#plt.subplots_adjust(bottom=0.15)
plt.margins(0.2)
                      
#pos1 = [i for i in range(len(req_h))]
#pos2 = [pos + bar_width for pos in pos1]
                      
#plt.bar(pos1, req_h, color='b', width=bar_width, label="Heavy")
#plt.bar(pos2, req_l, color='r', width=bar_width, label="Light")
#plt.legend()
                      


#plt.xticks([n + bar_width for n in range(len(req_h))], x)


#axes2 = plt.twinx()
#axes2.set_ylim(0, 1)
#axes2.set_ylabel("Percentage Heavy")

plt.show()



