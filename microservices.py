import sys
import socket
import docker
import requests
import threading
from time import time, localtime, sleep

# Linked List Node Objects
class ListNode:
    def __init__(self, val=-1):
        self.val = val
        self.next = None
        self.prev = None
        
    def __str__(self):
        return "({})".format(self.val)

'''
 Linked List Class
 - Maintains a certain maximum size n
 - Records the recent history of a value across past n time intervals.
 - Order: Most recent to oldest.
'''
class IntLinkedList:
    def __init__(self, max_len):
        self.size = 0
        self.count = 0
        self.max_len = max_len
        self.head = None
        self.tail = None
    
    def add(self, on):
        node = ListNode(val=on)
        if self.size == 0:
            self.size += 1
            self.count += on
            self.head = node
            self.tail = node
        
        elif self.size < self.max_len:
            node.next = self.head
            self.head.prev = node
            self.head = node
            self.size += 1
            self.count += on
       
        else:
            node.next = self.head
            self.head.prev = node
            self.head = node
            self.count += (on - self.tail.val)
            self.tail.prev.next = None
            self.tail = self.tail.prev
    
    def __str__(self):
        curr = self.head
        res = ""
        while curr != None:
            res += str(curr)
            if curr.next != None:
                res += "->"
            curr = curr.next
                
        return res

'''
Service Version Description Class
 - Stores information common across all instances of a service
 - image: The Docker image of this version
 - env: Environment variables to launch a container of this version
 - resources: How many resources allocated to each instance of this version
 - innerPort: The port inside the container listening to requests.
'''
class VersionDefinition:    
    def __init__(self, image, env, resources, port):
        self.image = image        
        self.env = env
        self.resources = resources
        self.innerPort = port
   
    def __str__(self):
        res = ""
        res += "image: " + self.image + "\n"
        res += "env: " + str(self.env) + "\n"
        res += "resources: " + str(self.resources) + "\n"
        return res 


'''
User-defined Configuration for the service as a whole

- heavy_description: Stores the VersionDefinition object of HW version.
- light_description: Stores the VersionDefinition object of LW version.
- pt: Performance SLA (desired maximum response time - milliseconds)
- max_replicas: Maximum number of total instances allowed to be deployed. 

- scale_up: Linked List recording history of scaling outs. Where 1 indicated that service wanted to scale out during that interval, and 0 indicates opposite.
- scale_down: Linked List recording history of scaling outs. Where 1 indicated that service wanted to scale in during that interval, and 0 indicated opposite.
Note: No difference between scale_down6 and scale_down24 (their specific functions were removed)
'''
class Configuration:
    network = None
    
    def __init__(self, pt, max_replicas, heavy=None, light=None):
        self.pt = pt
        self.max_replicas = max_replicas
        self.heavy_description = heavy
        self.light_description = light
        
        self.scale_up = IntLinkedList(2)
        self.scale_down24 = IntLinkedList(24)
        self.scale_down6 = IntLinkedList(6)
    
    def applyScalingData(self, scaleUp, scaleDown):
        up_on, down_on = (0, 0)
        if scaleUp == 1:
            up_on = 1
        elif scaleDown == 1:
            down_on = 1
            
        self.scale_up.add(up_on)
        self.scale_down24.add(down_on)
        self.scale_down6.add(down_on)
        print("{}\n{}\n{}\n".format(self.scale_up, self.scale_down24, self.scale_down6))
        
        # [Subject to Change]
        # Logic: Wait 2 intervals before being sure to scale out.
        #        Wait 3 intervals before being sure to scale in.
        doUpscale, doDownscale = (False, False)
        if self.scale_up.count == 2:
            doUpscale = True
        elif self.scale_down6.count == 3:
            doDownscale = True
        
        return {"upscale": doUpscale, "downscale": doDownscale}
        
    
    # Records a scaling up decision
    def applyUpscale(self):
        self.scale_up = IntLinkedList(2)
    
    # Records a scaling in decision
    def applyDownscale(self):
        for i in range(6):
            self.scale_down6.add(0)
            self.scale_down24.add(0)
            
    def __str__(self):
        res = ""
        res += "pt={}, max={}\n".format(self.pt, self.max_replicas)
        res += "heavy={}\nlight={}\n".format(str(self.heavy_description), str(self.light_description))
        return res
        
        
