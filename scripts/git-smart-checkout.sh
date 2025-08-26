#!/usr/bin/env bash
# git-smart-checkout: Clone/Reuse a repo and force-checkout a given ref (branch/tag/commit),
#                     with mirror URLs, minimal transfer, and automatic retries.

# Robustness
set -euo pipefail
IFS=$'\n\t'

# ---- Logging helpers --------------------------------------------------------
log_info()  { printf '[INFO] %s\n' "$*" >&2; }
log_warn()  { printf '[WARN] %s\n' "$*" >&2; }
log_error() { printf '[ERROR] %s\n' "$*" >&2; }

# ---- Usage ------------------------------------------------------------------
usage() {
    cat >&2 <<'USAGE'
Usage:
  git-smart-checkout.sh -n <local-dir> -r <ref|commit> -u <url> [-u <url2> ...] [options]

Required:
  -n, --name <dir>         Lokales Zielverzeichnis (Repo-Name / Pfad).
  -r, --ref  <ref>         Branch, Tag oder Commit-SHA.
  -u, --url  <url>         Mindestens eine Repo-URL (weitere für Mirror-Fallback wiederholen).

Options:
      --retries <N>        Anzahl der Versuche pro Netzoperation (default: 3).
      --sleep   <SEC>      Wartezeit zwischen Versuchen in Sekunden (default: 3).
      --no-clean           Arbeitsverzeichnis nach Checkout NICHT hart bereinigen.
      --full-if-needed     Falls Commit mit shallow fetch nicht erreichbar ist, ohne --depth erneut versuchen.
      --keep-remote        Remote-Config nicht verändern (ansonsten wird 'origin' auf die erste URL gesetzt).
      --depth <N>          Shallow-Depth für Fetch (default: 1). Nur für Branch/Tag sinnvoll.
      --no-partial         Partial clone/filter deaktivieren (lädt sonst blobs on-demand).
      --no-tags            Tags standardmäßig NICHT holen (default). Entfernen, um Tags zu erlauben.
      --allow-tags         Tags mit holen (überschreibt --no-tags).

Notes:
- Minimaler Transfer: --filter=blob:none, --no-tags und gezielte Refspecs.
- Für spezifische Commits wird zunächst shallow versucht; ggf. mit --full-if-needed erneut ohne --depth.
- Checkout erfolgt standardmäßig detached auf die exakt gefetchte Commit-ID (robust bei Branch/Tag-Änderungen).

Beispiele:
  # Branch minimal holen (aus Mirrors), forciert auschecken:
  git-smart-checkout.sh -n myrepo -r main -u https://github.com/org/proj.git -u https://gitmirror/org/proj.git

  # Tag auschecken:
  git-smart-checkout.sh -n myrepo -r v2.1.0 -u ssh://git@example.com/proj.git

  # Bestimmte Commit-SHA (fällt bei Bedarf auf non-shallow zurück):
  git-smart-checkout.sh -n myrepo -r 1a2b3c4d5e --full-if-needed -u https://github.com/org/proj.git
USAGE
    exit 2
}

# ---- Defaults ---------------------------------------------------------------
NAME=""
REF=""
URLS=()
RETRIES=3
SLEEP_SEC=3
CLEAN=1
FULL_IF_NEEDED=0
KEEP_REMOTE=0
DEPTH=1
USE_PARTIAL=1
FETCH_TAGS=0   # 0 => --no-tags, 1 => allow tags

# ---- Parse args -------------------------------------------------------------
if [[ $# -eq 0 ]]; then usage; fi

while (( "$#" )); do
    case "$1" in
        -n|--name)        NAME="${2:-}"; shift 2 ;;
        -r|--ref)         REF="${2:-}"; shift 2 ;;
        -u|--url)         URLS+=("${2:-}"); shift 2 ;;
        --retries)        RETRIES="${2:-}"; shift 2 ;;
        --sleep)          SLEEP_SEC="${2:-}"; shift 2 ;;
        --no-clean)       CLEAN=0; shift ;;
        --full-if-needed) FULL_IF_NEEDED=1; shift ;;
        --keep-remote)    KEEP_REMOTE=1; shift ;;
        --depth)          DEPTH="${2:-}"; shift 2 ;;
        --no-partial)     USE_PARTIAL=0; shift ;;
        --no-tags)        FETCH_TAGS=0; shift ;;
        --allow-tags)     FETCH_TAGS=1; shift ;;
        -h|--help)        usage ;;
        *) log_error "Unknown option: $1"; usage ;;
    esac
