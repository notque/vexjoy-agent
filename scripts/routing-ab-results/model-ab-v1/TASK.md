Fix a known bug in hooks/sync-to-user-claude.py.

Bug: the runtime-index policy in _sync_skills_flat_symlinks (lines ~373-381)
points ~/.claude/skills/INDEX.json wholesale at skills/INDEX.local.json
whenever the local file exists. A stale INDEX.local.json then hides newly
added tracked skills from everything that reads the runtime index — the same
replace-semantics failure PR #778 fixed in scripts/routing-manifest.py,
scripts/pre-route.py, and scripts/index-router.py (tracked-first merge:
local entries overlay/add per-name, never hide tracked ones). Read that fix
first: git log --grep="local-override" --oneline; git show d4eea119.

Required invariants after the fix:
1. The runtime index contains every entry of the tracked skills/INDEX.json;
   INDEX.local.json entries overlay/add per-name.
2. In-place writes to ~/.claude/skills/INDEX.json never reach the tracked
   skills/INDEX.json in the repo (keep the leak-prevention property).
3. Both install modes correct: symlink and copy.
4. Scope: hooks/sync-to-user-claude.py and hooks/tests/ only, unless you
   justify otherwise.

Deliverables:
- The fix.
- Tests in hooks/tests/test_sync_to_user_claude.py covering: stale local
  index no longer hides tracked entries; leak-prevention invariant holds;
  both install modes.
- Green: python3 -m pytest hooks/tests/test_sync_to_user_claude.py -q
- Green: ruff check . --config pyproject.toml && ruff format --check . --config pyproject.toml
- One local commit, message style "fix(sync): <what changed>". Do NOT push.
  Do NOT open a PR.

Safety:
- Never execute hooks/sync-to-user-claude.py against the real ~/.claude.
  Exercise it only through pytest tmp_path fixtures.
