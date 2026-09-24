#base=ducke2026
base=suriname
src=/media/benda/eeldata/$base
dest=/media/benda/data3/efish/fielddata/$base
dry_run=false

# make directories:
echo "make directories ..."
for path in $(find $src -type d); do
    dest_path="${dest}${path#$src}"
    test -d "$dest_path" && continue
    echo "$path -> $dest_path"
    $dry_run || mkdir -p "$dest_path"
done
echo

# copy and compress files:
echo "compress files ..."
for name in $(find $src -type f); do
    dest_file="${dest}${name#$src}"
    if test "${dest_file##*.}" = "wav"; then
	dest_file="${dest_file%wav}wv"
	test -f "$dest_file" && continue
	test -s "$name" || continue
	echo "$name -> $dest_file"
	$dry_run || wavpack -q -f -t "$name" -o "$dest_file"
    else
	test -f "$dest_file" && continue
	echo "$name -> $dest_file"
	$dry_run || cp -a "$name" "$dest_file"
    fi
    $dry_run || chmod a-wx "$dest_file"
done
echo

# compute overview for audian:
function compute () {
    local org_dir="$PWD"
    cd "$1"
    if test $(ls *.wv 2> /dev/null | wc -l) -gt 0; then
	echo "compute overview for $(ls *.wv | wc -l) wv files in $1 ..."
	if test $(ls *-fulltrace.wav 2> /dev/null | wc -l) -eq 0; then
	    $dry_run || audian-compress *.wv
	fi
    fi
    for subdir in */; do
	test -d "$subdir" && compute $subdir
    done
    cd "$org_dir"
}

echo "compute overview ..."
compute "$dest"
echo "DONE"
