#!/bin/bash

set -e

GITHUB_ORG="X11Libre"
REPO_PREFIX="mirror."
TEMPDIR=".tmp"

if [ "$GH_TOKEN" ]; then
    MIRROR_PREFIX="https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_ORG}/${REPO_PREFIX}"
else
    MIRROR_PREFIX="git@github.com:${GITHUB_ORG}/${REPO_PREFIX}"
fi

update_mirror() {
    local name="$1"
    local upstream="$2"
    local repo_name="${REPO_PREFIX}${name}"
    local repo_fqn="${GITHUB_ORG}/${repo_name}"

    if gh repo view "${repo_fqn}" >/dev/null 2>&1; then
        echo "repo ${repo_fqn} already exists"
    else
        gh repo create \
            ${repo_fqn} \
            --public \
            --description "Read-only mirror for CI. No issues or PRs accepted" \
            --disable-issues \
            --disable-wiki \
            --homepage "${upstream}"
    fi

    mkdir -p "$TEMPDIR"
    ( \
        cd "$TEMPDIR"
        git clone --mirror "${upstream}" "${name}.git"
        cd $name.git
        git remote add mirror "${MIRROR_PREFIX}$name.git"
        git push --tags mirror
        git push mirror `git for-each-ref refs/heads --format "%(refname:short)"`
    )
}

update_mirror_fdo() {
    update_mirror "fdo.$1" "https://gitlab.freedesktop.org/$2"
}

rm -Rf "${TEMPDIR}"

FDO="https://gitlab.freedesktop.org"

update_mirror_fdo xset          xorg/app/xset
update_mirror_fdo xorg-macros   xorg/util/macros
update_mirror_fdo pixman        pixman/pixman.git
update_mirror_fdo pthread-stubs xorg/lib/pthread-stubs.git
update_mirror_fdo xcbproto      xorg/proto/xcbproto.git
update_mirror_fdo libX11        xorg/lib/libX11.git
update_mirror_fdo libXau        xorg/lib/libXau.git
update_mirror_fdo libxkbfile    xorg/lib/libxkbfile.git
update_mirror_fdo font-util     xorg/font/util.git
update_mirror_fdo libfontenc    xorg/lib/libfontenc.git
update_mirror_fdo libXfont      xorg/lib/libXfont.git
update_mirror_fdo libXdmcp      xorg/lib/libXdmcp.git
update_mirror_fdo libXfixes     xorg/lib/libXfixes.git
update_mirror_fdo libxcb        xorg/lib/libxcb.git
update_mirror_fdo libxcb-util   xorg/lib/libxcb-util.git
update_mirror_fdo libxcb-image  xorg/lib/libxcb-image.git
update_mirror_fdo libxcb-wm     xorg/lib/libxcb-wm.git
update_mirror_fdo libxcb-keysyms        xorg/lib/libxcb-keysyms.git
update_mirror_fdo libxcb-render-util    xorg/lib/libxcb-render-util.git
update_mirror_fdo libxtrans     xorg/lib/libxtrans
update_mirror_fdo drm           mesa/drm
update_mirror_fdo libxcvt       xorg/lib/libxcvt.git
update_mirror_fdo xorgproto     xorg/proto/xorgproto.git
update_mirror_fdo piglit        mesa/piglit.git
update_mirror_fdo xts           xorg/test/xts
update_mirror_fdo rendercheck   xorg/test/rendercheck
update_mirror_fdo freetype      freetype/freetype