'''
Represents a running container (aka server)

- ip, port: Forms the address of the container
- container: Docker container object. Can be used to start, stop, modify the container.
- capacity_h: The ideal maximum number of users this heavyweight container can serve simultaneously while maintaining SLA.
- capacity_l: Same as capacity_h, but records capacity when this server is lightweight.

'''
class ServerDescription:
    def __init__(self, ip, port, container, c_h=0.0, c_l=0.0, isHeavy=True):
        self.ip = ip
        self.port = port
        self.container = container
        self.capacity_h = c_h
        self.capacity_l = c_l
        self.isHeavy = isHeavy
    
    # The reduction of servicable concurrent users if this container is scaled in.
    #     If container is heavyweight - The loss of shutting down this container.
    #     If container is lightweight - The loss of turning this server into a heavyweight.
    def capacityDelta(self):
        if self.isHeavy:
            return self.capacity_h
        
        return self.capacity_l - self.capacity_h
        
        
    # Stop the container and remove it.    
    def shutdown(self):
        self.container.stop()
        self.container.remove()
        print("Container Terminated: {}".format(str(self)))
        
    
    def __str__(self):
        res = ""
        res += "{}:{}->{}\t capacityH: {}\t capacityL: {}\t isHeavy: {}\n".format(self.ip, self.port, self.container.id, self.capacity_h, self.capacity_l, self.isHeavy)
        return res


