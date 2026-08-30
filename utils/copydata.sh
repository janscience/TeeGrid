#!/bin/bash

echo "Available SD cards and data:"
for disk in /media/$USER/*; do
    test "${PWD:0:${#disk}}" = "$disk" && continue
    diskname=${disk#/media/$USER/}
    test "${diskname:0:1}" = "d" && continue
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

mode="w"
logfile="$PWD/copydata-problems.log"
: > "$logfile"
#echo
#echo "Use"
#echo "[r] rsync (no compression)"
#echo "[w] wavpack (wav-file compression)"
#echo "Select "
#read mode
#test "$mode" != "r" && test "$mode" != "g" && test "$mode" != "w" && exit 1

echo

start_time="$(date -u +%s)"
for disk in /media/$USER/*; do
    test "${PWD:0:${#disk}}" = "$disk" && continue
    diskname=${disk#/media/$USER/}
    test "${diskname:0:1}" = "d" && continue
    if test "$mode" = "r"; then
	echo "copy $disk/* using rsync ..."
    elif test "$mode" = "w"; then
	echo "copy $disk/* using wavpack ..."
    fi
    {
	for path in $disk/*; do
	    if test -d "$path"; then
		destpath=${path#$disk/}
		site=${destpath%%-*}
		grid=${destpath#$site-}
		grid=${grid%%-*}
		destpath="$site/$grid/$destpath"
		mkdir -p $destpath
		if test "$mode" = "r"; then
		    rsync -av $path $destpath
		elif test "$mode" = "w"; then
		    cp -a --update=none $path/*.csv $destpath
		    cp -a --update=none $path/*.yml $destpath
		    for wavfile in $path/*.wav; do
			destfile=${wavfile##*/}
			destfile=${destfile/.wav/.wv}
			if test -s "$wavfile" && ! test -s $destpath/${destfile}; then
			    if wavpack -q -f -t $wavfile -o $destpath/${destfile}.part; then
				mv $destpath/${destfile}.part $destpath/${destfile}
			    else
				rm -f $destpath/${destfile}.part
				echo "FAILED $wavfile" >> "$logfile"
			    fi
			fi
		    done
		fi
		chmod a-w $destpath/*
		chmod a+r $destpath/*
		chmod a+rw $destpath
	    fi
	done
    } &
done
wait
end_time="$(date -u +%s)"
elapsed="$(($end_time-$start_time))"

echo
if test -s "$logfile"; then
    echo "!!! $(wc -l < "$logfile") files were NOT copied:"
    cat "$logfile"
    echo
    echo "finished in ${elapsed}s WITH PROBLEMS, see $logfile"
    exit 1
fi
rm -f "$logfile"
echo "finished copying in ${elapsed}s!"

## TODO
# do not copy 0byte files
# naming: siteXX-gridYY-devID2-TIME
# sort into directory structure siteX/gridY/timeZ/*.wav

# 1 SD card slot to internal harddrive: rsync 86 MB/s
# 1 SD card slot to internal harddrive: gzip 6 MB/s
# 1 SD card slot to internal harddrive: wavpack 50 MB/s

# 1 SD card USB to internal harddrive: rsync 154 MB/s  100%
# 1 SD card USB to internal harddrive: gzip 12 MB/s
# 1 SD card USB to internal harddrive: wavpack 52 MB/s  21%

# 4 SD card USB to internal harddrive: rsync   328 MB/s  100%
# 4 SD card USB to internal harddrive: wavpack 125 MB/s   20%

# 4 SD card USB to USB harddrive: rsync      222 MB/s  100%
# 4 SD card USB to USB harddrive: wavpack    106 MB/s   20%
# 4 SD card USB to USB harddrive: wavpack -f 130 MB/s   23%  <--!!!

# 4 x 265GB/2day = 8155s = 2.5hours !
# 25logger * 133GB/day@48kHz * 12Tage = 40TB uncompressed = 10TB compressed
