#!/usr/bin/env bash

set -euo pipefail

usage() {
    echo "Usage: $0 [-n] [-r dir] [-e ext1,ext2,...] [file1 file2 ...]"
    echo
    echo "Options:"
    echo "  -n           Dry run (show what would change without modifying files)"
    echo "  -r DIR       Recursively process all files under directory"
    echo "  -e EXTLIST   Comma-separated list of file extensions to include (e.g. c,h,cpp,py)"
    exit 1
}

log_info() { echo "[INFO] $*"; }
log_warn() { echo "[WARN] $*"; }
log_error() { echo "[ERROR] $*" >&2; }

dry_run=false
recurse_dir=""
filter_exts=()

while getopts ":nr:e:" opt; do
    case $opt in
        n) dry_run=true ;;
        r) recurse_dir="$OPTARG" ;;
        e) IFS=',' read -r -a filter_exts <<< "$OPTARG" ;;
        *) usage ;;
    esac
done
shift $((OPTIND-1))

if [[ $# -eq 0 && -z "$recurse_dir" ]]; then
    usage
fi

if ! command -v sed >/dev/null 2>&1; then
    log_error "sed not found in PATH"
    exit 2
fi
if ! command -v awk >/dev/null 2>&1; then
    log_error "awk not found in PATH"
    exit 2
fi

files=("$@")

if [[ -n "$recurse_dir" ]]; then
    if [[ ! -d "$recurse_dir" ]]; then
        log_error "Directory does not exist: $recurse_dir"
        exit 3
    fi
    while IFS= read -r -d '' f; do
        # Skip hidden files and files in hidden directories
        relpath="${f#$recurse_dir/}"
        if [[ "$relpath" == .* || "$relpath" == */.* ]]; then
            continue
        fi

        if [[ ${#filter_exts[@]} -eq 0 ]]; then
            files+=("$f")
        else
            for ext in "${filter_exts[@]}"; do
                if [[ "$f" == *".$ext" ]]; then
                    files+=("$f")
                    break
                fi
            done
        fi
    done < <(find "$recurse_dir" -type f -print0)
fi

for file in "${files[@]}"; do
    if [[ ! -f "$file" ]]; then
        log_warn "Skipping non-existent file: $file"
        continue
    fi

    if [[ ${#filter_exts[@]} -gt 0 ]]; then
        match=false
        for ext in "${filter_exts[@]}"; do
            if [[ "$file" == *".$ext" ]]; then
                match=true
                break
            fi
        done
        if [[ $match == false ]]; then
            log_info "Skipping $file (not matching extensions)"
            continue
        fi
    fi

    log_info "Processing $file"

    tmpfile=$(mktemp)
    trap 'rm -f "$tmpfile" "$tmpfile.fixed"' EXIT

    # Remove trailing whitespace and collapse multiple blank lines
    sed \
        -e 's/[ \t]\+$//' \
        -e '/^$/N;/^\n$/D' \
        -e ':a; /^\n*$/{$d;N;ba; }' \
        "$file" > "$tmpfile"

    # Ensure exactly one final newline using awk
    awk 'NF || NR==1{print prev} {prev=$0} END{print $0}' "$tmpfile" > "$tmpfile.fixed"
    mv "$tmpfile.fixed" "$tmpfile"

    if ! cmp -s "$file" "$tmpfile"; then
        if $dry_run; then
            log_info "Whitespace issues found in $file"
        else
            cp "$tmpfile" "$file"
            log_info "Fixed whitespace in $file"
        fi
    else
        log_info "No changes needed for $file"
    fi

    rm -f "$tmpfile"
    trap - EXIT
done