'''
Represents the state of the whole microservice.

- heavy: A list of the heavyweight containers deployed
- light: A list of the lightweight containers deployed
- load_history: Records the load on the service during the past 2 time intervals.
'''
class System:

    # Log File: Records timestamped configurations of heavyweight and lightweight containers 
    data_file = "./deployments.csv"

    def __init__(self, heavy=[], light=[]):
        self.heavy = heavy
        self.light = light
        self.load_history = []
    
    
    # Builds an object that includes all necessary information to build the NGINX configuration file.
    # - Records the address and version of each running container as well as the performance target (pt)
    def buildConfigData(self, pt):
        servers = []
        for s in self.heavy:
            s_config = {
                "server": s.ip,
                "port": s.port,
                "type": "heavy"
            }
            servers.append(s_config)
       
        for s in self.light:
            s_config = {
                "server": s.ip,
                "port": s.port,
                "type": "light"
            }
            servers.append(s_config)
        
        servers[0]["pt"] = pt
        return servers
    
    
    # Wipes the records in microservice log file
    def clearLogs(self):
        f = open(self.data_file, "w")
        f.write("")
        f.close()
        return
    
    
    # Logs the current time and the current configuration of lightweight/heavyweight instances.
    def logDeployments(self, load):
        f = open(self.data_file, "a")
        
        now = localtime(time())
        h, m, s = now.tm_hour, now.tm_min, now.tm_sec
        
        data = "{:02d}:{:02d}:{:02d},{},{},{}\n".format(h, m, s, len(self.heavy), len(self.light), load)
        f.write(data)
        f.close()
        return
        
    
    # Finds an unused port on this device
    def getFreePort(self):
        sock = socket.socket()
        sock.bind(('', 0))
        port = sock.getsockname()[1]
        sock.close()
        return port
        
    '''
    Makes the decision to scale in/out using 'data' parameter
    
    Parameters
    - data: The data recieved from the 'Monitor Server'
        Format: 
        {
          "conc_requests": (int - # concurrent requests on microservice currently),
          "total_capacity": (int - # concurrent requests that can be handled by microservice without violating SLA),
          "servers": [
              { "ip": (string - IP address), "port": (int - port #), "capacity": (float - capacity of this container/server) },
              ...
              ... (One object for each container) 
          ],
        }
    - config: The Configuration object.
    - pt: The performnace target
    
    Return Value: (upscale, downscale, server)
    - upscale: 1 if scale-out, 0 otherwise
    - downscale: 1 if scale-in, 0 otherwise
    - server: The server/container that needs to be changed (if any)
    '''
    def calculateScaling(self, data, config, pt):
        max_scale = config.max_replicas
        load = data["conc_requests"]
        capacity = data["total_capacity"]
        
        # Record current load
        self.load_history.append(load)
        if len(self.load_history) > 2:
          self.load_history = self.load_history[1:]
        
        # Predict future load from previous 2 time intervals
        predict_load = self.load_history[0]
        if len(self.load_history) == 2:
          predict_load = (predict_load + self.load_history[1]) / 2
        
        # Service rate of requests per second
        completion_rate = capacity * (1000 / pt)
        
        # Parse 'data'
        servers = dict()
        for server in data["servers"]:
            key = "{}:{}".format(server["ip"], server["port"])
            servers[key] = float(server["capacity"])
            
        
        self.updateCapacities(servers)
        delta, deltaServer = self.getMinDownscaleDelta(pt)
        
        # Default Return Value
        upscale, downscale, server = (0, 0, None)
        
        # Condition: Do we need to scale out?
        if (predict_load > 0.9 * capacity) and len(self.light) < max_scale:  
            upscale = 1
            # Condition: Do we scale out by switching from heavy to lightweight?
            if len(self.heavy) + len(self.light) == max_scale: 
                for h in self.heavy:
                    if server == None or h.capacity_h < server.capacity_h:
                        server = h
                        
        # Condition: Do we need to scale in?
        elif (predict_load == 0 or predict_load < 0.9 * (capacity - delta)) and (len(self.heavy) > 1 or len(self.light) > 0): 
            downscale = 1
            server = deltaServer
        
        return (upscale, downscale, server)
            
    
    # Updates the capacities of ServerDescription objects for each container
    # 
    # Parameters
    # - servers: The most recent data from NGINX.
    def updateCapacities(self, servers):
        for h in self.heavy:
            key = "{}:{}".format(h.ip, h.port)
            if servers.get(key) != None:
                h.capacity_h = servers.get(key)
                
        for l in self.light:
            key = "{}:{}".format(l.ip, l.port)
            if servers.get(key) != None:
                l.capacity_l = servers.get(key)
        
        return
        
    
    '''
    Calculates the minimum loss in capacity for scaling in.
    
    Parameters
    - pt : The performance target
    
    Return Value: (min_delta, server)
    - min_delta: Loss in capacity for scaling in.
    - server: The server that is the target for scaling in.
    '''
    def getMinDownscaleDelta(self, pt):
        min_delta = -1
        server = None
        
        # Logic:
        # First try to scale-in the lightweight instances. 
        # If there are no lightweight instances, scale-in the heavyweight instances.
        
        if len(self.light) > 0:
            for l in self.light:
                if min_delta == -1 or l.capacityDelta() < min_delta:
                    min_delta = l.capacityDelta()
                    server = l
        
        elif len(self.heavy) > 0:
            for h in self.heavy:
                if min_delta == -1 or h.capacityDelta() < min_delta:
                    min_delta = h.capacity_h
                    server = h
        
        return (min_delta, server)
        
    
    '''    
    Scale out the microservice
    
    Parameters:
    - config: The Configuration object.
    - server: The container that we want to scale-out to lightweight. If None, then just launch a new heavy-weight instance.
    - dockerCli: The Docker Client used to run Docker commands
    - lbClient: LoadBalancerClient object. Used to send requests to NGINX to update the configuration after scaling.
    '''     
    def upscale(self, config, server, dockerCli, lbClient):
        # Logic:
        # If we haven't maxed out # replicas yet, then launch a new heavyweight container
        # Otherwise, we switch a heavyweight container to lightweight.
        
        if server == None:
            print("Launching new container")
            h_desc = config.heavy_description
            tmpPort = self.getFreePort()
            
            new_container = dockerCli.containers.run(h_desc.image, detach=True, ports={h_desc.innerPort:tmpPort},
                environment=h_desc.env, network=config.network, 
                nano_cpus=(int(1000000000*h_desc.resources["cpu"])),
                mem_limit=h_desc.resources["mem"], 
                memswap_limit=h_desc.resources["swap"])
            
            new_server = ServerDescription(self.heavy[0].ip, tmpPort, new_container)
            self.heavy.append(new_server)
            
            # Update the NGINX configuration after 10 seconds to allow container slow start-up.
            def delayed_post(lbClient, data, server): 
                sleep(10)
                lbClient.POST_configData(data)
                
            post_thread = threading.Thread(target=delayed_post, args=(lbClient, self.buildConfigData(config.pt), new_server))
            post_thread.start()
            config.applyUpscale()
            
        else:
            print("Scaling-out container {}, heavy->light".format(server.container.id))
            l_desc = config.light_description
            tmpPort = self.getFreePort()
            
            new_container = dockerCli.containers.run(l_desc.image, detach=True, ports={l_desc.innerPort:tmpPort},
                environment=l_desc.env, network=config.network, 
                nano_cpus=(int(1000000000*l_desc.resources["cpu"])),
                mem_limit=l_desc.resources["mem"], 
                memswap_limit=l_desc.resources["swap"])
            
            new_server = ServerDescription(server.ip, tmpPort, new_container)
            new_server.capacity_h = server.capacity_h
            new_server.isHeavy = False
            
            self.light.append(new_server)
            self.heavy.remove(server)
            
            # Update the NGINX configuration after 10 seconds to allow container slow start-up
            def delayed_post(lbClient, data, server): 
                sleep(10)
                lbClient.POST_configData(data)
            
            post_thread = threading.Thread(target=delayed_post, args=(lbClient, self.buildConfigData(config.pt), new_server))
            post_thread.start()
            
            # Stop the old heavyweight container
            stop = lambda server : server.shutdown()
            stop_thread = threading.Thread(target=stop, args=(server,))
            stop_thread.start()
            lbClient.POST_configData(self.buildConfigData(config.pt))
            
            config.applyUpscale()
            
        return
      
        
    '''    
    Scale in the microservice
    
    Parameters:
    - config: The Configuration object.
    - server: The container that we want to scale-in. If lightweight, then change to heavyweight. If heavyweight, then shutdown container entirely.
    - dockerCli: The Docker Client used to run Docker commands.
    - lbClient: LoadBalancerClient object. Used to send requests to NGINX to update the configuration after scaling.
    '''  
    def downscale(self, config, server, dockerCli, lbClient):
        # Logic:
        # If we scale-in a heavyweight instance, then remove the container entirely.
        # Otherwise, we switch a lightweight instance back down to heavyweight instance.
        
        if server.isHeavy:
            print("Shutting down container {}".format(server.container.id))
            self.heavy.remove(server)
            
            # Stop the old heavyweight container
            stop = lambda server : server.shutdown()
            stop_thread = threading.Thread(target=stop, args=(server,))
            stop_thread.start()
            lbClient.POST_configData(self.buildConfigData(config.pt))
            
            config.applyDownscale()
            
        else:
            print("Downscaling container {}, light->heavy".format(server.container.id))
            h_desc = config.heavy_description
            tmpPort = self.getFreePort()
            
            new_container = dockerCli.containers.run(h_desc.image, detach=True, ports={h_desc.innerPort:tmpPort},
                environment=h_desc.env, network=config.network, 
                nano_cpus=(int(1000000000*h_desc.resources["cpu"])),
                mem_limit=h_desc.resources["mem"], 
                memswap_limit=h_desc.resources["swap"])
            
            new_server = ServerDescription(server.ip, tmpPort, new_container)
            new_server.capacity_h = server.capacity_h
            new_server.isHeavy = True
            self.heavy.append(new_server)
            self.light.remove(server)
            
            def delayed_post(lbClient, data, server): 
                sleep(10)
                lbClient.POST_configData(data)
            
            post_thread = threading.Thread(target=delayed_post, args=(lbClient, self.buildConfigData(config.pt), new_server))
            post_thread.start()
            
            # Stop the old lightweight container
            stop = lambda server : server.shutdown()
            stop_thread = threading.Thread(target=stop, args=(server,))
            stop_thread.start()
            lbClient.POST_configData(self.buildConfigData(config.pt))
            
            config.applyDownscale()
            
            
               
    def __str__(self):
        res = ""
        for h in self.heavy:
            res += str(h)
        res += "\n"
        
        for l in self.light:
            res += str(l)
        
        return res
        

