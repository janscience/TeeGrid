#base=ducke2026
base=suriname
src=/media/benda/eeldata/$base
dest=/media/benda/data3/efish/fielddata/$base
dry_run=false
compress_args="-f 50 -l 3000"


# make directories:
function make-directories () {
echo "make directories ..."
for path in $(find $src -type d); do
    dest_path="${dest}${path#$src}"
    test -d "$dest_path" && continue
    echo "$path -> $dest_path"
    $dry_run || mkdir -p "$dest_path"
done
echo


# copy and compress files:
function copy-compress () {
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

    
# compute full trace for audian:
function compute-fulltrace () {
    local org_dir="$PWD"
    cd "$1"
    if test $(ls *.wv 2> /dev/null | wc -l) -gt 0; then
	echo "compute full trace for $(ls *.wv | wc -l) wv files in $1 ..."
	if test $(ls *-fulltrace.wav 2> /dev/null | wc -l) -eq 0; then
	    $dry_run || audian-compress ${compress_args} *.wv
	fi
    fi
    for subdir in */; do
	test -d "$subdir" && compute-fulltrace $subdir
    done
    cd "$org_dir"
}


# main script:
make-directories
copy-compress
echo "compute full traces ..."
compute-fulltrace "$dest"
echo "DONE"
