#!/bin/bash
#
# VexJoy Agent installer: a thin wrapper around the vexinstall engine
# (scripts/vexinstall). The engine installs every runtime (claude, codex,
# factory, hermes, reasonix, antigravity), keeps a ledger in ~/.claude/vexjoy/, and moves
# anything it removes to ~/.claude/vexjoy/trash/. Layout: docs/installer-layout.md.
#
# Usage:
#   ./install.sh                     # apply (symlink mode for a main checkout off Windows, else copy)
#   ./install.sh --symlink|--copy    # choose the mode (recorded in the ledger)
#   ./install.sh --dry-run           # show the plan; write nothing
#   ./install.sh --uninstall         # remove every engine-owned entry (to trash); with no --target
#                                    # or --target claude, also rename install.sh's post-merge hook
#                                    # so git skips it
#   ./install.sh --rollback          # undo the last run: restore what it trashed and its settings backup
#   ./install.sh --migrate-overlays  # write ~/.claude/vexjoy/overlays.json, then exit
#                                    # (apply runs it when overlays.json is missing and
#                                    # ~/private-skills or ~/pgh/private-skills exists)
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
# One id per run: the engine groups this run's apply and prune (or uninstall) into the
# rollback point that --rollback restores.
RUN_ID="install-$(date -u +%Y%m%dT%H%M%SZ)-$$"

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

  --symlink            Link entries to this checkout (default for a main git checkout off Windows)
  --copy               Copy entries (default on Windows and for worktrees and /tmp checkouts)
  --dry-run            Print the vexinstall plan; write nothing
  --uninstall          Move every engine-owned entry to trash; remove owned settings hooks.
                       With no --target or --target claude, also rename install.sh's post-merge
                       git hook so git skips it (it reinstalls on pull). The pre-commit
                       private-leak gate stays.
  --rollback           Undo the last install or uninstall run: restore what it moved to trash
                       and the settings.json it replaced (later syncs are left alone)
  --target T           claude|codex|factory|hermes|reasonix|antigravity|all (default: all present)
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
    # Run the engine with a python 3.10+. A bare python3 can be a pyenv shim that picks 3.9
    # in some dirs, or /usr/bin/python3 3.9 on macOS, so try the known locations too.
    # The engine separately links ~/.claude/vexjoy/bin/python3 for hooks (VEXJOY_PYTHON overrides).
    local cand
    PYTHON_CMD=""
    if [[ -n "${VEXJOY_PYTHON:-}" ]]; then
        if "$VEXJOY_PYTHON" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2> /dev/null; then
            PYTHON_CMD="$VEXJOY_PYTHON"
            return
        fi
        echo -e "${RED}Error: VEXJOY_PYTHON=${VEXJOY_PYTHON} is not a runnable python 3.10+${NC}"
        exit 1
    fi
    for cand in python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3 \
        python3.14 python3.13 python3.12 python3.11 python3.10 python; do
        command -v "$cand" &> /dev/null || continue
        if "$cand" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2> /dev/null; then
            PYTHON_CMD="$cand"
            return
        fi
    done
    echo -e "${RED}Error: Python 3.10+ not found (python3 is $(python3 -V 2>&1 || echo missing)); install it or set VEXJOY_PYTHON=/path/to/python3${NC}"
    exit 1
}

vexinstall() {
    PYTHONPATH="${SCRIPT_DIR}/scripts${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_CMD" -m vexinstall "$@" \
        --source-root "$SCRIPT_DIR"
}

