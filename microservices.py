import sys
import socket
import docker
import requests
import threading
from time import time, localtime, sleep

class ListNode:
    def __init__(self, val=-1):
        self.val = val
        self.next = None
        self.prev = None
        
    def __str__(self):
        return "({})".format(self.val)

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
        
        doUpscale, doDownscale = (False, False)
        if self.scale_up.count == 2:
            doUpscale = True
        elif self.scale_down6.count == 6 and self.scale_down24.count > 20:
            doDownscale = True
        
        return {"upscale": doUpscale, "downscale": doDownscale}
        
    
    def applyUpscale(self):
        self.scale_up = IntLinkedList(2)
    
    def applyDownscale(self):
        for i in range(6):
            self.scale_down6.add(0)
            self.scale_down24.add(0)
            
    def __str__(self):
        res = ""
        res += "pt={}, max={}\n".format(self.pt, self.max_replicas)
        res += "heavy={}\nlight={}\n".format(str(self.heavy_description), str(self.light_description))
        return res
        
        
class ServerDescription:
    def __init__(self, ip, port, container, c_h=0.0, c_l=0.0, isHeavy=True):
        self.ip = ip
        self.port = port
        self.container = container
        self.capacity_h = c_h
        self.capacity_l = c_l
        self.isHeavy = isHeavy
    
    def capacityDelta(self):
        if self.isHeavy:
            return self.capacity_h
        
        return self.capacity_l - self.capacity_h
        
    def shutdown(self):
        self.container.stop()
        self.container.remove()
        print("Container Terminated: {}".format(str(self)))
        
    
    def __str__(self):
        res = ""
        res += "{}:{}->{}\t capacityH: {}\t capacityL: {}\t isHeavy: {}\n".format(self.ip, self.port, self.container.id, self.capacity_h, self.capacity_l, self.isHeavy)
        return res


class System:
    data_file = "./deployments.csv"

    def __init__(self, heavy=[], light=[]):
        self.heavy = heavy
        self.light = light
    
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
    
    def clearLogs(self):
        f = open(self.data_file, "w")
        f.write("")
        f.close()
        return
    
    def logDeployments(self, load):
        f = open(self.data_file, "a")
        
        now = localtime(time())
        h, m, s = now.tm_hour, now.tm_min, now.tm_sec
        
        data = "{:02d}:{:02d}:{:02d},{},{},{}\n".format(h, m, s, len(self.heavy), len(self.light), load)
        f.write(data)
        f.close()
        return
        
        
    def getFreePort(self):
        sock = socket.socket()
        sock.bind(('', 0))
        port = sock.getsockname()[1]
        sock.close()
        return port
        
    def calculateScaling(self, data, config):
        max_scale = config.max_replicas
        load = data["conc_requests"]
        capacity = data["total_capacity"]
        
        servers = dict()
        for server in data["servers"]:
            key = "{}:{}".format(server["ip"], server["port"])
            servers[key] = float(server["capacity"])
            
        self.updateCapacities(servers)
        delta, deltaServer = self.getMinDownscaleDelta()
        
        upscale, downscale, server = (0, 0, None)
        if load > 0.9 * capacity and len(self.light) < max_scale:
            upscale = 1
            if len(self.heavy) + len(self.light) == max_scale:
                for h in self.heavy:
                    if server == None or h.capacity_h < server.capacity_h:
                        server = h
                
        elif (load == 0 or load < 0.9 * (capacity - delta)) and (len(self.heavy) > 1 or len(self.light) > 0):
            downscale = 1
            server = deltaServer
        
        return (upscale, downscale, server)
            
    
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
        
    def getMinDownscaleDelta(self):
        min_delta = -1
        server = None
        
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
        
                
    def upscale(self, config, server, dockerCli, lbClient):
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
            
            def delayed_post(lbClient, data, server): 
                sleep(10)
                lbClient.POST_configData(data)
                
            post_thread = threading.Thread(target=delayed_post, args=(lbClient, self.buildConfigData(config.pt), new_server))
            post_thread.start()
            config.applyUpscale()
            
        else:
            print("Upscaling container {}, heavy->light".format(server.container.id))
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
            
            def delayed_post(lbClient, data, server): 
                sleep(10)
                lbClient.POST_configData(data)
            
            post_thread = threading.Thread(target=delayed_post, args=(lbClient, self.buildConfigData(config.pt), new_server))
            post_thread.start()
            
            stop = lambda server : server.shutdown()
            stop_thread = threading.Thread(target=stop, args=(server,))
            stop_thread.start()
            lbClient.POST_configData(self.buildConfigData(config.pt))
            
            config.applyUpscale()
            
        return
        
    
    def downscale(self, config, server, dockerCli, lbClient):
        if server.isHeavy:
            print("Shutting down container {}".format(server.container.id))
            self.heavy.remove(server)
            
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
        

