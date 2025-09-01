#!/bin/bash

set -euo pipefail

# Resolve the script path even if it's a symlink
get_script_dir() {
    local src="${BASH_SOURCE[0]}"
    while [ -h "$src" ]; do
        local dir
        dir="$(cd -P "$(dirname "$src")" >/dev/null 2>&1 && pwd)"
        src="$(readlink "$src")"
        [[ "$src" != /* ]] && src="$dir/$src"
    done
    cd -P "$(dirname "$src")" >/dev/null 2>&1 && pwd
}

SCRIPT_DIR="$(get_script_dir)"

purge_repos_master() {
    for repo in "$@" ; do
        echo "Purging repo: $repo"
        $SCRIPT_DIR/gh-purge-deleted-branch-workflows.sh "X11Libre/$repo"
        $SCRIPT_DIR/gh-purge-pipelines.sh --org X11Libre --repo $repo --branch master --keep 3
    done
}

purge_repos_master \
    xserver \
    xf86-video-amdgpu

XSERVER_CLEAN_BRANCHES="
    master
    maint-25.0
    release/25.0
    release/25.1
    wip/swapping_new
    rfc/new-abi-25.1
    wip/cleanup
    wip/requests
    wip/xinerama-walkScreen
"

for branch in $XSERVER_CLEAN_BRANCHES ; do
    echo "Purging X11Libre/xserver branch $branch"
    $SCRIPT_DIR/gh-purge-pipelines.sh --org X11Libre --repo xserver --branch $branch --keep 3 || true
done
