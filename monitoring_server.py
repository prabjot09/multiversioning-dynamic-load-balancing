from http.server import BaseHTTPRequestHandler, HTTPServer
from json import loads as parse, dumps as stringify
from time import time, localtime 

import os

'''
Convert the provided time into a proper format

Parameters: (h, m, s)
- Can take negative values or values higher than permissible (Ex: s = 90)

Return Value: (h, m, s)
- Returns properly formatted time (h = [0,23], m = [0,59], s =[0,59])
'''
def normalize_time(h, m, s):
    if s < 0:
       s += 60
       m -= 1
       
       if m < 0:
           m += 60
           h -= 1
           
           if h < 0:
               h += 24
    
    if s > 59:
        s -= 60
        m += 1
        
        if m > 59:
            m -= 60
            h += 1
        
            if h > 23:
                h -= 24
    
    return (h, m, s)
           

'''
Monitor Server

Has 2 acceptable Requests:
- GET /monitor?s={time},    where time is an integer.
- POST /lb-config,          (requires JSON file in body)
'''
class CustomServer(BaseHTTPRequestHandler):
    
    # Response to GET request
    def do_GET(self):
        if '/monitor' not in self.path:
            self.send_response(404)
            return;
            
        _, query = self.path.split("?")
        _, interval = query.split("=")
        interval = int(interval)
        
        now = localtime(time())
        h, m, s = now.tm_hour, now.tm_min, now.tm_sec
        
        # START: Retrieve data from NGINX access.log file for past `interval` seconds.
        s-= interval
        for i in range(interval):
            h, m, s = normalize_time(h, m, s)
            output = '>>'
            if i == 0:
                output = '>'
            
            cmd = os.system("cat /var/log/nginx/access.log | grep \"System State\" | grep \"{:02d}:{:02d}:{:02d}\" {} ./system_status.txt".format(h, m, s, output))
            s += 1
        # END: Retrieve data from NGINX access.log file for past `interval` seconds.
        
        
        # START: Parse the retrieved data stored in a temporary `./system_status.txt` file.
        resp = []
        f = open("./system_status.txt", "r")
        for line in f:
            resp_entry = dict()
            
            _, data = str(line).split("System State:")
            data = data[:-1]
            entries = data.split(",")
            for entry in entries:
                values = entry.split(":")
                
                if values[0] == "server":
                    servers = resp_entry.get("servers", [])
                    
                    server_data = ":".join(values[1:])
                    socket, capacity = server_data.split("-")
                    ip, port = socket[1:-1].split(":")
                     
                    servers.append({"ip": ip, "port": int(port), "capacity": "{:.2f}".format(float(capacity))})
                    resp_entry["servers"] = servers
                    
                elif values[0] == "total":
                    resp_entry["total_capacity"] = float(values[1])
               
                elif values[0] == "request_load":
                    resp_entry["conc_requests"] = float(values[1])  
                    
                elif values[0] == "arrival_rate":
                    resp_entry["arrival_rate"] = float(values[1])
            
            resp.append(resp_entry)
        # END: Parse the retrieved data stored in a temporary `./system_status.txt` file.             
        
        
        # Send the parsed data as response.
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(stringify(resp).encode('utf-8'))
         

    # Response to POST request
    def do_POST(self):
        if self.path != '/lb-config':
            self.send_response(404)
            return;
            
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        post_data = parse(post_data.decode('utf-8'))
        
        # Update NGINX with new configuration
        self.build_conf(post_data)
        print("Reconfiguring NGINX with config data: ", post_data)
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write("POST req for {}\n".format(self.path).encode('utf-8'))
                
      
    '''
    Build the new NGINX configuration file and restarts NGINX to apply configuration changes.
    
    Parameter:
    - data : The data containing information about the new configuration.
         Format - JSON:
         [
             {"server": (string - IP address), "port": (int - port #), "type": (string - 'heavy' or 'light'), "pt": (int - performance target, Can be empty)},
             ...,
             ... (One for each server)
         ]
    '''  
    def build_conf(self, data):
        conf = "worker_processes  1;\n"
        conf += "events { \n\tworker_connections  1024; \n}\n"
        conf += "\nhttp { \n"
        conf += "\tlog_format main  '[$time_local] $request - $request_time ';\n";
        conf += "\taccess_log  /var/log/nginx/access.log  main;\n"
        conf += "\n\tupstream backend { \n"
        
        # Build the configuration file for each server
        for server in data:
            weight = 7
            if server['type'] == "heavy":
                weight = 2
            
            pt = ""
            if server.get("pt") != None:
                pt = " pt={}".format(server['pt'])
                
            conf += "\t\tserver {}:{} weight={}{};\n".format(server['server'], server['port'], weight, pt)
        
        conf += "\t}\n"
        conf += "\n\tserver {\n "
        conf += "\t\tlisten 3333;\n"
        conf += "\t\tserver_name localhost;\n"
        conf += "\n\t\tlocation / {\n"
        conf += "\t\t\tproxy_pass http://backend;\n"
        conf += "\t\t}\n"
        conf += "\t}\n"
        
        conf += "}\n"
        
        # Write the configuration into a temporary file
        f = open("./nginx.conf", "w")
        f.write(conf)
        f.close()
        
        # Copy the config in temporary file to the actual NGINX configuration file
        os.system("cp ./nginx.conf /etc/nginx/nginx.conf")
        # Apply configuration by restarting NGINX
        reloaded = os.system("nginx -s reload")
        
        if reloaded != 0:
            os.system("nginx")
        
        return
        
        
# Starts the server
if __name__ == '__main__':
    server_address = ('', 8080)
    httpd = HTTPServer(server_address, CustomServer)
    print('Listening on port 8080')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    print('Stopping httpd...\n')
        
