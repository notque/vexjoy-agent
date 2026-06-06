#!/usr/bin/env bash
#
# Regression test for --per-item install conversion of whole-dir symlinks.
#
# Bug: when a component (e.g. ~/.claude/skills) was previously installed as a
# WHOLE-DIR symlink pointing at the repo source, re-running
#   ./install.sh --symlink --per-item --force
# left the whole-dir symlink in place instead of converting it to a real dir
# of per-item symlinks. Root cause: the per-item branch ran mkdir -p on the
# symlink (no-op) and then tested "$target/<item>", which resolved THROUGH the
# symlink back into the source, so every item looked like it already existed
# and was skipped.
#
# This test reproduces that starting state and asserts the conversion happens
# for both the primary ~/.claude surface (install_component) and a mirror
# surface ~/.hermes (sync_mirror_entry).
#
# Run:  bash tests/test_per_item_install.sh
# Exit: 0 on success, 1 on any failure (with a clear failure message).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

TEST_HOME="$(mktemp -d -t vexjoy-per-item-e2e-XXXXXX)"
trap 'rm -rf "$TEST_HOME"' EXIT

export HOME="$TEST_HOME"
export XDG_CONFIG_HOME="${TEST_HOME}/.config"
export XDG_DATA_HOME="${TEST_HOME}/.local/share"

PASS=0
FAIL=0
log()  { echo "  $*"; }
pass() { PASS=$((PASS + 1)); echo "  PASS: $*"; }
fail() { FAIL=$((FAIL + 1)); echo "  FAIL: $*"; }
assert() {
    local desc="$1"; shift
    if "$@" >/dev/null 2>&1; then
        pass "$desc"
    else
        fail "$desc"
        log "    ran: $*"
    fi
}

echo "==================================================================="
echo "Per-item conversion E2E (test_home=$TEST_HOME)"
echo "==================================================================="

# --- Pre-flight: simulate a prior --force install that left whole-dir symlinks.
# ~/.claude/skills and ~/.claude/agents point straight at the repo source dirs.
mkdir -p "$TEST_HOME/.claude"
ln -s "$REPO_ROOT/skills" "$TEST_HOME/.claude/skills"
ln -s "$REPO_ROOT/agents" "$TEST_HOME/.claude/agents"
log "Seeded whole-dir symlinks: ~/.claude/skills, ~/.claude/agents"

# Confirm the starting state really is a whole-dir symlink (guards the test itself).
assert "precondition: ~/.claude/skills is a whole-dir symlink" test -L "$TEST_HOME/.claude/skills"
assert "precondition: ~/.claude/agents is a whole-dir symlink" test -L "$TEST_HOME/.claude/agents"

# --- detect_conflicts surfaces whole-dir symlinks pointing at the source ---
echo ""
echo "[0a] dry-run conflict table labels whole-dir symlinks"
dry_output=$( cd "$REPO_ROOT" && bash install.sh --symlink --dry-run < /dev/null 2>&1 )
if [[ "$dry_output" == *"whole-dir symlink (will convert to per-item)"* ]]; then
    pass "dry-run table labels whole-dir symlink for conversion"
else
    fail "dry-run table should label whole-dir symlink for conversion"
    log "    output tail: ${dry_output: -300}"
fi

# --- A non-interactive --symlink run must not abort under set -e on EOF ---
# (Conflicts exist here, so the conflict prompt is reached; with stdin from
# /dev/null the read hits EOF and must fall through to the per-item default.)
echo ""
echo "[0b] non-interactive --symlink does not abort on prompt EOF"
ni_output=$( cd "$REPO_ROOT" && bash install.sh --symlink --force < /dev/null 2>&1 )
ni_rc=$?
if [ "$ni_rc" -eq 0 ]; then
    pass "non-interactive --symlink exited 0 (EOF fell through to default)"
else
    fail "non-interactive --symlink exited $ni_rc (prompt EOF tripped set -e)"
    log "    output tail: ${ni_output: -300}"
fi