class LoadBalancerClient:
    GET_path="monitor?s="
    POST_path="lb-config"
    
    interval = 45
    
    def __init__(self, target_ip, target_port):
        self.ip = target_ip
        self.port = target_port
        self.GET_path += str(self.interval)
    
    def GET_monitorData(self):
        url = "http://{}:{}/{}".format(self.ip, self.port, self.GET_path)
        print(url)
        r = requests.get(url=url)
        return r.json()
    
    def POST_configData(self, data):
        url = "http://{}:{}/{}".format(self.ip, self.port, self.POST_path)
        r = requests.post(url=url, json=data)
        return r.status_code
        
        


if __name__ == '__main__':
    args = sys.argv[1:]
    
    client = docker.from_env()
    
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
    
    sysConfig = Configuration(pt, max_replicas, heavy_desc, light_desc)
    sysConfig.network = network
    
    system = System()
    system.clearLogs()
    
    tmpPort = system.getFreePort()
    
    new_container = client.containers.run(sysConfig.heavy_description.image, 
        detach=True, ports={innerPort:tmpPort}, environment=env,
        network=network, nano_cpus=(int(1000000000*sysConfig.heavy_description.resources["cpu"])),
        mem_limit=sysConfig.heavy_description.resources["mem"],
        memswap_limit=sysConfig.heavy_description.resources["swap"])
    
    new_server = ServerDescription(ip, tmpPort, new_container, isHeavy=True)
    system.heavy.append(new_server)
    
    #print(21)
    #print(system)
    #print(sysConfig)
    
    nginxPort = system.getFreePort()
    configServerPort = system.getFreePort()
    while configServerPort == nginxPort:
        configServerPort = system.getFreePort()
    
    nginx_img = "nginx-dynamic:v4"
    
    for env_var in env:
        key, val = env_var.split("=")
        if key == "SERVICE_PORT":
            nginxPort = int(val)
     
    nginx_container = client.containers.run(nginx_img, detach=True,
        ports = {"3333/tcp": nginxPort, "8080/tcp":configServerPort},
        name=nginxContainerName,
        )
    
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
            
    system.logDeployments(0)
    
    try:
        while True:
            sleep(lb_client.interval)
            monitor_data = lb_client.GET_monitorData()
            print("Monitor Data: ", monitor_data)
            
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
                no_user_data["conc_requests"] = 0
                
                for i in range(lb_client.interval // 5):
                    monitor_data.append(no_user_data)
            
            scale_decision = None
            for entry in monitor_data:
                up, down, target_server = system.calculateScaling(entry, sysConfig)
                print("Update: {},{}->{}".format(up, down, target_server))
                
                scale_decision = sysConfig.applyScalingData(up, down)
            
            if scale_decision == None:
                continue
            
            print("Scaling Decision: ", scale_decision)
            
            if scale_decision["upscale"]:
                system.upscale(sysConfig, target_server, client, lb_client)
            elif scale_decision["downscale"]:
                system.downscale(sysConfig, target_server, client, lb_client)
            
            if len(monitor_data) == 0:
                system.logDeployments(0)
            else:
                system.logDeployments(int(monitor_data[-1]["conc_requests"]))
                
                    
            
    except KeyboardInterrupt:
        print("Shutting Down Microservice")
        
    #TODO: Shut down all containers 
    
            
    
    
    
    
    
    
    
    

            
        
       
       
            
