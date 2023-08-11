#!/bin/sh
# This is a comment!

#echo "" > /var/log/nginx/access.log
echo "" > /var/log/nginx/usage.csv

first=1

old_h=$(cat /var/log/nginx/access.log | grep v:4 | wc -l)
old_l=$(cat /var/log/nginx/access.log | grep v:2 | wc -l)

while [ : ]
do 
    sleep 10
    tot_h=$(cat /var/log/nginx/access.log | grep v:4 | wc -l)
    tot_l=$(cat /var/log/nginx/access.log | grep v:2 | wc -l)
    
    h=$(expr $tot_h - $old_h)
    l=$(expr $tot_l - $old_l)
    total=$(expr $h + $l)
    
    if [ "$total" -eq 0 ]
    then 
        total=1
    fi
    
    h_100=$(expr $h \* 100)
    perc=$(expr $h_100 / $total)
    now=$(date +"%T")
    echo -e "[$now] \t heavy: $h   \t light: $l    \t\t % heavy:$perc"
    
    if [ "$first" -eq 1 ]
    then
        echo "$now,$h,$l,$perc" > /var/log/nginx/usage.csv
        first=0
    fi
    
    if [ "$first" -eq 0 ]
    then
        echo "$now,$h,$l,$perc" >> /var/log/nginx/usage.csv
    fi
    
    old_h=$tot_h
    old_l=$tot_l
    #echo "" > /var/log/nginx/access.log
    
done