done

# ---- Validate args ----------------------------------------------------------
if [[ -z "$NAME" ]]; then log_error "Missing --name"; usage; fi
if [[ -z "$REF"  ]]; then log_error "Missing --ref";  usage; fi
if [[ ${#URLS[@]} -eq 0 ]]; then log_error "At least one --url is required"; usage; fi
if ! command -v git >/dev/null 2>&1; then log_error "'git' nicht gefunden"; exit 127; fi

# ---- Helpers ----------------------------------------------------------------
is_git_dir() {
    [[ -d "$1/.git" ]] || git -C "$1" rev-parse --git-dir >/dev/null 2>&1
}

is_sha_like() {
    [[ "$1" =~ ^[0-9a-fA-F]{7,40}$ ]]
}

sleep_backoff() {
    local attempt="$1"
    local base="$SLEEP_SEC"
    local delay=$(( base * attempt ))
    [[ $delay -lt 1 ]] && delay=1
    sleep "$delay"
}

git_retry() {
    # git_retry <desc> <cmd...>
    local desc="$1"; shift
    local attempt=1
    local rc=0
    while :; do
        if "$@"; then
            return 0
        fi
        rc=$?
        if (( attempt >= RETRIES )); then
            log_error "$desc: fehlgeschlagen nach $RETRIES Versuchen (rc=$rc)"
            return "$rc"
        fi
        log_warn "$desc: Versuch $attempt fehlgeschlagen (rc=$rc). Erneuter Versuch..."
        sleep_backoff "$attempt"
        attempt=$(( attempt + 1 ))
    done
}

# Compose common fetch flags
fetch_flags_common=()
(( USE_PARTIAL )) && fetch_flags_common+=( "--filter=blob:none" )
(( FETCH_TAGS == 0 )) && fetch_flags_common+=( "--no-tags" )
fetch_flags_common+=( "--prune" "--prune-tags" "--update-head-ok" "--force" )

# With or without depth
fetch_flags_shallow=( "${fetch_flags_common[@]}" "--depth=$DEPTH" )
fetch_flags_full=( "${fetch_flags_common[@]}" )

# ---- Clone or reuse existing ------------------------------------------------
if [[ -d "$NAME" ]]; then
    if is_git_dir "$NAME"; then
        log_info "Bestehendes Git-Repo erkannt: $NAME"
        if (( KEEP_REMOTE == 0 )); then
            log_info "Setze 'origin' auf erste URL: ${URLS[0]}"
            if git -C "$NAME" remote get-url origin >/dev/null 2>&1; then
                git -C "$NAME" remote set-url origin "${URLS[0]}"
            else
                git -C "$NAME" remote add origin "${URLS[0]}"
            fi
        else
            log_info "--keep-remote: Remote-Konfiguration unverändert."
        fi
    else
        log_error "Verzeichnis '$NAME' existiert, ist aber kein Git-Repo."
        exit 1
    fi
else
    # Frisches Clone: minimal & no-checkout
    mkdir -p "$(dirname -- "$NAME")"
    clone_ok=0
    for u in "${URLS[@]}"; do
        log_info "Clone von $u -> $NAME (minimaler Transfer, no-checkout)"
        clone_cmd=( git clone "--no-checkout" "--origin=origin" "$u" "$NAME" )
        (( USE_PARTIAL )) && clone_cmd+=( "--filter=blob:none" )
        (( FETCH_TAGS == 0 )) && clone_cmd+=( "--no-tags" )
        if git_retry "clone $u" "${clone_cmd[@]}"; then
            clone_ok=1
            break
        fi
    done
    if (( clone_ok == 0 )); then
        log_error "Clone von allen URLs fehlgeschlagen."
        exit 1
    fi
fi

# ---- Prepare partial clone config (for init/clone without --filter at fetch time) ----
if (( USE_PARTIAL )); then
    # Best effort: ensure repo knows it's a partial clone (helps späteres lazy-fetch)
    git -C "$NAME" config --local remote.origin.promisor true || true
    git -C "$NAME" config --local remote.origin.partialclonefilter "blob:none" || true
    git -C "$NAME" config --local extensions.partialClone "origin" || true
fi

# ---- Fetch target ref with minimal transfer ---------------------------------
# We'll try URLs in order; for each, attempt specific refspecs.
# Strategy:
#  - If SHA-like: try shallow fetch of the object; fallback to full if enabled.
#  - Else (name): try heads/<REF>, tags/<REF>, and plain <REF> shallow; fallback to full if needed.
enter_repo() { cd "$NAME"; } # for readability
enter_repo

fetch_from_url_for_ref() {
    # fetch_from_url_for_ref <url> <ref> <shallow_or_full>
    local url="$1" ref="$2" mode="$3" ; shift 3
    local -a flags=()
    if [[ "$mode" == "shallow" ]]; then
        flags=( "${fetch_flags_shallow[@]}" )
    else
        flags( "${fetch_flags_full[@]}" )
    fi

    if is_sha_like "$ref"; then
        # Try fetching the specific commit object
        # FETCH_HEAD will point to the fetched object on success.
        git_retry "fetch $url commit $ref ($mode)" \
            git fetch "${flags[@]}" "$url" "$ref"
        return $?
    else
        # Try specific namespaces to avoid extra refs
        local try=(
            "refs/heads/$ref:refs/tmp/$ref"
            "refs/tags/$ref:refs/tmp/$ref"
            "$ref:refs/tmp/$ref"
        )
        local t
        for t in "${try[@]}"; do
            if git_retry "fetch $url $t ($mode)" git fetch "${flags[@]}" "$url" "$t"; then
                return 0
            fi
        done
        return 1
    fi
}

fetch_ok=0
for u in "${URLS[@]}"; do
    # 1) Try shallow
    if fetch_from_url_for_ref "$u" "$REF" "shallow"; then
        fetch_ok=1
        break
    fi
    # 2) Optional fallback to full (still filtered blobs)
    if (( FULL_IF_NEEDED )); then
        log_warn "Shallow-Fetch nicht ausreichend. Versuche ohne --depth von $u ..."
        if fetch_from_url_for_ref "$u" "$REF" "full"; then
            fetch_ok=1
            break
        fi
    fi
done

if (( fetch_ok == 0 )); then
    log_error "Fetch der Referenz '$REF' aus allen URLs fehlgeschlagen."
    exit 1
fi

# Resolve fetched commit
TARGET_COMMIT="$(git rev-parse --verify --quiet FETCH_HEAD || true)"
if [[ -z "$TARGET_COMMIT" ]]; then
    log_error "FETCH_HEAD konnte nicht aufgelöst werden."
    exit 1
fi
log_info "Gefetched: $TARGET_COMMIT"

# ---- Forced checkout --------------------------------------------------------
# We checkout detached at the exact commit to be fully deterministic.
# (No implicit branch tracking; avoids surprises if remote refs move.)
if (( CLEAN )); then
    log_info "Bereinige Arbeitsverzeichnis (reset --hard, clean -fdx)"
    git reset --hard
    git clean -fdx
fi

log_info "Forciere Checkout (detached) auf $TARGET_COMMIT"
# Ensure no stray temp ref prevents checkout
git update-ref -d "refs/tmp/$REF" >/dev/null 2>&1 || true
git checkout --force --detach "$TARGET_COMMIT"

# Small summary
log_info "Arbeitsstatus:"
git --no-pager log -1 --oneline
git --no-pager status --short --branch

log_info "Fertig."
