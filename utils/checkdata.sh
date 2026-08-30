#!/bin/bash

# Compare the mounted SD cards against the archive.
# Run it in the archive directory with the cards still plugged in.
# Only file names are read, no audio, so it takes seconds.
# Says "archive matches the cards." and exits 0 if everything is there.

problems=0
for disk in /media/$USER/*; do
    test "${PWD:0:${#disk}}" = "$disk" && continue
    diskname=${disk#/media/$USER/}
    test "${diskname:0:1}" = "d" && continue
    for path in "$disk"/*; do
	test -d "$path" || continue
	session=${path#$disk/}
	# where copydata.sh would have put it
	dst=""
	if [[ $session =~ ^([^-]+)-([^-]+)-[^-]+-[0-9]{8}T[0-9]{4,6} ]]; then
	    test -d "${BASH_REMATCH[1]}/${BASH_REMATCH[2]}/$session" &&
		dst="${BASH_REMATCH[1]}/${BASH_REMATCH[2]}/$session"
	fi
	test -z "$dst" && test -d "$session" && dst="$session"
	test -z "$dst" && dst=$(find . -type d -name "$session" -print -quit)
	if test -z "$dst"; then
	    n=$(ls -1 "$path" | wc -l)
	    echo "MISSING $session (whole session, $n files)"
	    problems=$((problems+n))
	    continue
	fi
	for wavfile in "$path"/*.wav; do
	    test -s "$wavfile" || continue    # empty files are skipped on purpose
	    destfile=${wavfile##*/}
	    destfile=${destfile%.wav}.wv
	    if ! test -s "$dst/$destfile"; then
		echo "MISSING $session/$destfile"
		problems=$((problems+1))
	    fi
	done
	for extra in "$path"/*.csv "$path"/*.yml; do
	    test -f "$extra" || continue
	    if ! test -e "$dst/${extra##*/}"; then
		echo "MISSING $session/${extra##*/}"
		problems=$((problems+1))
	    fi
	done
    done
done

echo
if test $problems -gt 0; then
    echo "$problems files are on a card but not in the archive."
    exit 1
fi
echo "archive matches the cards."