# --- Run the per-item install ---
echo ""
echo "[1] install --symlink --per-item --force"
output=$( cd "$REPO_ROOT" && bash install.sh --symlink --per-item --force 2>&1 )
if [ $? -ne 0 ]; then
    fail "install --symlink --per-item --force exited non-zero"
    log "$output"
    exit 1
fi
pass "install --symlink --per-item --force exited 0"

# --- Assert ~/.claude/skills was converted to a real dir of per-item symlinks ---
echo ""
echo "[2] ~/.claude/skills converted to per-item dir"
if [ ! -L "$TEST_HOME/.claude/skills" ] && [ -d "$TEST_HOME/.claude/skills" ]; then
    pass "~/.claude/skills is now a real dir (not a whole-dir symlink)"
else
    fail "~/.claude/skills should be a real dir after per-item install"
    log "    state: $( [ -L "$TEST_HOME/.claude/skills" ] && echo "symlink -> $(readlink "$TEST_HOME/.claude/skills")" || echo "not a symlink" )"
fi

# A sample entry inside should be a per-item symlink into the repo. The repo
# skills/ top level holds category dirs (business, meta, ...); pick the first
# per-item symlink rather than hardcoding a name.
SAMPLE_SKILL=$(find "$TEST_HOME/.claude/skills" -maxdepth 1 -type l 2>/dev/null | head -1)
if [ -n "$SAMPLE_SKILL" ]; then
    pass "~/.claude/skills contains at least one per-item symlink"
else
    fail "~/.claude/skills should contain per-item symlinks"
fi
SKILL_TARGET=$(readlink "$SAMPLE_SKILL" 2>/dev/null || echo "")
if [[ "$SKILL_TARGET" == "$REPO_ROOT/skills/"* ]]; then
    pass "per-item skill symlink points into repo skills tree"
else
    fail "per-item skill symlink should point into repo skills tree (got '$SKILL_TARGET')"
fi

# --- Assert ~/.claude/agents was converted too ---
echo ""
echo "[3] ~/.claude/agents converted to per-item dir"
if [ ! -L "$TEST_HOME/.claude/agents" ] && [ -d "$TEST_HOME/.claude/agents" ]; then
    pass "~/.claude/agents is now a real dir (not a whole-dir symlink)"
else
    fail "~/.claude/agents should be a real dir after per-item install"
fi

# --- Mirror surface: ~/.hermes/skills should also be a real dir of per-item links ---
echo ""
echo "[4] ~/.hermes/skills is a per-item dir (sync_mirror_entry path)"
if [ -d "$TEST_HOME/.hermes/skills" ] && [ ! -L "$TEST_HOME/.hermes/skills" ]; then
    pass "~/.hermes/skills is a real dir"
    HERMES_SAMPLE=$(find "$TEST_HOME/.hermes/skills" -maxdepth 1 -type l 2>/dev/null | head -1)
    if [ -n "$HERMES_SAMPLE" ]; then
        pass "~/.hermes/skills contains per-item symlinks"
    else
        fail "~/.hermes/skills should contain per-item symlinks"
    fi
else
    fail "~/.hermes/skills should be a real dir after per-item install"
fi

# --- Idempotence: re-run should keep the per-item layout, never re-create a whole-dir symlink ---
echo ""
echo "[5] re-run --symlink --per-item --force (idempotent)"
output=$( cd "$REPO_ROOT" && bash install.sh --symlink --per-item --force 2>&1 )
if [ $? -ne 0 ]; then
    fail "second per-item install exited non-zero"
    log "$output"
    exit 1
fi
pass "second per-item install exited 0"
if [ ! -L "$TEST_HOME/.claude/skills" ] && [ -d "$TEST_HOME/.claude/skills" ]; then
    pass "~/.claude/skills remains a real dir after re-run"
else
    fail "~/.claude/skills should remain a real dir after re-run"
fi

# --- Summary ---
echo ""
echo "==================================================================="
echo "Results: $PASS passed, $FAIL failed"
echo "==================================================================="
if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
