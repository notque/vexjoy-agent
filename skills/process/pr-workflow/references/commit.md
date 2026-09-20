# Commit contract

Inspect repository instructions, current branch, status, diff, and active merge/rebase/detached state. Use `scripts/validate_state.py` when available. Do not stage credential-like files without explicit resolution.

Group changes by cohesive intent and present the path list before staging unless the user already named the exact paths. Stage explicit paths, inspect `git diff --cached`, and ensure staged content contains no unrelated work.

If `.adr-session.json` exists, run `python3 ~/.claude/scripts/adr-coverage.py`; report uncovered decisions before committing. Validate the proposed message with `scripts/validate_message.py`. The repository expects Conventional Commit subjects and rejects AI-attribution boilerplate. Execute only within the user’s implement/commit authorization, then verify `git show --stat --oneline HEAD` and remaining `git status --short`.
