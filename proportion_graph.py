import matplotlib.pyplot as plt
import pandas

x = []
req_h = []
req_l = []
proportion = []

bar_width = 0.5
y_height = 0

f = open("/var/log/nginx/usage.csv", "r")
interval = -1
start = -1
curr = 1

for line in f:
    line = line[:-1]
    data = line.split(",")
    
    if len(data) == 1:
        continue
  
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
    req_h.append(int(data[1]))
    req_l.append(int(data[2]))
    proportion.append(float(data[3]) / 100)

    y_height = max(y_height, int(data[1]))
    y_height = max(y_height, int(data[2]))
f.close()

m1_t = pandas.DataFrame({
    'heavy': req_h,
    'light': req_l,
    'proportion': proportion})

m1_t[['heavy', 'light']].plot(kind='bar', width=bar_width)
plt.ylabel("Requests Recieved")
plt.ylim([0,int(y_height*1.2)])
plt.xlabel("Time (interval = {} seconds)".format(interval))
m1_t['proportion'].plot(secondary_y=True, cmap='inferno')
plt.ylabel("% Sent to Heavy Version")
plt.ylim([0,1.2])

ax = plt.gca()
plt.xlim([-bar_width, len(m1_t['light'])-bar_width])
ax.set_xticklabels(x)
                      
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
    


