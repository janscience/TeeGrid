base=ducke2026

# make directories:
echo "make directories ..."
for path in $(find $base -type d); do
    dest="${base}-compressed${path#$base}"
    test -d "$dest" && continue
    echo "$path -> $dest"
    mkdir -p "$dest"
done

# copy and compress files:
echo "compress files ..."
for name in $(find $base -type f); do
    dest="${base}-compressed${name#ducke2026}"
    if test "${dest##*.}" = "wav"; then
	dest="${dest%wav}wv"
	test -f "$dest" && continue
	test -s "$name" || continue
	echo "$name -> $dest"
	wavpack -q -f -t "$name" -o "$dest"
    else
	test -f "$dest" && continue
	echo "$name -> $dest"
	cp -a "$name" "$dest"
    fi
    chmod a-wx "$dest"
done

# compute overview for audian:
function compute () {
    local org_dir="$PWD"
    cd "$1"
    if test $(ls *.wv 2> /dev/null | wc -l) -gt 0; then
	echo "compute overview for $(ls *.wv | wc -l) wv files in $1 ..."
	if test $(ls *-fulltrace.wav 2> /dev/null | wc -l) -eq 0; then
	    audian-compress *.wv
	fi
    fi
    for subdir in */; do
	test -d "$subdir" && compute $subdir
    done
    cd "$org_dir"
}

echo "compute overview ..."
compute "${base}-compressed"
echo "DONE"
