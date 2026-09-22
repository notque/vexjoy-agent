#!/bin/bash
#
# VexJoy Agent installer: a thin wrapper around the vexinstall engine
# (scripts/vexinstall). The engine installs every runtime (claude, codex,
# factory, hermes, reasonix), keeps a ledger in ~/.claude/vexjoy/, and moves
# anything it removes to ~/.claude/vexjoy/trash/. Layout: docs/installer-layout.md.
#
# Usage:
#   ./install.sh                     # apply (symlink mode for a main checkout, else copy)
#   ./install.sh --symlink|--copy    # choose the mode (recorded in the ledger)
#   ./install.sh --dry-run           # show the plan; write nothing
#   ./install.sh --uninstall         # remove every engine-owned entry (to trash)
#   ./install.sh --rollback          # restore the newest settings backup and trash session
#   ./install.sh --migrate-overlays  # write ~/.claude/vexjoy/overlays.json, then exit
#   ./install.sh --help
#
# Env: VEXJOY_NO_GIT_HOOKS=1 skips .git/hooks; VEXJOY_NO_DEPS=1 skips pip and npm.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${HOME}/.claude"
STATE_DIR="${CLAUDE_DIR}/vexjoy"
RUNTIMES=(codex factory hermes reasonix)

MODE=""
ACTION="apply"
DRY_RUN=false
TAKEOVER=true
TARGET="all"
CONFIGURE=false
CONFIGURE_ONLY=false
EXTRA=()

usage() {
    cat << 'EOF'
Usage: ./install.sh [options]

  --symlink            Link entries to this checkout (default for a main git checkout)
  --copy               Copy entries (default for worktrees and /tmp checkouts)
  --dry-run            Print the vexinstall plan; write nothing
  --uninstall          Move every engine-owned entry to trash; remove owned settings hooks
  --rollback           Restore the newest settings.json backup and the newest trash session
  --target T           claude|codex|factory|hermes|reasonix|all (default: all present)
  --no-takeover        Leave unowned entries at desired paths in place (default: trash and replace)
  --allow-mass-remove  Allow a plan that removes more than 10 entries or 20% of a target
  --configure          Run the interactive profile picker, then install
  --configure-only     Run the picker, write .local/profile.yaml, then exit
  --migrate-overlays   Write ~/.claude/vexjoy/overlays.json from the legacy private roots, then exit
  --force, --no-force, --per-item, --sync
                       Deprecated; accepted and ignored (the engine never prompts)
EOF
}

deprecated() {
    echo -e "${YELLOW}Note: $1 is deprecated and ignored; vexinstall is always non-interactive and per-entry.${NC}"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --symlink) MODE="symlink" ;;
        --copy) MODE="copy" ;;
        --uninstall) ACTION="uninstall" ;;
        --rollback) ACTION="rollback" ;;
        --migrate-overlays) ACTION="migrate-overlays" ;;
        --dry-run) DRY_RUN=true ;;
        --target)
            [[ $# -ge 2 ]] || { echo -e "${RED}--target needs a value${NC}"; exit 2; }
            TARGET=$2
            shift
            ;;
        --no-takeover) TAKEOVER=false ;;
        --allow-mass-remove) EXTRA+=(--allow-mass-remove) ;;
        --configure) CONFIGURE=true ;;
        --configure-only) CONFIGURE_ONLY=true ;;
        --force|-f|--no-force|--per-item|--sync) deprecated "$1" ;;
        --help|-h) usage; exit 0 ;;
        *) echo -e "${RED}Unknown option: $1${NC}"; usage; exit 1 ;;
    esac
    shift
done

check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        echo -e "${RED}Error: Python 3.10+ not found${NC}"
        exit 1
    fi
    if ! "$PYTHON_CMD" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
        echo -e "${RED}Error: Python 3.10+ required, found $("$PYTHON_CMD" -V 2>&1)${NC}"
        exit 1
    fi
}

vexinstall() {
    PYTHONPATH="${SCRIPT_DIR}/scripts${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_CMD" -m vexinstall "$@" \
        --source-root "$SCRIPT_DIR"
}

