#!/bin/sh
# This is a comment!

nginx
python3 ./nginx-dynamic/monitoring_server.py &&
sh proportion.sh 
tail -f /dev/null
