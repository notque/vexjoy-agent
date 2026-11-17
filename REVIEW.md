# Review rules

Rules the AI reviewer checks on every pull request.
Source: "How the Claude Code team thinks about verification"
(https://claude.dev/blog/how-the-claude-code-team-thinks-about-verification/).

## What to check in this repo

Scope: correctness bugs and safety-policy violations only.
Style and formatting are ruff's job.

Grade each finding with the severity levels in
`skills/shared-patterns/severity-classification.md`:
CRITICAL, HIGH, MEDIUM, or LOW.
Tag a finding **pre-existing** when the bug existed before the diff.

## Diff-triggered checklist

The reviewer checks only rows whose trigger matches the diff under review.

| Trigger | Check | Origin |
|---|---|---|
| Diff changes what a hook prints on stdout | Output shape matches the event's contract; `hooks/tests/test_hook_output_contract.py` passes with no new excuse entry in its `_KNOWN` dict | d6a8b6bb |
| Diff adds a file under `hooks/` | File is registered in `.claude/settings.json` or documented as an adapter in `scripts/codex-hooks-allowlist.txt` | audit 2026-11-16 (11 unregistered hook files) |
| Diff adds or edits a `pip install` line in `.github/workflows/` | Every installed package has a pinned version | c92d2bd0 |
| Diff writes `INDEX.json` or another generated file | Write uses atomic temp-then-rename, not direct overwrite | 58796653 |
| Diff prints or logs response text, tokens, or URLs with keys | Redact credentials before truncating to a display length | 8764fade |
| Diff adds module-level imports or top-level work in a hook | Hook stays lazy-loaded and works on Python 3.10; no `platform`, `subprocess`, or heavy stdlib at import time | 693bfe8e |
| Diff adds a CI gate script | Script has a negative control or an entry in `scripts/negative-control-allowlist.txt` | a134e0fe |
| Diff interpolates user input into HTML, shell, YAML, or an HTTP header | Input is escaped or validated before interpolation | audit 2026-11-16 (publish scripts, account aliases) |
| Diff adds `time.sleep` to a test | See the flaky-test policy in `skills/process/testing/references/patterns-quality-catalog.md` Pattern 11 | audit 2026-11-16 (timing-based router tests) |
| Diff edits `scripts/ci-local.sh` or the lint job | `tests/test_ci_local_script.py` still passes | bad5247d |

An Origin is a commit short SHA, or `audit <date> (<what was found>)` when the
row came from an audit and no single commit fixed it. An Origin must be the
change or finding that motivated the row.

## Pruning

Review this table when it passes 25 rows.
Remove rows whose trigger has not matched in 90 days.
