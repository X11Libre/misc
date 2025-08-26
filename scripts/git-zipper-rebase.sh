#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage:"
    echo "  git zipper-rebase <target>"
    echo "  git zipper-rebase --continue"
    echo "  git zipper-rebase --abort"
    echo "  git zipper-rebase --dry-run"
    echo "  git zipper-rebase --skip"
    exit 1
}

log_info() { echo "[INFO] $*"; }
log_warn() { echo "[WARN] $*" >&2; }
log_error() { echo "[ERROR] $*" >&2; }

# --- Prüfen ob wir in einem Git-Repo sind ---
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    log_error "Not inside a git repository"
    exit 10
fi

GIT_DIR=$(git rev-parse --git-dir)
STATE_FILE="$GIT_DIR/rebase-zipper"
LOCK_FILE="$GIT_DIR/rebase-zipper.lock"

acquire_lock() {
    if [[ -f "$LOCK_FILE" ]]; then
        log_error "Lockfile exists: $LOCK_FILE"
        echo "Another zipper-rebase may be running (PID: $(cat "$LOCK_FILE" 2>/dev/null))"
        exit 11
    fi
    echo $$ >"$LOCK_FILE"
    trap 'rm -f "$LOCK_FILE"' EXIT INT TERM
}

release_lock() {
    rm -f "$LOCK_FILE"
    trap - EXIT INT TERM
}

cmd=${1:-}
shift || true

case "$cmd" in
    --abort)
        acquire_lock
        if git rebase --abort 2>/dev/null; then
            log_info "git rebase aborted"
        fi
        rm -f "$STATE_FILE"
        release_lock
        log_info "State + lock removed"
        exit 0
        ;;
    --continue)
        acquire_lock
        if ! git rebase --continue; then
            log_warn "Conflict not resolved yet"
            release_lock
            exit 2
        fi
        ;;
    --skip)
        acquire_lock
        if ! git rebase --skip; then
            log_warn "Could not skip commit"
            release_lock
            exit 3
        fi
        ;;
    --dry-run)
        DRYRUN=1
        ;;
    "")
        usage
        ;;
    *)
        TARGET=$cmd
        ;;
esac

BRANCH=$(git rev-parse --abbrev-ref HEAD)
TARGET=${TARGET:-origin/main}

acquire_lock

if [[ ! -f "$STATE_FILE" ]]; then
    BASE=$(git merge-base "$BRANCH" "$TARGET")
    X=$(git rev-list --count "${BASE}..${TARGET}")
    {
        echo "BASE=$BASE"
        echo "X=$X"
        echo "TARGET=$TARGET"
    } >"$STATE_FILE"
fi

source "$STATE_FILE"

if [[ ${X:-0} -eq 0 ]]; then
    log_info "Branch already up-to-date with $TARGET"
    rm -f "$STATE_FILE"
    release_lock
    exit 0
fi

while [[ $X -gt 0 ]]; do
    NEXT=$(( X - 1 ))
    TARGET_COMMIT=$(git rev-parse "${TARGET}~${NEXT}")
    log_info ">>> Rebasing onto $TARGET_COMMIT ($TARGET~$NEXT)"

    if [[ "${DRYRUN:-0}" -eq 1 ]]; then
        X=$NEXT
        continue
    fi

    if ! git rebase --onto "$TARGET_COMMIT" "$BASE" "$BRANCH"; then
        log_warn "Conflict. Run 'git zipper-rebase --continue' after resolving."
        release_lock
        exit 4
    fi

    BASE="$TARGET_COMMIT"
    X=$NEXT

    {
        echo "BASE=$BASE"
        echo "X=$X"
        echo "TARGET=$TARGET"
    } >"$STATE_FILE"
done

rm -f "$STATE_FILE"
release_lock
log_info "Rebase complete!"
