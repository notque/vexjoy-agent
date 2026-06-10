# Workflow

1. UNDERSTAND. Read hooks/sync-to-user-claude.py in full; map every reader and
   writer of the runtime index path and the INDEX.local.json branch in
   _sync_skills_flat_symlinks. Read git show d4eea119 for the established
   merge semantics. Read hooks/tests/test_sync_to_user_claude.py — list the
   existing symlink-policy tests your change will break or retire.

2. DESIGN. A symlink cannot express a merge. Choose the runtime-index shape:
   materialize a merged file (tracked entries first; INDEX.local.json entries
   setdefault-overlay per name — add, never hide) written to the runtime
   location. Decide and state: when the merged file regenerates (every sync
   run is acceptable; document the staleness window), how symlink mode and
   copy mode each produce it, and how the leak-prevention property survives
   (the runtime file must never be a link to — or write through to — the
   tracked skills/INDEX.json). Write the design as a short comment block or
   docstring at the changed site, not a separate doc.

3. TEST FIRST. Extend hooks/tests/test_sync_to_user_claude.py before fixing:
   (a) stale local index containing a subset/old copy → runtime index still
   carries every tracked entry; (b) local-only entries appear (overlay adds);
   (c) local entry colliding with a tracked name → tracked content wins;
   (d) leak invariant: mutate the runtime index in place, assert the repo's
   tracked file is byte-identical; (e) run matrix over symlink mode and copy
   mode. New tests must FAIL against the unfixed code — verify, then fix.

4. IMPLEMENT. Smallest change in _sync_skills_flat_symlinks (and helpers it
   needs) satisfying invariants 1–3. Keep the file's existing patterns:
   logging style, mode handling, stale-cleanup loop interactions, and
   expected_names bookkeeping.

5. VERIFY. python3 -m pytest hooks/tests/test_sync_to_user_claude.py -q green;
   ruff check . --config pyproject.toml and ruff format --check . --config
   pyproject.toml green; re-read the diff once for scope creep (task scope:
   hooks/sync-to-user-claude.py + hooks/tests/ only).

6. ACCEPT. All invariants demonstrably tested; one local commit
   "fix(sync): <what changed>"; no push, no PR.
