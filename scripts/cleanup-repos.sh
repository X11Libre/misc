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

purge_repo_xserver() {
    local repo="xserver"
    echo "Purging repo: $repo"
    $SCRIPT_DIR/gh-purge-deleted-branch-workflows.sh "X11Libre/$repo"
    for branch in master release/25.0 release/25.1 ; do
        $SCRIPT_DIR/gh-purge-pipelines.sh --org X11Libre --repo $repo --branch $branch --keep 1
    done
}

INPUT_DRIVERS="elographics evdev joystick keyboard libinput mouse synaptics vmmouse void wacom"
VIDEO_DRIVERS="
    amdgpu apm ark ast ati chips cirrus dummy fbdev freedreno geode i128 i740
    intel mach64 mga neomagic nested nouveau nv omap qxl r128 rendition s3virge
    savage siliconmotion sis sisusb suncg14 suncg3 suncg6 sunffb sunleo suntcx
    tdfx trident v4l vbox vesa vmware voodoo wsfb xgi"

driver_repos() {
    for i in $INPUT_DRIVERS ; do
        echo -n "xf86-input-$i "
    done
    for i in $VIDEO_DRIVERS ; do
        echo -n "xf86-video-$i "
    done
}

purge_repo_xserver
purge_repos_master $(driver_repos)

exit

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
