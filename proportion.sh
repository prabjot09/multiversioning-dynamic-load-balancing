#!/bin/sh
# This is a comment!

echo "" > /var/log/nginx/access.log
echo "" > /var/log/nginx/usage.csv

while [ : ]
do 
    sleep 10
    h=$(cat /var/log/nginx/access.log | grep v:4 | wc -l)
    l=$(cat /var/log/nginx/access.log | grep v:2 | wc -l)
    total=$(expr $h + $l)
    
    if [ "$total" -eq 0 ]
    then 
        total=1
    fi
    
    h_100=$(expr $h \* 100)
    perc=$(expr $h_100 / $total)
    now=$(date +"%T")
    echo -e "[$now] \t heavy: $h   \t light: $l    \t\t % heavy:$perc"
    echo "$now,$perc" >> /var/log/nginx/usage.csv
    
    echo "" > /var/log/nginx/access.log
    
done

