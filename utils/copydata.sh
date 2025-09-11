#!/bin/bash

echo "Available SD cards and data:"
for disk in /media/$USER/*; do
    echo
    echo "$disk :"
    for data in $disk/*; do
	ndata=$(ls -1 $data | wc -l)
	echo "  ${data#$disk/}: $ndata files"
    done
done

echo
echo -n "copy all data to $PWD? [Y/n] "
read resp
test -z "$resp" && resp='y'

test "$resp" != "y" && exit 1
echo

start_time="$(date -u +%s)"
for disk in /media/$USER/*; do
    echo "copy $disk ..."
    rsync -av $disk/* . &
done
wait
end_time="$(date -u +%s)"
elapsed="$(($end_time-$start_time))"

echo
echo "finished copying in ${elapsed}s!"

# 4 SD cards:  0.37GB/s
# 1 SD card:   0.18GB/s



