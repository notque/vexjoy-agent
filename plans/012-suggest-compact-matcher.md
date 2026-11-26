# Plan 012: suggest-compact starts only for the Write and Edit calls it counts

> **Executor instructions**: follow this plan step by step. Run every
> verification command and confirm the expected result before the next step.
> If a STOP condition occurs, stop and report. Do not improvise. Do not run
> any step marked OWNER-GATED. When done, update this plan's row in
> `plans/README.md`, unless a reviewer dispatched you and maintains the index.
>
> **Drift check (run first)**: `git diff --stat c68ac1fe..HEAD -- .claude/settings.json hooks/suggest-compact.py hooks/tests/test_suggest_compact.py skills/meta/toolkit/references/toolkit-governance/hook-standardization.md`
> If an in-scope file changed, compare the "Current state" excerpts with the
> live code. A mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: perf
- **Kind**: fix
- **Planned at**: commit `c68ac1fe`, 2026-11-26

## Why this matters

`suggest-compact.py` counts Write and Edit calls and suggests `/compact` at a
threshold. Its registration in `.claude/settings.json` has no `matcher`, so
Claude Code starts it, as a fresh Python process, before every tool call:
Grep, Glob, Read, Bash, Agent, Skill, TodoWrite, WebFetch, and every MCP tool.
For any tool other than Write or Edit it prints an empty result and exits.

Measured on the planning host (isolated HOME, median): 59 ms per run, 33 ms
on a host with a healthy bytecode cache. For tools with no other PreToolUse
hook (Grep, Glob, TodoWrite, Skill, WebFetch, WebSearch, MCP tools) it is the
whole hook delay before the call; the fix removes it. For Read it is 1 of 2
processes, for Bash 1 of 10. The Codex and Antigravity mirrors already
register it only for edits (`scripts/codex-hooks-allowlist.txt:61`,
`scripts/agy-hooks-allowlist.txt:54`); only the Claude registration is wide.

## Current state

- `hooks/suggest-compact.py`: the hook.
  - Line 75: `_TRACKED_TOOLS = frozenset({"Edit", "Write"})`.
  - Lines 150-153, the early exit:

    ```python
    tool_name = event.get("tool_name", "")
    if tool_name not in _TRACKED_TOOLS:
        empty_output(_EVENT_NAME).print_and_exit(0)
        return
    ```
- `.claude/settings.json`: the first `PreToolUse` group (lines 206-214 at the
  planned commit) has no `matcher` key:

  ```json
  {"hooks": [{"type": "command",
              "command": "sh \"$HOME/.claude/hooks/lib/pyrun.sh\" \"$HOME/.claude/hooks/suggest-compact.py\"",
              "description": "Advisory: suggests /compact when Edit/Write call count reaches threshold (ADR-103)",
              "timeout": 10}]}
  ```
  Other PreToolUse groups in the same file use `"matcher": "Write|Edit"`;
  match that spelling.
- `scripts/codex-hooks-allowlist.txt:61`:
  `PreToolUse:suggest-compact.py matcher=Edit|Write class=adapted mode=patch failure=open`
  (no change needed).
- `skills/meta/toolkit/references/toolkit-governance/hook-standardization.md:210`:
  ``| `suggest-compact.py` | (all) | Suggest `/compact` at edit threshold |``.
  The `(all)` cell becomes stale.
- `scripts/validate-hook-health.py:695-699`: matcher liveness picks the first
  tool of a matcher (`matcher.split("|")[0]`) as the test `tool_name`, so
  `Write|Edit` makes the liveness run send `Write`, a tool the hook counts.
- `hooks/tests/test_suggest_compact.py`: existing tests load the hook by path
  (`HOOK_PATH`, line 23). Add the new test there and match its style.