'''
Represents the 'Monitor Server' used to communicate with NGINX

- interval: The interval between each GET request to monitor NGINX
- GET_path: The path for sending GET requests
- POST_path: The path for sending POST requests
'''
class LoadBalancerClient:
    GET_path="monitor?s="
    POST_path="lb-config"
    
    interval = 15
    
    def __init__(self, target_ip, target_port):
        self.ip = target_ip
        self.port = target_port
        self.GET_path += str(self.interval)
    
    
    # Sends GET request: Response contains the new performance data from NGINX
    def GET_monitorData(self):
        url = "http://{}:{}/{}".format(self.ip, self.port, self.GET_path)
        print(url)
        r = requests.get(url=url)
        return r.json()
    
    # Sends POST request: Updates the NGINX configuration.
    def POST_configData(self, data):
        url = "http://{}:{}/{}".format(self.ip, self.port, self.POST_path)
        r = requests.post(url=url, json=data)
        return r.status_code
        
        


if __name__ == '__main__':

    # Docker Image for NGINX load balancer
    nginx_img = "prabjotd09/nginx-dynamic:v6-5"
    
    args = sys.argv[1:]
    
    # Docker Client object to run Docker commands
    client = docker.from_env()
    
    # START: Parse the script command
    env = []
    index = 0
    while args[index] == "e":
        index += 1
        env.append(args[index])
        index += 1
    
    ip = args[index]
    index += 1
    
    network = args[index]
    index += 1
    
    nginxContainerName = args[index]
    index += 1
    
    innerPort = args[index]
    index += 1
    
    heavy_desc = None
    light_desc = None
    
    for _ in range(2):
        version = VersionDefinition(args[index], env, {
            "mem": args[index + 1],
            "swap": args[index + 2],
            "cpu": float(args[index + 3])
        }, innerPort)
        
        index += 4
        
        if args[index] == "heavy":
            heavy_desc = version
        else:
            light_desc = version
        index += 1
    
    pt = int(args[index][3:])
    index += 1
    
    max_replicas = int(args[index][4:])
    index += 1
    # END: Parse the script command
    
    # Build the microservice Configuration object.
    sysConfig = Configuration(pt, max_replicas, heavy_desc, light_desc)
    sysConfig.network = network
    
    # Build the microservice System object
    system = System()
    system.clearLogs()
    
    tmpPort = system.getFreePort()
    
    # Launch a single heavyweight instance
    new_container = client.containers.run(sysConfig.heavy_description.image, 
        detach=True, ports={innerPort:tmpPort}, environment=env,
        network=network, nano_cpus=(int(1000000000*sysConfig.heavy_description.resources["cpu"])),
        mem_limit=sysConfig.heavy_description.resources["mem"],
        memswap_limit=sysConfig.heavy_description.resources["swap"])
    
    new_server = ServerDescription(ip, tmpPort, new_container, isHeavy=True)
    system.heavy.append(new_server)
    
    
    # START: Launching NGINX Load Balancer CLient 
    nginxPort = system.getFreePort()
    configServerPort = system.getFreePort()
    while configServerPort == nginxPort:
        configServerPort = system.getFreePort()
    
    
    for env_var in env:
        key, val = env_var.split("=")
        if key == "SERVICE_PORT":
            nginxPort = int(val)
     
    nginx_container = client.containers.run(nginx_img, detach=True,
        ports = {"3333/tcp": nginxPort, "8080/tcp":configServerPort},
        name=nginxContainerName,
        )
    # END: Launching NGINX Load Balancer Client
    
    
    # Build LoadBalancerClient object and Update NGINX configuration to the initial setup
    lb_client = LoadBalancerClient(ip, configServerPort)
    post_data = system.buildConfigData(pt)
    while True:
        try:
            status = lb_client.POST_configData(post_data)
            print("POST Attempt Success", status)
            break
        except:
            print("POST Attempt Failed")
            sleep(0.1)
            
            
    # Record initial confiuration
    system.logDeployments(0)
    
    try:
        # Monitor the server periodically
        while True:
            sleep(lb_client.interval)
            monitor_data = lb_client.GET_monitorData()
            print("Monitor Data: ", monitor_data)
            
            # If no data is recieved, then no requests were recieved by the service in the previous interval.
            # Fabricate data object to show 0 activity.
            if len(monitor_data) == 0:
                no_user_data = dict()
                no_user_servers = []
                capacity = 0
                for h in system.heavy:
                    no_user_servers.append({"ip": h.ip, "port":h.port, "capacity":str(h.capacity_h)})
                    capacity += h.capacity_h
                
                for l in system.light:
                    no_user_servers.append({"ip": l.ip, "port":l.port, "capacity":str(l.capacity_l)})
                    capacity += l.capacity_l
                
                no_user_data["servers"] = no_user_servers
                no_user_data["total_capacity"] = capacity
                no_user_data["conc_requests"] = 0.0
                no_user_data["arrival_rate"] = 0.0
                
                for i in range(lb_client.interval // 15):
                    monitor_data.append(no_user_data)
            
            
            # Note: 'monitor_data' can be a list of data if NGINX logs more frequently than the monitoring interval.
            #       In this case, we record all of the data, but the scaling decision is made using the most recent log in 'monitor_data'
            scale_decision = None
            for entry in monitor_data:
                up, down, target_server = system.calculateScaling(entry, sysConfig, sysConfig.pt)
                print("Update: {},{}->{}".format(up, down, target_server))
                
                scale_decision = sysConfig.applyScalingData(up, down)
            
            if scale_decision == None:
                continue
            
            print("Scaling Decision: ", scale_decision)
            
            # Apply the scaling
            if scale_decision["upscale"]:
                system.upscale(sysConfig, target_server, client, lb_client)
            elif scale_decision["downscale"]:
                system.downscale(sysConfig, target_server, client, lb_client)
            
            # Log the current configuration
            if len(monitor_data) == 0:
                system.logDeployments(0)
            else:
                system.logDeployments(int(monitor_data[-1]["conc_requests"]))
                
                    
    # The graceful shutdown of the whole microservice and NGINX load balancer.
    except KeyboardInterrupt:
        print("Shutting Down Microservice")
        stop = lambda server : server.shutdown()
        
        for l in system.light:
            stop_thread = threading.Thread(target=stop, args=(l,))
            stop_thread.start()
        for h in system.heavy:
            stop_thread = threading.Thread(target=stop, args=(h,))
            stop_thread.start()
        
        def terminate(cont):
            cont.stop()
            cont.remove()
            
        stop_thread = threading.Thread(target=terminate, args=(nginx_container,))
        stop_thread.start()
    
            
    
    
    
    
    
    
    
    

            
        
       
       
            
