#!/bin/sh
# This is a comment!

rm ~/Res/test_parse1.csv

cd /home/ubuntu/jmeter/apache-jmeter-5.5/bin & ./jmeter -n -t ~/DockerMV/demo.jmx -l ~/Res/test_parse1.csv & \
    cd ~/multiversioning-dynamic-load-balancing & sudo python3 microservices.py e SERVICE_PORT=3333 192.168.23.237 my-net my_znn 1081 alirezagoli/znn-text:v1 1g 1g 0.2 light alirezagoli/znn-multimedia:v1 1g 1g 0.2 heavy pt=1000 max=2 & sudo python3 parse_rt.py && kill $!
