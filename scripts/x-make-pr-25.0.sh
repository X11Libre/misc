#!/usr/bin/env bash
set -euo pipefail

### CONFIGURATION
UPSTREAM_REMOTE="origin"
UPSTREAM_BRANCH="release/25.0"
UPSTREAM_REF="$UPSTREAM_REMOTE/$UPSTREAM_BRANCH"
DEFAULT_MODE="rebase"
REVIEWERS="X11Libre/dev"
MILESTONE="25.0.x bugfix"

### HELP
if [[ $# -lt 1 ]]; then
  cat <<EOF
Usage: $(basename "$0") [options] <commit> [<commit> ...]

Options:
  --rebase            Use rebase mode (markers added to PR branch, then incubator rebased).
  --branch <name>     Explicitly set PR branch name instead of auto-generating it.

Arguments:
  One or more commit SHAs (not necessarily consecutive) to include in the PR.

EOF
  exit 1
fi

### PARSE OPTIONS
MODE="$DEFAULT_MODE"
BRANCH_NAME=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rebase)
      MODE="rebase"
      shift
      ;;
    --branch)
      BRANCH_NAME="$2"
      shift 2
      ;;
    *)
      COMMITS+=("$1")
      shift
      ;;
  esac
done

if [[ ${#COMMITS[@]} -eq 0 ]]; then
  echo "Error: At least one commit must be specified." >&2
  exit 1
fi

### SAVE CURRENT BRANCH
INCUBATOR_BRANCH=$(git rev-parse --abbrev-ref HEAD)

### DETERMINE BRANCH NAME
if [[ -z "$BRANCH_NAME" ]]; then
  FIRST_SUBJECT=$(git log -1 --pretty=%s "${COMMITS[0]}")
  BRANCH_NAME=$(echo "$FIRST_SUBJECT" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-')
  BRANCH_NAME="pr/25.0/${BRANCH_NAME}_$(date +%Y-%m-%d_%H-%M-%S)"
fi

TMP_BRANCH="tmp-${BRANCH_NAME}"

echo "Mode: $MODE"
echo "Incubator: $INCUBATOR_BRANCH"
echo "New PR branch: $BRANCH_NAME"
echo "Commits: ${COMMITS[*]}"

### CREATE TEMP BRANCH FOR PR
git fetch origin
git checkout -b "$TMP_BRANCH" "$UPSTREAM_REF"

# Cherry-pick commits
for c in "${COMMITS[@]}"; do
  if ! git cherry-pick "$c"; then
    echo "Cherry-pick of $c failed. Please resolve manually!" >&2
    exit 1
  fi
done

# Rename to final branch
git branch -M "$BRANCH_NAME"

# Push it to github
git push "$UPSTREAM_REMOTE" "$BRANCH_NAME"

### CREATE PR
if [[ ${#COMMITS[@]} -eq 1 ]]; then
  gh pr create -m "$MILESTONE" -a "@me" --fill -B "$UPSTREAM_BRANCH" -H "$BRANCH_NAME" --reviewer "$REVIEWERS"
else
  TMP_FILE=$(mktemp)
  echo "# Pull Request description (edit below, lines starting with # are ignored)" > "$TMP_FILE"
  echo "" >> "$TMP_FILE"
  git log --format='%h %s' "${COMMITS[@]}" >> "$TMP_FILE"
  ${EDITOR:-vi} "$TMP_FILE"
  gh pr create -m "$MILESTONE" -a "@me" --title "PR: ${COMMITS[*]}" --body-file "$TMP_FILE" -B "$UPSTREAM_BRANCH" -H "$BRANCH_NAME" --reviewer "$REVIEWERS"
  rm -f "$TMP_FILE"
fi

PR_URL=$(gh pr view --json url -q .url "$BRANCH_NAME")
PR_NUMBER=$(echo "$PR_URL" | grep -o '[0-9]*$')

### HANDLE MARKERS
if [[ "$MODE" == "incubator" ]]; then
  # Rewrite incubator branch directly
  git checkout "$INCUBATOR_BRANCH"
  for c in "${COMMITS[@]}"; do
    git rebase -i --autosquash --keep-empty --exec "
      git commit --amend -m \"[PR #$PR_NUMBER] $(git log -1 --pretty=%s)\" \
      --trailer \"PR: $PR_URL\""
  done
else
  # Rebase incubator onto PR branch (markers first in PR branch)
  git checkout "$BRANCH_NAME"
  for c in "${COMMITS[@]}"; do
    git commit --amend -m "[PR #$PR_NUMBER] $(git log -1 --pretty=%s)" \
      --trailer "PR: $PR_URL"
  done
  git checkout "$INCUBATOR_BRANCH"
  git rebase "$BRANCH_NAME"
fi

### RESTORE
git checkout "$INCUBATOR_BRANCH"
git branch -D "$BRANCH_NAME"

echo "Done. PR created: $PR_URL"
