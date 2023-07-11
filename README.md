
Original NGINX Documentation is available at http://nginx.org

# Description
This is an extension of NGINX Open Source which has replaced the default round robin load balancing scheme with a custom scheme that is made specifically to load balance between multiversioned software.
At the current stage of development, the load balancing is supported for software with 1 Heavy-weight version and 1 Light-weight version. The heavy version is the regular "full" service of the application and the light version provides the same service at a reduced quality. 



# Logic Behind Multi-versioning
Typically if the current resources of the system and the number of service deploymenets are insufficient to support the current load on the service without violating the response time SLA (Service Level Agreement), then the service would be scaled up. However, this may become costly to keep scaling up whenever the load exceeds current capacity. An alternative is to have a second version of the service which provides lower quality service, but it is able to handle much larger loads given the same number of resources and deployments. In this manner, clients can recieve timely service without the service provider from having to incur unmanagable costs. For more information about this type of multiversioning and its benefits, you can refer to a research paper that this project closely follows:
A framework for satisfying the performance requirements of containerized software systems through multi-versioning - http://dx.doi.org/10.1145/3358960.3379125.

You may also refer to the source code for the project developed in this paper whose purpose is to extend the Docker containerization framework to multiversioned microservice deployment. It has been added to this project here: [DockerMV](https://github.com/prabjot09/nginx-dynamic-load-balancing/tree/main/DockerMV_SaraGholami)


# Definition of Performance Target:
The SLA (Service Level Agreement) specifies an upper-bound on the response-time that requests can have which ensures users recieve timely responses. The term referred to as the "performance target (pt)" in this program is exactly this desired upper bound. The load balancing will aim to keep the p90/p95/p99 response-times as close to this performance target as possible.


# Set-up Instructions on Linux:
1. Install a C compiler such as GCC. Use the command `gcc -v` to verify it is correctly installed.
2. Clone this repository to your desired directory.
3. Open the terminal and change your current directory to the root folder of the cloned repository.
4. Configure NGINX by running the following command:

   ``./configure --prefix=/etc/nginx --sbin-path=/usr/sbin/nginx --conf-path=/etc/nginx/nginx.conf --error-log-path=/var/log/nginx/error.log --http-log-path=/var/log/nginx/access.log --pid-path=/var/run/nginx.pid --lock-path=/var/run/nginx.lock --http-client-body-temp-path=/var/cache/nginx/client_temp --http-proxy-temp-path=/var/cache/nginx/proxy_temp --http-fastcgi-temp-path=/var/cache/nginx/fastcgi_temp --http-uwsgi-temp-path=/var/cache/nginx/uwsgi_temp --http-scgi-temp-path=/var/cache/nginx/scgi_temp --user=nginx --group=nginx --with-http_realip_module --with-http_addition_module --with-http_sub_module --with-http_dav_module --with-http_flv_module --with-http_mp4_module --with-http_gunzip_module --with-http_gzip_static_module --with-http_random_index_module --with-http_secure_link_module --with-http_stub_status_module --with-http_auth_request_module --with-threads --with-stream --with-http_slice_module --with-mail --with-file-aio --with-ipv6 --with-http_v2_module --with-cc-opt='-O2 -g -pipe -Wall -Wp,-D_FORTIFY_SOURCE=2 -fexceptions -fstack-protector --param=ssp-buffer-size=4 -m64 -mtune=generic' --with-http_realip_module``
6. Compile the program with: `sudo make`
7. Installing the program with: `sudo make install`
8. Set the load balancer configuration file (Instructions Below)
9. Start the program with: `sudo nginx`



# Configuring the Load Balancer:
1. From the root directory go to `./conf` directory and open the `nginx.conf` file.
2. Inside the `http` block there is a block called `upstream backend` with a list of servers. Change the server configuration as follows:
  - Identify the IP address and port of your heavy-weight version of the service you have already deployed on some server. Replace that with the first line in the `upstream backend` block. Change the weight parameter to 2.
  - For the second line repeat the previous step, except set the weight parameter to any number other than 2 (Example: 7)
3. To configure the SLA (response-time performance target), add `pt=[resp_time_performance_target]` to the end of just ONE of the server lines that were updated in step 2.

    After step (3), the result should look like this with the specifics of your set up replaced with the variables in '[..,]'
    ![image](https://github.com/prabjot09/nginx-dynamic-load-balancing/assets/77180065/512fbafc-85f2-4227-a39f-cc4766e00ad8)

4. [Option - Default port is 3333] You can change the port than NGINX will run on in the same file. Inside the `http` block there is a block `server`. Within the `server` block change the number beside `listen` to your desired port.
5. To save your configuration file run the command from the ./conf directory: `sudo cp ./nginx.conf /etc/nginx/nginx.conf`.
6. If your NGINX is currently running, use `sudo nginx -s reload` to update the configuration at run-time. Otherwise, use `sudo nginx` to start up the load balancer.

  
# Source Code Modifications:
The original NGINX source code has been modified in 3 main ways.
1. New data structures have been created to represent the service versions and relevant metrics used to perform the new load balancing.
2. The replacement of the Round Robin load balancing algorithm with the custom load balancing technique defined in this project done in **./src/http/ngx_http_upstream_round_robin.c**.
3. Additional logging done after request completion, and updating the metrics used for the load balancing as requests are completed.

The specific modifications and assoicated source code files are listed below:
1. **./src/http/ngx_http_request.h**:
   1. Created `custom_versioned_server_t` data structure to represent versions and relevant data such as the number of requests completed, number of active requests, list of active request start times, prediction metrics (used by load balancing algorithm), etc.
   2. Created `req_time_t` data structure to represent the start times of all active request in order of oldest to newest. Implemented as a linked list.
   3. Modified `ngx_http_request_t` data structure to specify the version that a request is sent to, its start time, no. of requests completed at its arrival, etc.
   
2. **./src/http/ngx_http_upstream_round_robin.h**:
   1. Modified `ngx_http_upstream_rr_peer_t` data structure to include the version of the upstream server, and its performance target.
      
3. **./src/http/ngx_http_upstream_round_robin.c**:
   1. Created `custom_server_init()` method to initialize the `custom_versioned_server_t` data structure with initial values.
   2. Modified `ngx_http_upstream_init_round_robin()` method to initialize 2 structures for each version `custom_versioned_server_t` and specify the correct version for each upstream server as specified in the nginx.conf configuration file. Also, retrieve the performance target from the configuration file.
   3. Modified `ngx_http_upstream_get_peer()` method to replace the round robin load balancing strategy with my own custom load balancing. In brief, it retrieves the data of both the light and heavy versions of the service, and applies the custom load balancing technique to predict the response time of an incoming request and retrieve the duration of the oldest active request. If either of these are violating the performance target, then send the request to the light version. Otherwise, the load balancer has predicted that the system load is low enough that we can provide the request full service by sending it to the heavy version.

4. **./src/http/ngx_http_upstream.c**:
   1. Modified the `ngx_http_upstream_server()` method to accept the performance target configuration parameter.
   2. Modified the `ngx_http_upstream_connect()` method to initialize information to the request structure relevant to the implemented load balancing such as request arrival time, selected service version, no. of completed requests at arrival, etc.

5. **./src/http/modules/ngx_http_log_module.c**
   1. Modified the `ngx_http_log_request_time()` method to log additional relevant information for each request such as the prediction made by the load balancing technique, the no. of active requests, the version of the service that responded to this request, arrival time, etc. It also includes the calculation done to update the prediction scheme based on the response time logs of the most recently completed request.


# Load Balancing Setup/Calculations:
This set up generates 2 values ($p$ and $t$ which are used for the load balancing logic).
1. **Response Time Prediction**: For each incoming request the load balancer predicts the response time if the request were to be executed on the heavy-weight version. We denote this predicted time with $p$. 
   1. **Estimate the Average Request Load**: In order to perform the afformentioned prediction, the model first estimates the load that a single request puts on the service. This is calculated each time a request is completed to maintain an updated estimate. The logic behind the calculation is that if a request takes $X$ time to be processed by the service, and the service had responded to $Y$ requests in this duration, then on average each request takes $(X / Y)$ time to be executed. This can be considered the 'load' of a single request. Thus, this gives the following calculation (t = response time, $r_f$ = Requests Complete Now, $r_i$ = Requests Complete on Arrival, $a$ = Average Request Load): $$a = {{t} \over {r_f - r_i}}$$.
   2. **Exponential Smoothing**: To ensure that both recent and old response data is incorporated exponential smoothing is used each time the average request load is updated. By defining the overall estimate for the average request load as $e$, then we can calculate the exponentially smoothed average request load as ($e_i$ = The estimate of request load before the update, $e_f$ = the updated estimated, $a$ = The calculation from the previous step, $\alpha$ = exponential smoothing factor): $$e_f = (1-\alpha)\*e_i + \alpha\*{a}$$. This $e_f$ is the new value for the average request load.
   3. **Load Prediction**: From the previous calculation we know that the average time to execute a request is estimated to be $e_f$. If the number of active requests is $n$, then we can predict the response time of an incoming request to be the time to finish all active requests plus the incoming request. The predicted response time $p$ can be defined as: $$p = e_f \* (n+1)$$
2. **Current Load Management**: The load balancer keeps track of all active requests and how long it has been since the request arrived. We denote the active duration of the oldest active request as $t$.
   1. **Request Queue**: A linked list data structure associated with each service version containing all active requests on that service starting from the oldest to the newest. As new requests arrive, their arrival time is recorded at the end of the queue. As requests are completed, their arrival times are set to NULL.
   2. **Oldest Active Request**: Given the above request queue, if we remove elements from the queue until the first element has a non-NULL arrival time, then the first element (if any left) will be the arrival time of the oldest request. By comparing it with the current time the load balancer calculates the elapsed time since the requests arrival. This time is referred to as $t$.

# Load Balancing Logic:
For the explaination behind the variables used in this section refer to the previous section on **Load Balancing Setup/Calculations.**
Note: As mentioned earlier $pt$ refers to the performance target (i.e. the upper bound for the response time specified in the SLA).
1. If $p \ge pt$, send request to light-weight version of service.
2. If $(t + e_f) \ge pt$, send request to light-weight version of service.
3. Otherwise, send request to heavy-weight version of service.
Reasoning: If either we predict the request to exceed the performance target (response time upper bound) if sent to the heavy-weight version or that the current load on the heavy-weight version exceeds the performance target, then the current system load is too high to give the request full service. However, when neither of these conditions are violated, then the load on the system is considered low enought that we can safely provide full service for this request.
