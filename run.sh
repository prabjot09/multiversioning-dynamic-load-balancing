#!/bin/sh
# This is a comment!

nginx & sh ./nginx-dynamic/proportion.sh & python3 ./nginx-dynamic/monitoring_server.py & tail -f /dev/null
