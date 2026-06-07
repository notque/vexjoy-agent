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

run_install_for_home() {
    local test_home="$1"; shift
    (
        cd "$REPO_ROOT" &&
        HOME="$test_home" \
        XDG_CONFIG_HOME="${test_home}/.config" \
        XDG_DATA_HOME="${test_home}/.local/share" \
        bash install.sh "$@"
    )
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

# --- Assert ~/.claude/skills became a nested tree (real category dirs + per-skill symlinks) ---
echo ""
echo "[2] ~/.claude/skills converted to nested per-skill dir"
if [ ! -L "$TEST_HOME/.claude/skills" ] && [ -d "$TEST_HOME/.claude/skills" ]; then
    pass "~/.claude/skills is now a real dir (not a whole-dir symlink)"
else
    fail "~/.claude/skills should be a real dir after install"
    log "    state: $( [ -L "$TEST_HOME/.claude/skills" ] && echo "symlink -> $(readlink "$TEST_HOME/.claude/skills")" || echo "not a symlink" )"
fi

# A repo category (e.g. business) must be a REAL dir, not a category symlink,
# so users can drop their own skills inside it.
if [ -d "$TEST_HOME/.claude/skills/business" ] && [ ! -L "$TEST_HOME/.claude/skills/business" ]; then
    pass "~/.claude/skills/business is a real category dir"
else
    fail "~/.claude/skills/business should be a real dir (nested layout)"
fi

# Inside the category, each skill must be a per-skill symlink into the repo.
SAMPLE_SKILL=$(find "$TEST_HOME/.claude/skills/business" -maxdepth 1 -type l 2>/dev/null | head -1)
if [ -n "$SAMPLE_SKILL" ]; then
    pass "~/.claude/skills/business contains per-skill symlinks"
else
    fail "~/.claude/skills/business should contain per-skill symlinks"
fi
SKILL_TARGET=$(readlink "$SAMPLE_SKILL" 2>/dev/null || echo "")
if [[ "$SKILL_TARGET" == "$REPO_ROOT/skills/business/"* ]]; then
    pass "per-skill symlink points into repo skills/business tree"
else
    fail "per-skill symlink should point into repo skills/business (got '$SKILL_TARGET')"
fi

# A top-level skill dir (one holding SKILL.md, e.g. workflow) is symlinked whole.
if [ -L "$TEST_HOME/.claude/skills/workflow" ]; then
    pass "~/.claude/skills/workflow (top-level skill) is symlinked whole"
else
    fail "~/.claude/skills/workflow should be a whole-dir symlink"
fi

# A top-level loose file (INDEX.json) is symlinked at the top level.
if [ -L "$TEST_HOME/.claude/skills/INDEX.json" ]; then
    pass "~/.claude/skills/INDEX.json is symlinked"
else
    fail "~/.claude/skills/INDEX.json should be symlinked"
fi

# A user-dropped external skill inside a category must be preserved on re-run.
mkdir -p "$TEST_HOME/.claude/skills/business/my-external-skill"
echo "external" > "$TEST_HOME/.claude/skills/business/my-external-skill/SKILL.md"

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
    HERMES_SAMPLE=$(find "$TEST_HOME/.hermes/skills/business" -maxdepth 1 -type l 2>/dev/null | head -1)
    if [ -n "$HERMES_SAMPLE" ]; then
        pass "~/.hermes/skills/business contains per-item symlinks"
    else
        fail "~/.hermes/skills/business should contain per-item symlinks"
    fi
else
    fail "~/.hermes/skills should be a real dir after per-item install"
fi

# --- Idempotence: re-run should keep the nested layout and preserve external skills ---
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
# The user's external skill inside a category must survive the re-run.
if [ -f "$TEST_HOME/.claude/skills/business/my-external-skill/SKILL.md" ]; then
    pass "external skill inside category preserved on re-run"
else
    fail "external skill inside category should be preserved on re-run"
fi

# --- Factory gets the same nested layout ---
echo ""
echo "[6] ~/.factory/skills is a nested per-skill dir"
if [ -d "$TEST_HOME/.factory/skills/business" ] && [ ! -L "$TEST_HOME/.factory/skills/business" ]; then
    pass "~/.factory/skills/business is a real category dir"
    FAC_SAMPLE=$(find "$TEST_HOME/.factory/skills/business" -maxdepth 1 -type l 2>/dev/null | head -1)
    if [ -n "$FAC_SAMPLE" ]; then
        pass "~/.factory/skills/business contains per-skill symlinks"
    else
        fail "~/.factory/skills/business should contain per-skill symlinks"
    fi
else
    fail "~/.factory/skills/business should be a real category dir"
fi

# --- External whole-dir symlinks must be preserved, not converted ---
echo ""
echo "[7] external symlinks are preserved"

EXT_HOME="$TEST_HOME/external-claude-home"
EXT_SKILLS="$TEST_HOME/external-claude-skills"
mkdir -p "$EXT_HOME/.claude" "$EXT_SKILLS/custom-skill"
echo "external" > "$EXT_SKILLS/custom-skill/SKILL.md"
ln -s "$EXT_SKILLS" "$EXT_HOME/.claude/skills"
output=$(run_install_for_home "$EXT_HOME" --symlink --per-item --force 2>&1)
if [ $? -ne 0 ]; then
    fail "external ~/.claude/skills install exited non-zero"
    log "$output"
else
    pass "external ~/.claude/skills install exited 0"
fi
if [ -L "$EXT_HOME/.claude/skills" ] && [ "$(readlink "$EXT_HOME/.claude/skills")" = "$EXT_SKILLS" ]; then
    pass "external ~/.claude/skills symlink preserved"
else
    fail "external ~/.claude/skills symlink should be preserved"
fi
if [ -f "$EXT_HOME/.claude/skills/custom-skill/SKILL.md" ]; then
    pass "external ~/.claude/skills custom skill remains reachable"
else
    fail "external ~/.claude/skills custom skill should remain reachable"
fi
output=$(run_install_for_home "$EXT_HOME" --uninstall 2>&1)
if [ $? -ne 0 ]; then
    fail "external ~/.claude/skills uninstall exited non-zero"
    log "$output"
else
    pass "external ~/.claude/skills uninstall exited 0"
fi
if [ -L "$EXT_HOME/.claude/skills" ] && [ "$(readlink "$EXT_HOME/.claude/skills")" = "$EXT_SKILLS" ]; then
    pass "external ~/.claude/skills symlink preserved through uninstall"
else
    fail "external ~/.claude/skills symlink should be preserved through uninstall"
fi
if [ -f "$EXT_HOME/.claude/skills/custom-skill/SKILL.md" ]; then
    pass "external ~/.claude/skills custom skill remains reachable after uninstall"
else
    fail "external ~/.claude/skills custom skill should remain reachable after uninstall"
fi

EXT_FACTORY_HOME="$TEST_HOME/external-factory-home"
EXT_FACTORY_SKILLS="$TEST_HOME/external-factory-skills"
mkdir -p "$EXT_FACTORY_HOME/.factory" "$EXT_FACTORY_SKILLS/custom-skill"
echo "external" > "$EXT_FACTORY_SKILLS/custom-skill/SKILL.md"
ln -s "$EXT_FACTORY_SKILLS" "$EXT_FACTORY_HOME/.factory/skills"
output=$(run_install_for_home "$EXT_FACTORY_HOME" --symlink --per-item --force 2>&1)
if [ $? -ne 0 ]; then
    fail "external ~/.factory/skills install exited non-zero"
    log "$output"
else
    pass "external ~/.factory/skills install exited 0"
fi
if [ -L "$EXT_FACTORY_HOME/.factory/skills" ] && [ "$(readlink "$EXT_FACTORY_HOME/.factory/skills")" = "$EXT_FACTORY_SKILLS" ]; then
    pass "external ~/.factory/skills symlink preserved"
else
    fail "external ~/.factory/skills symlink should be preserved"
fi
if [ -f "$EXT_FACTORY_HOME/.factory/skills/custom-skill/SKILL.md" ]; then
    pass "external ~/.factory/skills custom skill remains reachable"
else
    fail "external ~/.factory/skills custom skill should remain reachable"
fi
output=$(run_install_for_home "$EXT_FACTORY_HOME" --uninstall 2>&1)
if [ $? -ne 0 ]; then
    fail "external ~/.factory/skills uninstall exited non-zero"
    log "$output"
else
    pass "external ~/.factory/skills uninstall exited 0"
fi
if [ -L "$EXT_FACTORY_HOME/.factory/skills" ] && [ "$(readlink "$EXT_FACTORY_HOME/.factory/skills")" = "$EXT_FACTORY_SKILLS" ]; then
    pass "external ~/.factory/skills symlink preserved through uninstall"
else
    fail "external ~/.factory/skills symlink should be preserved through uninstall"
fi
if [ -f "$EXT_FACTORY_HOME/.factory/skills/custom-skill/SKILL.md" ]; then
    pass "external ~/.factory/skills custom skill remains reachable after uninstall"
else
    fail "external ~/.factory/skills custom skill should remain reachable after uninstall"
fi

EXT_CATEGORY_HOME="$TEST_HOME/external-category-home"
EXT_CATEGORY_SKILLS="$TEST_HOME/external-business-skills"
mkdir -p "$EXT_CATEGORY_HOME/.claude/skills" "$EXT_CATEGORY_SKILLS/custom-business"
echo "external" > "$EXT_CATEGORY_SKILLS/custom-business/SKILL.md"
ln -s "$EXT_CATEGORY_SKILLS" "$EXT_CATEGORY_HOME/.claude/skills/business"
output=$(run_install_for_home "$EXT_CATEGORY_HOME" --symlink --per-item --force 2>&1)
if [ $? -ne 0 ]; then
    fail "external ~/.claude/skills/business install exited non-zero"
    log "$output"
else
    pass "external ~/.claude/skills/business install exited 0"
fi
if [ -L "$EXT_CATEGORY_HOME/.claude/skills/business" ] && [ "$(readlink "$EXT_CATEGORY_HOME/.claude/skills/business")" = "$EXT_CATEGORY_SKILLS" ]; then
    pass "external ~/.claude/skills/business symlink preserved"
else
    fail "external ~/.claude/skills/business symlink should be preserved"
fi
if [ -f "$EXT_CATEGORY_HOME/.claude/skills/business/custom-business/SKILL.md" ]; then
    pass "external ~/.claude/skills/business custom skill remains reachable"
else
    fail "external ~/.claude/skills/business custom skill should remain reachable"
fi
output=$(run_install_for_home "$EXT_CATEGORY_HOME" --uninstall 2>&1)
if [ $? -ne 0 ]; then
    fail "external ~/.claude/skills/business uninstall exited non-zero"
    log "$output"
else
    pass "external ~/.claude/skills/business uninstall exited 0"
fi
if [ -L "$EXT_CATEGORY_HOME/.claude/skills/business" ] && [ "$(readlink "$EXT_CATEGORY_HOME/.claude/skills/business")" = "$EXT_CATEGORY_SKILLS" ]; then
    pass "external ~/.claude/skills/business symlink preserved through uninstall"
else
    fail "external ~/.claude/skills/business symlink should be preserved through uninstall"
fi
if [ -f "$EXT_CATEGORY_HOME/.claude/skills/business/custom-business/SKILL.md" ]; then
    pass "external ~/.claude/skills/business custom skill remains reachable after uninstall"
else
    fail "external ~/.claude/skills/business custom skill should remain reachable after uninstall"
fi

# --- Uninstall preserves external skills, removes toolkit symlinks ---
echo ""
echo "[8] uninstall preserves external skills"
CLAUDE_TOP_LINK_TARGET="$TEST_HOME/claude-top-linked-skill"
CLAUDE_CHILD_LINK_TARGET="$TEST_HOME/claude-child-linked-skill"
FACTORY_TOP_LINK_TARGET="$TEST_HOME/factory-top-linked-skill"
FACTORY_CHILD_LINK_TARGET="$TEST_HOME/factory-child-linked-skill"
mkdir -p "$CLAUDE_TOP_LINK_TARGET" "$CLAUDE_CHILD_LINK_TARGET" \
         "$FACTORY_TOP_LINK_TARGET" "$FACTORY_CHILD_LINK_TARGET"
echo "external" > "$CLAUDE_TOP_LINK_TARGET/SKILL.md"
echo "external" > "$CLAUDE_CHILD_LINK_TARGET/SKILL.md"
echo "external" > "$FACTORY_TOP_LINK_TARGET/SKILL.md"
echo "external" > "$FACTORY_CHILD_LINK_TARGET/SKILL.md"
ln -s "$CLAUDE_TOP_LINK_TARGET" "$TEST_HOME/.claude/skills/external-top-link"
ln -s "$CLAUDE_CHILD_LINK_TARGET" "$TEST_HOME/.claude/skills/business/external-child-link"
ln -s "$FACTORY_TOP_LINK_TARGET" "$TEST_HOME/.factory/skills/external-top-link"
ln -s "$FACTORY_CHILD_LINK_TARGET" "$TEST_HOME/.factory/skills/business/external-child-link"
output=$( cd "$REPO_ROOT" && bash install.sh --uninstall 2>&1 )
if [ $? -ne 0 ]; then
    fail "uninstall exited non-zero"
    log "$output"
fi
# Toolkit per-skill symlink should be gone.
if [ ! -e "$TEST_HOME/.claude/skills/business/csuite" ]; then
    pass "toolkit skill symlink removed on uninstall"
else
    fail "toolkit skill symlink should be removed on uninstall"
fi
# External skill must remain.
if [ -f "$TEST_HOME/.claude/skills/business/my-external-skill/SKILL.md" ]; then
    pass "external skill preserved through uninstall"
else
    fail "external skill should be preserved through uninstall"
fi
if [ -L "$TEST_HOME/.claude/skills/external-top-link" ] && [ -f "$TEST_HOME/.claude/skills/external-top-link/SKILL.md" ]; then
    pass "external top-level Claude skill symlink preserved through uninstall"
else
    fail "external top-level Claude skill symlink should be preserved through uninstall"
fi
if [ -L "$TEST_HOME/.claude/skills/business/external-child-link" ] && [ -f "$TEST_HOME/.claude/skills/business/external-child-link/SKILL.md" ]; then
    pass "external nested Claude skill symlink preserved through uninstall"
else
    fail "external nested Claude skill symlink should be preserved through uninstall"
fi
if [ -L "$TEST_HOME/.factory/skills/external-top-link" ] && [ -f "$TEST_HOME/.factory/skills/external-top-link/SKILL.md" ]; then
    pass "external top-level Factory skill symlink preserved through uninstall"
else
    fail "external top-level Factory skill symlink should be preserved through uninstall"
fi
if [ -L "$TEST_HOME/.factory/skills/business/external-child-link" ] && [ -f "$TEST_HOME/.factory/skills/business/external-child-link/SKILL.md" ]; then
    pass "external nested Factory skill symlink preserved through uninstall"
else
    fail "external nested Factory skill symlink should be preserved through uninstall"
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
