
Documentation is available at http://nginx.org

This is an extension of NGINX Open Source which has replaced the default round robin load balancing scheme with a custom scheme that is made specifically to load balance between multiversioned software.
At the current stage of development, the load balancing is supported for software with 1 Heavy-weight version and 1 Light-weight version. The heavy version is the regular "full" service of the application and the light version provides the same service at a reduced quality. 



# Logic Behind Multi-versioning
Typically if the current resources of the system and the number of service deploymenets are insufficient to support the current load on the service without violating the response time SLA (Service Level Agreement), then the service would be scaled up. However, this may become costly to keep scaling up whenever the load exceeds current capacity. An alternative is to have a second version of the service which provides lower quality service, but it is able to handle much larger loads given the same number of resources and deployments. In this manner, clients can recieve timely service without the service provider from having to incur unmanagable costs. For more information about this type of multiversioning and its benefits, you can refer to a research paper that this project closely follows:
A framework for satisfying the performance requirements of containerized software systems through multi-versioning - http://dx.doi.org/10.1145/3358960.3379125


# Definition of Performance Target:
The SLA (Service Level Agreement) specifies an upper-bound on the response-time that requests can have which ensures users recieve timely responses. The term referred to as the "performance target (pt)" in this program is exactly this desired upper bound. The load balancing will aim to keep the p90/p95/p99 response-times as close to this performance target as possible.


# Set-up Instructions on Linux:
1. Install a C compiler such as GCC. Use the command `gcc -v` to verify it is correctly installed.
2. Clone this repository to your desired directory.
3. Open the terminal and change your current directory to the root folder of the cloned repository.
4. Configure NGINX by running the following command: ``./configure --prefix=/etc/nginx --sbin-path=/usr/sbin/nginx --conf-path=/etc/nginx/nginx.conf --error-log-path=/var/log/nginx/error.log --http-log-path=/var/log/nginx/access.log --pid-path=/var/run/nginx.pid --lock-path=/var/run/nginx.lock --http-client-body-temp-path=/var/cache/nginx/client_temp --http-proxy-temp-path=/var/cache/nginx/proxy_temp --http-fastcgi-temp-path=/var/cache/nginx/fastcgi_temp --http-uwsgi-temp-path=/var/cache/nginx/uwsgi_temp --http-scgi-temp-path=/var/cache/nginx/scgi_temp --user=nginx --group=nginx --with-http_realip_module --with-http_addition_module --with-http_sub_module --with-http_dav_module --with-http_flv_module --with-http_mp4_module --with-http_gunzip_module --with-http_gzip_static_module --with-http_random_index_module --with-http_secure_link_module --with-http_stub_status_module --with-http_auth_request_module --with-threads --with-stream --with-http_slice_module --with-mail --with-file-aio --with-ipv6 --with-http_v2_module --with-cc-opt='-O2 -g -pipe -Wall -Wp,-D_FORTIFY_SOURCE=2 -fexceptions -fstack-protector --param=ssp-buffer-size=4 -m64 -mtune=generic' --with-http_realip_module``
5. Compile the program with: `sudo make`
6. Installing the program with: `sudo make install`
7. Set the load balancer configuration file (Instructions Below)
8. Start the program with: `sudo nginx`



# Configuring the Load Balancer:
1. From the root directory go to `./conf` directory and open the `nginx.conf` file.
2. Inside the `http` block there is a block called `upstream backend` with a list of servers. Change the server configuration as follows:
  - Identify the IP address and port of your heavy-weight version of the service you have already deployed on some server. Replace that with the first line in the `upstream backend` block. Change the weight parameter to 2.
  - For the second line repeat the previous step, except set the weight parameter to any number other than 2 (Example: 7)
3. To configure the SLA (response-time performance target), add `pt=[resp_time_performance_target]` to the end of just ONE of the server lines that were updated in step 2.
    After step (3), the result should look like this with the specifics of your set up replaced with the variables in '[..,]'
    upstream backend {
        server [Heavyweight_IP]:[Heavyweight_Port] weight=2 pt=[performance_target];
        server [Lightweight_IP]:[Lightweight_Port] weight=7;
    }
4. [Option - Default port is 3333] You can change the port than NGINX will run on in the same file. Inside the `http` block there is a block `server`. Within the `server` block change the number beside `listen` to your desired port.
5. To save your configuration file run the command from the ./conf directory: `sudo cp ./nginx.conf /etc/nginx/nginx.conf`.
6. If your NGINX is currently running, use `sudo nginx -s reload` to update the configuration at run-time. Otherwise, use `sudo nginx` to start up the load balancer.

  