# newest_ts GLOB PREFIX SUFFIX: newest engine timestamp among matching names (empty if none).
newest_ts() {
    local dir=$1 prefix=$2 suffix=$3 name best=""
    [ -d "$dir" ] || return 0
    for name in $(ls -1 "$dir" 2>/dev/null); do
        name=${name#"$prefix"}
        name=${name%"$suffix"}
        [[ $name =~ ^[0-9]{8}T[0-9]{12}Z$ ]] || continue
        [[ $name > $best ]] && best=$name
    done
    printf '%s' "$best"
}

rollback() {
    local ts rc=0
    ts=$(newest_ts "${STATE_DIR}/backups" "settings." ".json")
    if [ -n "$ts" ]; then
        echo -e "${YELLOW}Restoring settings.json backup ${ts}...${NC}"
        [ "$DRY_RUN" = true ] || vexinstall restore-settings "$ts" || rc=$?
    else
        echo -e "${YELLOW}No settings backup in ${STATE_DIR}/backups${NC}"
    fi
    ts=$(newest_ts "${STATE_DIR}/trash" "" "")
    if [ -n "$ts" ]; then
        echo -e "${YELLOW}Restoring trash session ${ts}...${NC}"
        [ "$DRY_RUN" = true ] || vexinstall restore-trash "$ts" || rc=$?
    else
        echo -e "${YELLOW}No trash session in ${STATE_DIR}/trash${NC}"
    fi
    return "$rc"
}

# A runtime whose CLI is on PATH gets its root dir, so `--target all` installs it.
ensure_runtime_dirs() {
    local rt
    for rt in "${RUNTIMES[@]}"; do
        if command -v "$rt" &> /dev/null && [ ! -d "${HOME}/.${rt}" ]; then
            if [ "$DRY_RUN" = true ]; then
                echo -e "${BLUE}  Would create ${HOME}/.${rt} (${rt} is on PATH)${NC}"
            else
                mkdir -p "${HOME}/.${rt}"
            fi
        fi
    done
}

_write_git_hook() {
    local name=$1 hook="${SCRIPT_DIR}/.git/hooks/$1" body
    body=$(cat)
    if [ -e "$hook" ] && ! grep -q "Written by vexjoy-agent" "$hook" 2>/dev/null; then
        echo -e "${YELLOW}  Existing ${name} hook found; not overwriting: ${hook}${NC}"
        return 0
    fi
    mkdir -p "${SCRIPT_DIR}/.git/hooks"
    printf '%s\n' "$body" > "$hook"
    chmod +x "$hook"
    echo -e "${GREEN}  ✓ Installed ${name} hook${NC}"
}

# post-merge: engine sync after git pull. pre-commit: private-leak gate (spec 7.5).
install_git_hooks() {
    [ -d "${SCRIPT_DIR}/.git" ] || return 0
    [ "${VEXJOY_NO_GIT_HOOKS:-0}" = "1" ] && return 0
    _write_git_hook post-merge << 'HOOK'
#!/usr/bin/env bash
# Written by vexjoy-agent install.sh: syncs runtime installs after git pull.
# Never links anything itself (installer spec 5.1). Always exits 0.
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
command -v python3 >/dev/null 2>&1 || exit 0
PYTHONPATH="$REPO_DIR/scripts${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -m vexinstall sync --target all --source-root "$REPO_DIR" </dev/null || true
exit 0
HOOK
    _write_git_hook pre-commit << 'HOOK'
#!/usr/bin/env bash
# Written by vexjoy-agent install.sh: private-leak gate (installer spec 7.5).
# Blocks a commit when a tracked file carries a private overlay skill name or
# overlay file content. Reports paths and matched names only, never contents.
# Exit 2 from the checker (bad overlays.json) warns and allows the commit.
REPO_DIR="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
[ -f "$REPO_DIR/scripts/check-private-leak.py" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0
python3 "$REPO_DIR/scripts/check-private-leak.py" --repo "$REPO_DIR"
rc=$?
if [ "$rc" -eq 1 ]; then
  echo "[vexjoy-agent] commit blocked: private overlay data in tracked files (see LEAK lines above)" >&2
  exit 1
fi
[ "$rc" -eq 0 ] || echo "[vexjoy-agent] check-private-leak exited $rc; commit allowed" >&2
exit 0
HOOK
}

install_deps() {
    [ "${VEXJOY_NO_DEPS:-0}" = "1" ] && return 0
    local -a pip=("$PYTHON_CMD" -m pip) args=(install -r "${SCRIPT_DIR}/requirements.txt" --quiet)
    if "${pip[@]}" install --help 2>/dev/null | grep -q -- "--break-system-packages"; then
        args+=(--break-system-packages)
    fi
    if "${pip[@]}" "${args[@]}" 2>/dev/null || "${pip[@]}" "${args[@]}" --user 2>/dev/null; then
        echo -e "${GREEN}  ✓ Python dependencies installed${NC}"
    else
        echo -e "${YELLOW}  ⚠ Could not install Python dependencies. Run: ${pip[*]} ${args[*]}${NC}"
    fi
    # Vercel Jev gateway: the repo plus every real (copied) scripts dir.
    command -v npm &> /dev/null || { echo -e "${YELLOW}  ⚠ npm unavailable; /d falls back to /do${NC}"; return 0; }
    local dir real seen=" "
    for dir in "${SCRIPT_DIR}/scripts" "${CLAUDE_DIR}/scripts" "${HOME}/.codex/scripts" "${HOME}/.factory/scripts" \
        "${HOME}/.hermes/scripts" "${HOME}/.reasonix/scripts"; do
        dir="${dir}/jev_gateway"
        [ -f "$dir/package-lock.json" ] || continue
        real=$(cd "$dir" && pwd -P)
        [[ $seen == *" $real "* ]] && continue
        seen="${seen}${real} "
        (cd "$dir" && npm ci --ignore-scripts --no-audit --no-fund --silent) \
            && echo -e "${GREEN}  ✓ Gateway dependencies in ${dir}${NC}" \
            || echo -e "${YELLOW}  ⚠ Gateway dependencies failed in ${dir}; /d falls back to /do${NC}"
    done
}

# ADR-122: runtime state readable by the owner only.
harden_permissions() {
    chmod 700 "${CLAUDE_DIR}" "${CLAUDE_DIR}/learning" 2>/dev/null || true
    chmod 600 "${CLAUDE_DIR}/settings.json" "${CLAUDE_DIR}/history.jsonl" 2>/dev/null || true
    chmod 600 "${HOME}/.factory/settings.json" "${HOME}/.reasonix/settings.json" 2>/dev/null || true
}

check_python

if [ "$ACTION" = "migrate-overlays" ]; then
    args=(migrate-overlays)
    [ "$DRY_RUN" = true ] && args+=(--dry-run)
    vexinstall "${args[@]}"
    exit $?
fi

if [ "$ACTION" = "uninstall" ]; then
    args=(uninstall --target "$TARGET")
    [ "$DRY_RUN" = true ] && args+=(--dry-run)
    vexinstall "${args[@]}"
    exit $?
fi

if [ "$ACTION" = "rollback" ]; then
    rollback
    exit $?
fi

if [ "$CONFIGURE" = true ] || [ "$CONFIGURE_ONLY" = true ]; then
    PROFILE_FILE="${VEXJOY_INSTALL_PROFILE:-${SCRIPT_DIR}/.local/profile.yaml}"
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}Would run the profile picker (scripts/configure-profile.py)${NC}"
    else
        "$PYTHON_CMD" "${SCRIPT_DIR}/scripts/configure-profile.py" --output "$PROFILE_FILE"
    fi
    if [ "$CONFIGURE_ONLY" = true ]; then
        echo "Profile written. Run ./install.sh to apply it."
        exit 0
    fi
fi

ensure_runtime_dirs
args=(--target "$TARGET")
[ -n "$MODE" ] && args+=(--mode "$MODE")
[ "$TAKEOVER" = true ] && args+=(--takeover)
args+=(${EXTRA[@]+"${EXTRA[@]}"})

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}vexinstall plan (dry run; nothing is written)${NC}"
    vexinstall plan --dry-run "${args[@]}"
    exit $?
fi

echo -e "${YELLOW}vexinstall apply ${args[*]}${NC}"
rc=0
vexinstall apply "${args[@]}" || rc=$?
if [ "$rc" -ne 0 ]; then
    echo -e "${RED}vexinstall apply failed (exit ${rc}). Nothing was forced. Review:${NC}"
    echo -e "${RED}  PYTHONPATH=${SCRIPT_DIR}/scripts python3 -m vexinstall plan --target ${TARGET} --takeover${NC}"
    exit "$rc"
fi
install_git_hooks
install_deps
harden_permissions
echo -e "${GREEN}✓ Installed. Check with: PYTHONPATH=${SCRIPT_DIR}/scripts python3 -m vexinstall doctor${NC}"