# The engine restores the rollback point that this script's last apply and prune (or uninstall)
# recorded: every trash session of that run and the settings.json backup it took. The newest
# trash session and backup on disk are often a later sync's, so they are never picked by date.
# Undoing an uninstall also writes back the post-merge hook that the uninstall removed. The engine
# prints its "[rollback] run <id> (...)" line only for a run it has rolled back and marked done, so
# the hook comes back on exit 1 too (a trash session or backup was gone): no later --rollback could.
rollback() {
    local -a args=(rollback)
    local out rc=0
    [ "$DRY_RUN" = true ] && args+=(--dry-run)
    out=$(vexinstall "${args[@]}") || rc=$?
    [ -z "$out" ] || printf '%s\n' "$out"
    # Only the first line: a later "skipped: <path>" line may hold any text.
    if [ "$DRY_RUN" = false ] && [[ ${out%%$'\n'*} == "[rollback] run "*" (uninstall)" ]]; then
        install_git_hooks
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
    if { command -v agy &> /dev/null || command -v antigravity &> /dev/null; } && [ ! -d "${HOME}/.gemini" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would create ${HOME}/.gemini (agy is on PATH)${NC}"
        else
            mkdir -p "${HOME}/.gemini"
        fi
    fi
}

_write_git_hook() {
    local name=$1 hook="${SCRIPT_DIR}/.git/hooks/$1" body
    body=$(cat)
    if [ -e "$hook" ] && ! grep -q "Written by vexjoy-agent" "$hook" 2>/dev/null; then
        echo -e "${YELLOW}  Existing ${name} hook found; not overwriting: ${hook}${NC}"
        return 0
    fi
    # A failed write warns and lets the install go on: the hooks run before apply.
    if mkdir -p "${SCRIPT_DIR}/.git/hooks" && printf '%s\n' "$body" > "$hook" && chmod +x "$hook"; then
        echo -e "${GREEN}  ✓ Installed ${name} hook${NC}"
    else
        echo -e "${YELLOW}  ⚠ Could not write ${name} hook: ${hook}${NC}"
    fi
}

# post-merge: engine sync after git pull. pre-commit: private-leak gate (spec 7.5).
install_git_hooks() {
    [ "${VEXJOY_NO_GIT_HOOKS:-0}" = "1" ] && return 0
    if [ -f "${SCRIPT_DIR}/.git" ]; then
        echo -e "${YELLOW}  Git hooks skipped: ${SCRIPT_DIR}/.git is a file (worktree or submodule); ./install.sh in the main checkout writes them${NC}"
        return 0
    fi
    [ -d "${SCRIPT_DIR}/.git" ] || return 0
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

# main_hooks_dir: the dir install.sh writes hooks to, <main checkout>/.git/hooks. From a linked worktree
# it asks git for the main .git, since git runs the main checkout's hooks for merges in every worktree.
# Prints nothing without .git or for a submodule (install.sh never writes hooks there). Fails when
# .git is a file git cannot read.
main_hooks_dir() {
    local common
    if [ -d "${SCRIPT_DIR}/.git" ]; then
        printf '%s\n' "${SCRIPT_DIR}/.git/hooks"
    elif [ -f "${SCRIPT_DIR}/.git" ]; then
        common=$(git -C "$SCRIPT_DIR" rev-parse --git-common-dir 2> /dev/null) && [ -n "$common" ] \
            && common=$(cd "$SCRIPT_DIR" && cd "$common" && pwd) || return 1
        [ "${common##*/}" != ".git" ] || printf '%s\n' "${common}/hooks"
    fi
}

# Uninstall without --target (or with --target claude) renames our post-merge to
# post-merge.vexjoy-removed.<UTC time>, which git never runs. The engine records uninstalled targets and
# `sync` skips them, but a pre-engine hook's `ln -s` loop, or an engine from a clone older than that
# record, would re-install everything on the next pull. Another --target uninstall keeps it: its sync
# skips the uninstalled target and keeps claude and the rest current.
# The pre-commit private-leak gate stays: it installs nothing.
# When a marked post-merge may still run, GIT_HOOK_PROBLEM says why, and the uninstall exits 1.
uninstall_git_hooks() {
    local dir name hook ts
    if [ "${VEXJOY_NO_GIT_HOOKS:-0}" = "1" ]; then
        echo -e "${YELLOW}  Git hooks skipped (VEXJOY_NO_GIT_HOOKS=1)${NC}"
        return 0
    fi
    if ! dir=$(main_hooks_dir); then
        GIT_HOOK_PROBLEM="Git hooks not checked: git cannot read ${SCRIPT_DIR}/.git; run ./install.sh --uninstall in the main checkout too"
        echo -e "${YELLOW}  ⚠ ${GIT_HOOK_PROBLEM}${NC}"
        return 0
    fi
    ts=$(date -u +%Y%m%dT%H%M%SZ)
    [ -n "$dir" ] || return 0
    for name in post-merge pre-commit; do
        hook="${dir}/${name}"
        [ -e "$hook" ] || continue
        if ! grep -q "Written by vexjoy-agent" "$hook" 2> /dev/null; then
            echo -e "  Keeping ${name} hook (not written by vexjoy-agent): ${hook}"
        elif [ "$name" = pre-commit ]; then
            echo -e "  Keeping pre-commit hook (the private-leak gate installs nothing; delete it to stop the check): ${hook}"
        elif [ "$TARGET" != all ] && [ "$TARGET" != claude ]; then
            echo -e "${YELLOW}  Keeping post-merge hook (a --target uninstall keeps it; its sync skips the uninstalled target and updates the rest): ${hook}${NC}"
        elif [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would rename post-merge hook to ${hook}.vexjoy-removed.${ts}${NC}"
        elif mv -f "$hook" "${hook}.vexjoy-removed.${ts}"; then
            echo -e "${GREEN}  ✓ Renamed post-merge hook to ${hook}.vexjoy-removed.${ts}; git does not run it${NC}"
        else
            GIT_HOOK_PROBLEM="${hook} is still in place: delete it, or the next pull re-installs everything"
            echo -e "${YELLOW}  ⚠ Could not rename post-merge hook: ${hook}${NC}"
        fi
    done
}

# pip_requirements PYTHON: install requirements.txt into PYTHON; --break-system-packages when pip knows
# it, then --user as a fallback. Prints the manual command on failure.
pip_requirements() {
    local -a pip=("$1" -m pip) args=(install -r "${SCRIPT_DIR}/requirements.txt" --quiet)
    if "${pip[@]}" install --help 2>/dev/null | grep -q -- "--break-system-packages"; then
        args+=(--break-system-packages)
    fi
    if "${pip[@]}" "${args[@]}" 2>/dev/null || "${pip[@]}" "${args[@]}" --user 2>/dev/null; then
        echo -e "${GREEN}  ✓ Python dependencies installed for $1${NC}"
    else
        echo -e "${YELLOW}  ⚠ Could not install Python dependencies for $1. Hooks and scripts need them. Run: ${pip[*]} ${args[*]}${NC}"
    fi
}

# Hooks run under the interpreter linked at ~/.claude/vexjoy/bin/python3 (chosen by the engine during
# apply), which can differ from PYTHON_CMD. Install deps there too, so call this after apply.
install_deps() {
    [ "${VEXJOY_NO_DEPS:-0}" = "1" ] && return 0
    pip_requirements "$PYTHON_CMD"
    local linked="${HOME}/.claude/vexjoy/bin/python3" real_linked real_cmd
    if [ -x "$linked" ]; then
        real_linked=$("$linked" -I -c 'import os, sys; print(os.path.realpath(sys.executable))' 2>/dev/null) || real_linked=""
        real_cmd=$("$PYTHON_CMD" -I -c 'import os, sys; print(os.path.realpath(sys.executable))' 2>/dev/null) || real_cmd=""
        if [ -z "$real_linked" ]; then
            echo -e "${YELLOW}  ⚠ Hook python ${linked} does not run; rerun ./install.sh after fixing it${NC}"
        elif [ "$real_linked" != "$real_cmd" ]; then
            pip_requirements "$linked"
        fi
    fi
    # Vercel Jev gateway: the repo plus every real (copied) scripts dir. A sync that replaces a
    # copy moves its node_modules into the new one (docs/installer-layout.md, npm dependencies).
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
    chmod 600 "${HOME}/.factory/settings.json" "${HOME}/.reasonix/settings.json" "${HOME}/.gemini/config/hooks.json" 2>/dev/null || true
}

# no-agent-summary: Bun preload that suppresses Claude Code's agent_summary side-query.
# Deploys the JS file to a space-free path (BUN_OPTIONS splits on whitespace) and keeps
# one managed block in ~/.bashrc exporting BUN_OPTIONS.
# MIT: Flamerix AI (upstream), declanbx (fork). Vendored in hooks/no-agent-summary/.
NAS_DEST="$HOME/.local/share/no-agent-summary"
NAS_HOOK="$NAS_DEST/no-agent-summary.js"
NAS_BEGIN="# >>> no-agent-summary >>>"
NAS_END="# <<< no-agent-summary <<<"
NAS_RC="$HOME/.bashrc"

nas_block() {
    cat <<NASEOF
${NAS_BEGIN}
# Bun preload that stops Claude Code's agent_summary side-query (status-line labels
# for background agents, each a full-transcript model call every 30 s).
# Installed from: ${SCRIPT_DIR}
case " \${BUN_OPTIONS-} " in
  *" --preload=${NAS_HOOK} "*) ;;
  *) export BUN_OPTIONS="\${BUN_OPTIONS:+\$BUN_OPTIONS }--preload=${NAS_HOOK}" ;;
esac
${NAS_END}
NASEOF
}

# nas_shellrc set|remove: scripts/vexinstall/shellrc.py edits only the block, in place, writes
# nothing when it is current, keeps a symlinked rc a link, backs the old file up first, and leaves
# the file alone when a marker line is missing.
nas_shellrc() {
    PYTHONPATH="${SCRIPT_DIR}/scripts${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_CMD" -m vexinstall.shellrc "$1" \
        "$NAS_RC" "$NAS_BEGIN" "$NAS_END" --backup-dir "${STATE_DIR}/backups" --label no-agent-summary
}

install_no_agent_summary() {
    local src="$SCRIPT_DIR/hooks/no-agent-summary/no-agent-summary.js"
    if [ ! -f "$src" ]; then
        echo -e "${YELLOW}  no-agent-summary: source not found at ${src}; skipping${NC}"
        return 0
    fi
    mkdir -p "$NAS_DEST"
    cp "$src" "$NAS_HOOK"
    cp "$SCRIPT_DIR/hooks/no-agent-summary/status.sh" "$NAS_DEST/status.sh"
    echo -e "${GREEN}  ✓ no-agent-summary: deployed ${NAS_HOOK}${NC}"
    nas_block | nas_shellrc set || echo -e "${YELLOW}  ⚠ no-agent-summary: ${NAS_RC} not updated (see above)${NC}"
}

uninstall_no_agent_summary() {
    nas_shellrc remove || echo -e "${YELLOW}  ⚠ no-agent-summary: ${NAS_RC} not updated (see above)${NC}"
    # Remove the deployed JS file and status script.
    rm -f "$NAS_HOOK" "$NAS_DEST/status.sh"
    echo -e "${GREEN}  ✓ no-agent-summary: removed ${NAS_HOOK}${NC}"
}

# Git hooks first, so neither a missing python nor a failed engine run leaves the wrong post-merge:
# apply replaces a pre-engine one, which links repo items into runtime roots on every pull, and
# uninstall renames ours, since its sync would re-install everything on the next pull.
GIT_HOOK_PROBLEM=""
if [ "$ACTION" = "apply" ] && [ "$DRY_RUN" = false ] && [ "$CONFIGURE_ONLY" = false ]; then
    install_git_hooks
elif [ "$ACTION" = "uninstall" ]; then
    uninstall_git_hooks
fi

check_python

if [ "$ACTION" = "migrate-overlays" ]; then
    args=(migrate-overlays)
    [ "$DRY_RUN" = true ] && args+=(--dry-run)
    vexinstall "${args[@]}"
    exit $?
fi

if [ "$ACTION" = "uninstall" ]; then
    args=(uninstall --target "$TARGET" --run-id "$RUN_ID")
    [ "$DRY_RUN" = true ] && args+=(--dry-run)
    vexinstall "${args[@]}"
    [ "$DRY_RUN" = true ] || uninstall_no_agent_summary
    if [ -n "$GIT_HOOK_PROBLEM" ]; then
        echo -e "${RED}⚠ ${GIT_HOOK_PROBLEM}${NC}"
        exit 1
    fi
    exit 0
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

# First install with ~/private-skills or ~/pgh/private-skills present: write
# overlays.json so private skills deploy from there, never from the repo.
if [ ! -f "${STATE_DIR}/overlays.json" ] && { [ -d "${HOME}/private-skills" ] || [ -d "${HOME}/pgh/private-skills" ]; }; then
    if [ "$DRY_RUN" = true ]; then
        vexinstall migrate-overlays --dry-run
    else
        vexinstall migrate-overlays
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
vexinstall apply "${args[@]}" --run-id "$RUN_ID" || rc=$?
if [ "$rc" -ne 0 ]; then
    echo -e "${RED}vexinstall apply failed (exit ${rc}). Nothing was forced. Review:${NC}"
    echo -e "${RED}  PYTHONPATH=${SCRIPT_DIR}/scripts python3 -m vexinstall plan --target ${TARGET} --takeover${NC}"
    exit "$rc"
fi
if [ "$TAKEOVER" = true ]; then
    vexinstall prune --unowned --confirm --target "$TARGET" --run-id "$RUN_ID" || true
fi
install_deps
install_no_agent_summary
harden_permissions
echo -e "${GREEN}✓ Installed. Check with: PYTHONPATH=${SCRIPT_DIR}/scripts python3 -m vexinstall doctor${NC}"
