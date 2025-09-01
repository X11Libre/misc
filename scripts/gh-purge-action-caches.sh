#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 owner/repo"
    exit 1
}

if [[ $# -ne 1 ]]; then
    usage
fi

REPO="$1"

log_info()  { echo "[INFO] $*"; }
log_warn()  { echo "[WARN] $*"; }
log_error() { echo "[ERROR] $*" >&2; }

# Check GitHub CLI
if ! command -v gh >/dev/null 2>&1; then
    log_error "GitHub CLI (gh) not found"
    exit 2
fi
if ! gh auth status >/dev/null 2>&1; then
    log_error "GitHub CLI not authenticated. Run: gh auth login"
    exit 3
fi

log_info "Fetching all cache pages for $REPO ..."

# Use jq -s to slurp multiple JSON documents into one array
gh api "/repos/$REPO/actions/caches?per_page=100" --paginate \
  | jq -s '[.[] | .actions_caches[]]' \
  | while read -r line; do :; done # dummy to avoid subshell bug

# Now extract IDs line by line
gh api "/repos/$REPO/actions/caches?per_page=100" --paginate \
  | jq -s '[.[] | .actions_caches[]] | .[].id' \
  | while read -r id; do
      log_info "Deleting cache $id"
      if gh api --method DELETE "/repos/$REPO/actions/caches/$id" >/dev/null 2>&1; then
          log_info "Deleted cache $id"
      else
          log_warn "Failed to delete cache $id"
      fi
  done

log_info "All cache deletion attempts completed."
