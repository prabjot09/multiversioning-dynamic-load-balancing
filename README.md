
Original NGINX Documentation is available at http://nginx.org.
This is an extension of NGINX which implements load balancing for multiversioned services.

# Table of Contents
- [Concept Introduction](#intro)
  - [Description](#desc)
  - [Multiversioning Background](#mv-logic)
  - [Defining Performance Target](#pt)
- [Getting Started with Project](#start)
  - [Setting Up](#setup)
  - [Load Balancing Configuration](#lb-config)
  - [Evaluating Version Utilization](#utilization)
- [Project Logic](#logic)
  - [Source Code Modifications](#src-code)
  - [Load Balancing Calculations](#lb-math)
  - [Load Balancing Logic](#lb-logic)
- [Testing the Project](#test)
  - [Test Using ZNN News Service](#znn)
  - [Test Using Teastore Recommender Service](#teastore)
  - [Load Testing Using JMeter](#jmeter)
- [Shutdown and Cleanup](#close)

___
<a name="intro"/>

# Intro
This section discusses the conceptual background behind the project and defines the term 'performance target' used in the rest of the documentation.
<a name="desc"/>
<br/>

## Description
This is an extension of NGINX Open Source which has replaced the default round robin load balancing scheme with a custom scheme that is made specifically to load balance between multiversioned software.
At the current stage of development, the load balancing is supported for software with 1 Heavy-weight version and 1 Light-weight version. The heavy version is the regular "full" service of the application and the light version provides the same service at a reduced quality. 


<a name="mv-logic"/>

## Logic Behind Multi-versioning
Typically if the current resources of the system and the number of service deployments are insufficient to support the current load on the service without violating the response time SLA (Service Level Agreement), then the service would be scaled up. However, it may become costly to keep scaling up whenever the load exceeds current capacity. An alternative is to have a second version which provides lower quality service, but it is able to handle much larger loads given the same number of resources and deployments. In this manner, clients can recieve timely service without the service provider from having to incur unmanageable costs. For more information about this type of multiversioning and its benefits, you can refer to a research paper that this project closely follows: *A framework for satisfying the performance requirements of containerized software systems through multi-versioning* - http://dx.doi.org/10.1145/3358960.3379125.

You may also refer to the source code for the project developed in that paper whose purpose is to extend the Docker containerization framework to the multiversioning of microservices. The source code has been added to this repository here: [DockerMV](https://github.com/prabjot09/multiversioning-dynamic-load-balancing/tree/main/DockerMV_SaraGholami)

<a name="pt"/>

## Definition of Performance Target:
The SLA (Service Level Agreement) specifies an upper-bound on the response-time which ensures that users recieve timely responses. The term referred to as the "performance target (*pt*)" in this project is exactly this desired upper bound measured in milliseconds. The load balancing will aim to keep the outlier (i.e, p90, p95, p99) response-times as close to this performance target as possible.

___
<a name="start"/>

# Getting Started with Project:
This section covers how to install, compile, configure, and run the load balancer. It also goes over a helpful script which allows the tester to see the distribution of requests that go to each version of the service in real-time.
<a name="setup"/>
<br/>

## Set-up Instructions on Linux:
1. Install a C compiler such as GCC. Use the command `gcc -v` to verify it is correctly installed.
2. Clone this repository to your desired directory.
3. Open the terminal and change your current directory to the root folder of the cloned repository.
4. Configure NGINX by running the following command:

   ``/configure --prefix=/etc/nginx --sbin-path=/usr/sbin/nginx --conf-path=/etc/nginx/nginx.conf --error-log-path=/var/log/nginx/error.log --http-log-path=/var/log/nginx/access.log --pid-path=/var/run/nginx.pid --lock-path=/var/run/nginx.lock --with-http_realip_module --with-http_addition_module --with-http_sub_module --with-http_dav_module --with-http_flv_module --with-http_mp4_module --with-http_gunzip_module --with-http_gzip_static_module --with-http_random_index_module --with-http_secure_link_module --with-http_stub_status_module --with-http_auth_request_module --with-threads --with-stream --with-http_slice_module --with-mail --with-file-aio --with-ipv6 --with-http_v2_module --with-cc-opt='-O2 -g -pipe -Wall -Wp,-D_FORTIFY_SOURCE=2 -fexceptions -fstack-protector --param=ssp-buffer-size=4 -m64 -mtune=generic' --with-http_realip_module``
5. Compile the program with: `sudo make`
6. Install the program with: `sudo make install`
7. Set the load balancer configuration file (Instructions Below)
8. Start the program with: `sudo nginx`



<a name="lb-config"/>

## Configuring the Load Balancer:
1. From the root directory, go to `./conf` directory and open the `nginx.conf` file.
2. Inside the `http` block there is a sub-block named `upstream backend` with a list of servers. Change the server configuration as follows:
   1. Identify the IP address and port of the heavy-weight version that you have already deployed on some server. Change the first line in the `upstream backend` block to use this IP address and port. Also, change the weight parameter to 2.
   2. Repeat the previous step for the second line, but set the weight parameter to any number *other than* 2 (Example: 7)
3. To configure the SLA (response-time performance target in milliseconds), add `pt=[performance_target]` to the end of just ONE of the server lines that were updated in step (2). (Ex: pt=500)

    After step (3), the result should look like this with the specifics of your set-up replaced with the variables in '[...]'
    ![image](https://github.com/prabjot09/nginx-dynamic-load-balancing/assets/77180065/512fbafc-85f2-4227-a39f-cc4766e00ad8)

4. [Option - Default port is 3333] You can change the load balancer's port in this file as well. Inside the `http` block there is a sub-block called `server`. Within the `server` sub-block change the number beside `listen` to your desired port.
5. Save the `nginx.conf` file. Load the configuration file by running this command from the root directory of the repository: `sudo cp ./nginx.conf /etc/nginx/nginx.conf`.
6. If the load balancer is already running, use command `sudo nginx -s reload` to update the configuration at run-time. Otherwise, use `sudo nginx` to start up the load balancer.

<a name="utilization"/>

## Evaluating Version Utilization:
In order to evaluate how the system is responding to the current load, a script has been created which will output in real-time the number of requests that each version of the service has recieved and the percent of request recieved by the heavy-weight version (in other words, the percent of requests given full service). The script can be found here: [proportion.sh](https://github.com/prabjot09/nginx-dynamic-load-balancing/blob/main/proportion.sh). To run the script use this command from the root directory of this repository: `sh proportion.sh`.

This script is meant to be run while the load balancer is running and is recieving some load from real/simulated users. It is used to evaluate the load balancer's effectiveness in balancing performance (minimizing response times) and service quality (maximizing requests run by heavy-weight version).

The output of the script is produced in the terminal that the script is run from. But it also generates a .csv file which can be later plotted to visualize the output. This file will be generated in the `/var/log/nginx/usage.csv` directory on the host that runs the load balancer.

___
<a name="logic"/>

# Project Logic
This sections covers the theory behind the project, the modifications made to the default NGINX load balancer and the logic behind the decisions made.
<a name="src-code"/>
<br/>

## Source Code Modifications:
The original NGINX source code has been modified in 3 main ways.
1. New data structures have been introduced to represent the different service versions and to store relevant metrics used by the custom load balancer.
2. The Round Robin load balancing logic has been replaced with the custom load balancing technique defined in this project. These changes were done in **./src/http/ngx_http_upstream_round_robin.c**.
3. Additional logging is done after request completion, and the metrics stored in the new data structures are updated at this time.

The specific modifications and assoicated source code files are listed below:
1. **./src/http/ngx_http_request.h**:
   1. Created `custom_versioned_server_t` data structure to represent versions and relevant data such as the number of requests completed, number of active requests, list of active request start times, prediction metrics (used by load balancing algorithm), etc.
   2. Created `req_time_t` data structure to represent the start times of all active request in order from oldest to newest. This data structure was implemented as a linked list.
   3. Modified `ngx_http_request_t` data structure to specify the version that a request is sent to, the requests start time, no. of requests completed at its arrival, etc.
   
2. **./src/http/ngx_http_upstream_round_robin.h**:
   1. Modified `ngx_http_upstream_rr_peer_t` data structure to include the version of the upstream server, and its performance target.
      
3. **./src/http/ngx_http_upstream_round_robin.c**:
   1. Created `custom_server_init()` method to initialize the `custom_versioned_server_t` data structure with initial values.
   2. Modified `ngx_http_upstream_init_round_robin()` method to initialize 2 structures for each version `custom_versioned_server_t` and attach the correct version to each upstream server as specified in the nginx.conf configuration file. Also, retrieve the performance target value from the configuration file.
   3. Modified `ngx_http_upstream_get_peer()` method to replace the round robin load balancing strategy with my own custom load balancing. In brief, it retrieves the data of both the light and heavy versions of the service, and applies the custom load balancing technique to predict the response time of an incoming request and retrieve the duration of the oldest active request. If either of these values violate the performance target, then send the request to the light version. Otherwise, the load balancer has predicted that the system load is low enough that we can provide the request full service by sending it to the heavy version.

4. **./src/http/ngx_http_upstream.c**:
   1. Modified the `ngx_http_upstream_server()` method to parse the performance target parameter from the `nginx.conf` file.
   2. Modified the `ngx_http_upstream_connect()` method to initialize request information that is relevant to the implemented load balancing such as request arrival time, selected service version, no. of completed requests at arrival, etc.

5. **./src/http/modules/ngx_http_log_module.c**
   1. Modified the `ngx_http_log_request_time()` method to log additional relevant information for each request such as the predicted reponse time, the no. of active requests, the version of the service that responded to this request, arrival time, etc. It also calculates and updates the prediction scheme based on the response time logs of the most recently completed request.

<a name="lb-math"/>

## Load Balancing Setup/Calculations:
This set up generates 2 values (*p* and *t* which are used for the load balancing logic).
1. **Response Time Prediction**: For each incoming request the load balancer predicts the response time if the request were to be executed on the heavy-weight version. We denote this predicted time with *p*. 
   1. **Estimate the Average Request Load**: In order to perform the afformentioned prediction, the model first estimates the load that a single request puts on the service. This is calculated each time a request is completed to maintain an updated estimate. The logic behind the calculation is that if a request takes *X* time to be processed by the service, and the service had responded to *Y* requests in this duration, then on average each request takes *(X / Y)* time to be executed. This can be considered the 'load' of a single request. Thus, this gives the following calculation (*t* = response time, *r<sub>f* = Requests Complete Now, *r<sub>i* = Requests Complete on Arrival, *a* = Average Request Load):
      
      <img src="https://latex.codecogs.com/svg.image?&space;a={{t}\over{r_f-r_i}}" title=" a={{t}\over{r_f-r_i}}" />

   2. **Exponential Smoothing**: To ensure that both recent and old response data is incorporated exponential smoothing is used each time the average request load is updated. By defining the overall estimate for the average request load as *e*, then we can calculate the exponentially smoothed average request load as (*e<sub>i* = The estimate of request load before the update, *e<sub>f* = the updated estimated, *a* = The calculation from the previous step, &alpha; = exponential smoothing factor):
   
      <img src="https://latex.codecogs.com/svg.image?\inline&space;e_f=(1-\alpha)\*e_i&plus;\alpha*{a}" />

      This *e<sub>f* is the new value for the average request load.

   3. **Load Prediction**: From the previous calculation we know that the average time to execute a request is estimated to be *e<sub>f*. If the number of active requests is *n*, then we can predict the response time of an incoming request to be the time to finish all active requests plus the incoming request. The predicted response time *p* can be defined as:

      <img src="https://latex.codecogs.com/svg.image?p=e_f(n+1)" />
      
3. **Current Load Management**: The load balancer keeps track of all active requests and how long it has been since the request arrived. We denote the active duration of the oldest active request as *t*.
   1. **Request Queue**: A linked list data structure associated with each service version containing all active requests on that service starting from the oldest to the newest. As new requests arrive, their arrival time is recorded at the end of the queue. As requests are completed, their arrival times are set to NULL.
   2. **Oldest Active Request**: Given the above request queue, if we remove elements from the queue until the first element has a non-NULL arrival time, then the first element (if any left) will be the arrival time of the oldest request. By comparing it with the current time the load balancer calculates the elapsed time since the requests arrival. This time is referred to as *t*.


<a name="lb-logic"/>

## Load Balancing Logic:
For the explaination behind the variables used in this section refer to the previous section on **Load Balancing Setup/Calculations.**
Note: As mentioned earlier *pt* refers to the performance target (i.e. the upper bound for the response time specified in the SLA).
1. If *p &ge; pt*, send request to light-weight version of service.
2. If *(t + e<sub>f* *) &ge; pt*, send request to light-weight version of service.
3. Otherwise, send request to heavy-weight version of service.
Reasoning: If either we predict the request to exceed the performance target (response time upper bound) if sent to the heavy-weight version or that the current load on the heavy-weight version exceeds the performance target, then the current system load is too high to give the request full service. However, when neither of these conditions are violated, then the load on the system is considered low enought that we can safely provide full service for this request.

___
<a name="test"/>
  
# Testing the Project
This section goes over how to run the tests that showcase the performance of the system.
<a name="znn"/>
<br/>

## Test with ZNN News Service
Note: This experiment also requires the installation of Docker which is also part of the setup for DockerMV. Do not skip the installation of Docker when you are setting up DockerMV later in this test.

This service has the following 2 versions: 

- `znn-text` - The light-weight version which provides news only in the form of text.
- `znn-multimedia` - The heavy-weight version which provides news alongside relevant images.

The following are the steps required to execute the test:
1. Set up and compile the DockerMV software on your system. Refer to the README documentation in the "DockerMV_SaraGholami" folder of the root directory in this repo to install this project. Make sure to preform all the steps listed under the "How to Use?" section of that README file.
2. Once DockerMV is set up, navigate to the root directory of DockerMV.
3. Navigate to the following directory from the root directory of DockerMV: `./go/src/github.com/docker/cli` within DockerMV.
4. From this directory, open a terminal and run this command: `hostname -I | awk '{print $1}'`. The output is your IP address and it will be referred to as <HOST_IP>
5. Run the following commands without changing the current directory. Replace <HOST_IP> with the output recieved above. If the DockerMV program is not located in the $HOME directory, please replace '$HOME' with the path to the directory:

``sudo docker run --network="my-net" -d -p 3306:3306 alirezagoli/znn-mysql:v1``

``sudo ./build/docker service create <HOST_IP> my-net my_znn 1081 $HOME/DockerMV/znn_sample_rule.txt alirezagoli/znn-text:v1 1 1g 1g 0.2 alirezagoli/znn-multimedia:v1 1 1g 1g 0.2``

6. Run the following command to identify the ports associated with each version that has been launched: `sudo docker container ls`. The output should look similar to the image below.

![image](https://github.com/prabjot09/multiversioning-dynamic-load-balancing/assets/77180065/e0fd7aa3-7089-4f65-a492-f80dd1ae41be)

7. Note the port of the heavy-weight version underlined in blue (let's call this 'PORT_H') and note the port of the light-weight version underlined in green (let's call this 'PORT_L').
8. Switch the current working directory to the root directory of this repository. Then, open the file `conf/nginx.conf`
9. Edit the `upstream` block in the file to correctly configure the load balancer by following the given format and replace the parameters <...> with information specific for you (pt=500 is recommended). Further guidance for this can be found [here](#lb-config).
    
``
upstream backend {
    server <HOST_IP>:<PORT_H> weight=2 pt=<user_defined_performance_target>;
    server <HOST_IP>:<PORT_L> weight=7;
}
``

10. Inside the `server` block change the number listed beside `listen` to the port that you want the load balancer to run on (This port must not be already in use). Let's call this port `LB_PORT`
11. Save the file and use the following command to apply the configuration: `sudo cp ./conf/nginx.conf /etc/nginx/nginx.conf`
12. Run the load balancer with the command: `sudo nginx`. If the service is already running, then use `sudo nginx -s reload` to restart it.
13. Now you can use a load testing application by sending requests to `http://<HOST_IP>:<LB_PORT>/news.php`. A guide on load testing with the JMeter application is given [here](#jmeter).

<a name="teastore"/>

## Testing with Teastore Recommender Service
**Note**: This experiment requires the installation of Docker which is part of the setup for DockerMV. Although DockerMV is not required for this test, please follow the steps in the "How to Use?" section of the README file in DockerMV which outlines how to install Docker. The README file can be found in the `DockerMV_SaraGholami` folder in the root directory of this repo.

This service has 2 versions: 
1. `teastore-recommender:SingleTrain`: This version runs the training algorithm for product recommendation just once. This reduces the accuracy of the predictions, but lightens the load on the service.
2. `teastore-recommender:MultipleTrain`: This version runs the training algorithm for product recommendations periodically, which increases prediction accuracy, but places a larger load on the service.

The steps to execute the tests are as follows:
1. Ensure that Docker has been installed on the system. If not, refer to the **Note** at the beginning of this section.
2. Since the teastore application is made of many individual microservices, we need to launch all associated services, not just the product recommendation service. To launch all the required services run the following commands (replace <HOST_IP> with the IP address of the host system that the service is deployed on which can be found by running this command: `hostname -I | awk '{print $1}`). For further details on how these commands work and any manual adjustments you'd like to make refer to the Teastore application documentation [here](https://github.com/DescartesResearch/TeaStore/blob/master/GET_STARTED.md#11-run-as-multiple-single-service-containers):
   1. ``sudo docker run -e "HOST_NAME=<HOST_IP>" -e "SERVICE_PORT=10000" -p 10000:8080 -d descartesresearch/teastore-registry``
   2. ``sudo docker run -p 3306:3306 -d descartesresearch/teastore-db``
   3. ``sudo docker run -e "REGISTRY_HOST=<HOST_IP>" -e "REGISTRY_PORT=10000" -e "HOST_NAME=<HOST_IP>" -e "SERVICE_PORT=1111" -e "DB_HOST=<HOST_IP>" -e "DB_PORT=3306" -p 1111:8080 -d descartesresearch/teastore-persistence``
   4. ``sudo docker run -e "REGISTRY_HOST=<HOST_IP>" -e "REGISTRY_PORT=10000" -e "HOST_NAME=<HOST_IP>" -e "SERVICE_PORT=2222" -p 2222:8080 -d descartesresearch/teastore-auth``
   5. ``sudo docker run -e "REGISTRY_HOST=<HOST_IP>" -e "REGISTRY_PORT=10000" -e "HOST_NAME=<HOST_IP>" -e "SERVICE_PORT=4444" -p 4444:8080 -d descartesresearch/teastore-image``
   6. ``sudo docker run -e "REGISTRY_HOST=<HOST_IP>" -e "REGISTRY_PORT=10000" -e "HOST_NAME=<HOST_IP>" -e "SERVICE_PORT=8080" -p 8080:8080 -d descartesresearch/teastore-webui``
  **Note**: [Changing Hosts] You may launch these services on different devices/hosts, but ensure that the <HOST_IP> matches the IP of the device the service is launched for.
  **Note2**: [Changing Port 1] You may change the port for the 1st service, however you must change the `REGISTRY_PORT` of services (3)-(6) to match this change.
  **Note3**: [Changing Port 2] You may change the port for the 2nd service, however you must change the `DB_PORT` of service (3) to match the change.
  **Note4**: [Changing ANY Port] You may change the port for any service, however you must update the `SERVICE_PORT` of the same service to match the port specified after the `-p` option.
  3. Choose a port that is currently unused by the host. If in the later steps you find that the port is in use, please restart from this step. We will refer to this port as <LB_PORT>. 
  4. Launch the 2 versions of the recommender service with the following commands. <PORT1> and <PORT2> must not be already in use. Please ensure that the `REGISTRY_HOST` and `REGISTRY_PORT` match those in step (2):
     1. ``sudo docker run -e "REGISTRY_HOST=<HOST_IP> -e "REGISTRY_PORT=10000 -e "HOST_NAME=<HOST_IP> -e "SERVICE_PORT=<LB_PORT>" -p <PORT1>:8080 -d sgholami/teastore-recommender:SingleTrain``
     2. ``sudo docker run -e "REGISTRY_HOST=<HOST_IP> -e "REGISTRY_PORT=10000 -e "HOST_NAME=<HOST_IP> -e "SERVICE_PORT=<LB_PORT>" -p <PORT2>:8080 -d sgholami/teastore-recommender:MultipleTrain``
  5. Switch the current working directory to the root directory of this repository. Then, open the file `conf/nginx.conf`
  6. Edit the `upstream` block in the file to correctly configure the load balancer by following the given format and replace the parameters <...> with information specific for you (pt=50 is recommended). Further guidance for this can be found [here](#lb-config).
    
``
upstream backend {
    server <HOST_IP>:<PORT2> weight=2 pt=<user_defined_performance_target>;
    server <HOST_IP>:<PORT1> weight=7;
}
``

10. Inside the `server` block change the number listed beside `listen` to <LB_PORT>
11. Save the file and use the following command to apply the configuration: `sudo cp ./conf/nginx.conf /etc/nginx/nginx.conf`
12. Run the load balancer with the command: `sudo nginx`. If the service is already running, then use `sudo nginx -s reload` to restart it.
13. Test that the service is running correctly by going to the UI for the service at `http://<HOST_IP>:<WEBUI_PORT>` and clicking on Server Status. The <WEBUI_PORT> is the port used in step (2.6) which should be 8080 if you have used the same setup in the instructions.
14. Now you can use a load testing application by sending various requests to `http://<HOST_IP>:<WEBUI_PORT>`. There is a lot more content and complexity involved with the Teastore service, since the recommender service is used by the system, but isn't directly accessible to the user. For this reason, we recommend sticking with the load testing scheme that has been provided using JMeter. A guide on load testing with the JMeter application is given [here](#jmeter).

<a name="jmeter"/>

## Load Testing with JMeter
JMeter is an application that uses Java 8 to simulate loads on servers. The following are the steps to set up JMeter.
1. Install Java 8+ on the host that you want to run JMeter on. This does not necessarily need to be the same host where the services to be tested are launched.
2. Install Apache JMeter from an archive of their releases. We used Apache JMeter 5.5 however more recent releases should work fine as well. The releases can be found [here](https://archive.apache.org/dist/jmeter/binaries/) and download the .zip file of your preferred release. The release for JMeter 5.5 is found [here](https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-5.5.zip). In the case that these links become obsolete, please go to the official site of Apache JMeter and try to find the 'Download Releases' section where you may find instructions to help you.
3. Extract the contents of the .zip file to your preferred directory.
4. Install the JMeter plugins manager by following the instructions [here](https://jmeter-plugins.org/install/Install/). The restart is not required since we haven't started JMeter yet.
5. Open a terminal and navigate to the root directory of the extracted contents which should be called `apache-jmeter-<version>`.
6. Navigate to the /bin folder and execute the command to launch the load testing UI: ``./jmeter``
7. Once JMeter is launched, on the navigation bar at the top select File->Open.
8. Now find the .jmx file you want to use to perform the load test. There are 2 default test files you can download that are provided in the root directory of DockerMV for each of the tested services. The ZNN test file can be found [here](https://github.com/pacslab/DockerMV/blob/master/znn.jmx) and the Teastore test file can be found [here](https://github.com/pacslab/DockerMV/blob/master/teastore.jmx).
9. Ensure that the host and ports for the test case are set to the match the service you'd like to test. In the case of the ZNN service requests should be sent to `http://<HOST_IP>:<LB_PORT>`. In the case of the Teastore service requests should be sent to `http://<HOST_IP>:<WEBUI_PORT>`
   1. If using the **znn.jmx** test file, using the navigation panel on the left, navigate to 'Test Plan' -> 'Threads' -> 'HTTP Request' to configure the IP address and Port Number. Navigate to 'Test Plan' -> 'Threads' to configure the amount of load and the duration of the load tests.
   2. If using the **teastore.jmx** test file, using the navigation panel on the left, navigate to 'Teastore' and set all relevant parameters in the `User Defined Variables` selection on the right.
10. Save the file after making all the necessary changes and close (not minimize) the UI.
11. From the same terminal as before run the following command to execute the load tests. Any path and file/folder name will work as long as the directory specified in the path exists, however the name and path of <TEST_FILE> must be the same as the file edited in step (8) :

``./jmeter -n -t ./<path-to-file>/<TEST_FILE>.jmx -l ./<path-to-file>/<file_name>.csv -e -o ./<path-to-folder>/<results folder>``

11. The results of the test will be output in the terminal as it executes. To run an additional script to see how the load balancer is distributing requests, refer to this [section](#utilization).
12. To view the results in visual form, navigate to the folder specified in step (10) and open the index.html file. Results of particular interest can be found under the 'Charts->Over Time' section and particular from the 'Response Time Percentiles Over Time (successful responses)' graph.

___
<a name="close"/>

# Shutdown and Cleanup
1. To close all active docker containers that have been launched use the command: `sudo docker container ls -aq | xargs sudo docker stop | xargs sudo docker rm`.
2. To close a specific docker container follow these steps:
   1. Use the command `sudo docker container ls`. Find the container you'd like to shutdown from the names in the `IMAGES` column, and copy its hash in the `CONTAINER ID` column. Let's call this <CONTAINER_ID>.
   2. Run this command to pause the container: `sudo docker stop <CONTAINER_ID>`.
   3. Run this command to delete the container: `sudo docker rm <CONTAINER_ID>`.
3. Run this command to stop the load balancer: `sudo nginx -s stop`.