- History: the hook was added without a matcher in `fd9fc315` ("add strategic
  compact hook (ADR-103)"); its design always counted only Edit and Write.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Hook tests | `python3 -m pytest hooks/tests/test_suggest_compact.py -n 0 -q` | all pass |
| Mirror tests | `python3 -m pytest scripts/tests/test_codex_hooks_allowlist.py scripts/tests/test_codex_hooks_runtime_compat.py -n 0 -q` | all pass |
| Hook health (static checks read the repo) | `python3 scripts/validate-hook-health.py --ci` | exit 0 |
| Doc counts | `python3 scripts/validate-doc-counts.py` | exit 0 |
| Lint job | `bash scripts/ci-local.sh` | exit 0 |

Do not run `scripts/register-hook.py add` or `remove`: they deploy into the
live `~/.claude`. Edit the repo's `.claude/settings.json` directly. This
changes no safety hook; the new matcher reaches live sessions only after merge
and the next sync.

## Scope

**In scope** (the only files to modify):
- `.claude/settings.json` (the suggest-compact group only)
- `hooks/tests/test_suggest_compact.py`
- `skills/meta/toolkit/references/toolkit-governance/hook-standardization.md` (line 210 only)

**Out of scope** (do not touch, though they look related):
- `hooks/suggest-compact.py`: behavior stays the same.
- Every other registration in `.claude/settings.json`, including the hooks
  that are no-ops in Claude Code (`pretool-routing-gate.py`,
  `gemini-turn-gate-userprompt.py`): removing those needs validator changes
  and is a separate decision.
- `scripts/codex-hooks-allowlist.txt`, `scripts/agy-hooks-allowlist.txt`.

## Git workflow

- Branch: `perf/suggest-compact-matcher`.
- One commit. Message: one lowercase past-tense sentence, no type prefix, no
  trailing period, then a blank line and `Verified-By: tests`. Example from
  `git log`: `dropped the trivial intent skip so every /d route runs the intent check again, trivial ones included, at the owner's call`.
- Do not push, open a PR, merge, deploy, or tag.

## Steps

### Step 1: Write the failing test

In `hooks/tests/test_suggest_compact.py`, add
`test_registered_only_for_the_tools_it_counts()`:

```python
def test_registered_only_for_the_tools_it_counts() -> None:
    """A matcher-less registration starts a process for every tool call; the hook counts only Edit/Write."""
    settings = json.loads((Path(__file__).resolve().parents[2] / ".claude" / "settings.json").read_text())
    groups = [
        g for g in settings["hooks"]["PreToolUse"]
        if any(h.get("command", "").endswith('suggest-compact.py"') for h in g.get("hooks", []))
    ]
    assert len(groups) == 1
    assert set(groups[0].get("matcher", "").split("|")) == set(mod._TRACKED_TOOLS)
```

The file already loads the hook as `mod` (lines 23-30). Add `import json`
only if the file lacks it.

**Verify**: `python3 -m pytest hooks/tests/test_suggest_compact.py -n 0 -q -k registered_only` → 1 failed (`set('') != {'Edit', 'Write'}` or similar).

### Step 2: Add the matcher

In `.claude/settings.json`, in the suggest-compact group from "Current
state", add `"matcher": "Write|Edit"` as the group's first key, the way the
other PreToolUse groups place it. Change nothing else. Keep the file's
indentation (2 spaces per level).

**Verify**:
- `python3 -c "import json; json.load(open('.claude/settings.json'))"` → exit 0.
- `git diff --stat -- .claude/settings.json` → 1 file changed, 1 insertion.
- `python3 -m pytest hooks/tests/test_suggest_compact.py -n 0 -q` → all pass.

### Step 3: Show the per-tool effect

Run this count of registered PreToolUse commands per tool (Claude Code
semantics: an empty or `*` matcher matches every tool; otherwise the matcher
is a regex matched against the whole tool name):

```bash
python3 - <<'EOF'
import json, re
s = json.load(open(".claude/settings.json"))
for tool in ["Grep", "Glob", "TodoWrite", "Skill", "Read", "Bash", "Write", "Edit", "Agent"]:
    n = sum(len(g["hooks"]) for g in s["hooks"]["PreToolUse"]
            if g.get("matcher", "") in ("", "*") or re.fullmatch(g["matcher"], tool))
    print(tool, n)
EOF
```

**Verify**: `Grep 0`, `Glob 0`, `TodoWrite 0`, `Skill 0`, `Read 1`, `Bash 9`,
`Write 10`, `Edit 10`, `Agent 4`. (Before the change: Grep, Glob, TodoWrite
and Skill were 1, Read 2, Bash 10, Agent 5.) If a number differs because
another registration changed since the planned commit, check that each
before-to-after drop is exactly 1 for every tool except Write and Edit, and
report the numbers.

### Step 4: Update the doc row and run the gates

In `hook-standardization.md` line 210, change the matcher cell `(all)` to
`Write|Edit`.

**Verify**:
- `python3 -m pytest scripts/tests/test_codex_hooks_allowlist.py scripts/tests/test_codex_hooks_runtime_compat.py -n 0 -q` → all pass.
- `python3 scripts/validate-hook-health.py --ci` → exit 0.
- `python3 scripts/validate-doc-counts.py` → exit 0.
- `bash scripts/ci-local.sh` → exit 0.

## Test plan

- New test `test_registered_only_for_the_tools_it_counts` in
  `hooks/tests/test_suggest_compact.py`: the registration's matcher equals
  the hook's `_TRACKED_TOOLS`, so the two cannot drift apart again.
- Existing suggest-compact tests keep passing unchanged (behavior is the same).
- Verification: `python3 -m pytest hooks/tests/test_suggest_compact.py -n 0 -q` → all pass, including 1 new test.

## Done criteria

- [ ] `python3 -m pytest hooks/tests/test_suggest_compact.py -n 0 -q` exits 0
- [ ] Step 3 printed `Grep 0` and `Read 1`
- [ ] `python3 scripts/validate-hook-health.py --ci` exits 0
- [ ] `bash scripts/ci-local.sh` exits 0
- [ ] `git status --short` shows no file outside the in-scope list
- [ ] `plans/README.md` row for 012 updated

## STOP conditions

Stop and report if:

- The code at the "Current state" locations does not match the excerpts.
- A step's verification fails twice after a reasonable fix attempt.
- The fix needs a file outside the in-scope list.
- `_TRACKED_TOOLS` in `hooks/suggest-compact.py` is no longer exactly
  `{"Edit", "Write"}`: the hook's design changed, so the matcher must follow
  the new set. Report instead of guessing.
- A validator or test requires every registration to keep its current
  matcher (a pinned-registrations snapshot): report it rather than editing
  the snapshot.

## Maintenance notes

- If the hook ever counts more tools, change `_TRACKED_TOOLS` and the matcher
  together; the new test fails until both agree.
- Other wide registrations found in the same audit, for a later plan: in
  Claude Code, `pretool-routing-gate.py` returns at once outside Antigravity,
  `gemini-turn-gate-userprompt.py` exits when `CLAUDECODE=1`, and
  `adr-enforcement.py` runs only with `ADR_ENFORCEMENT=1`. Each costs one
  process per matching event. `scripts/validate-hook-health.py:621-633`
  requires the Antigravity-mirror hooks to stay registered, so that change
  needs a validator update first.
- Reviewer: the diff is one added `matcher` line, one test, and one doc cell.
