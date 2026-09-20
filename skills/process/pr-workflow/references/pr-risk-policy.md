# PR risk policy

Risk selects review depth; it does not grant mutation authority.

High-risk paths always dominate: `hooks/`, `.github/`, `install.sh`, `scripts/sync-*`, `.claude/settings*.json`, and root `CLAUDE.md`. Small changes confined to docs, ADRs, generated `INDEX.json`, or skill/agent references are Low. Everything else starts Medium.

Size escalation: 1–200 changed lines is small, 201–800 medium, 801+ large and should usually be split. Low-path medium size becomes Medium; Low-path large becomes High. A High path stays High regardless of size.

- Low: direct review or one independent reviewer when useful.
- Medium: roster from `scripts/right-size-review.py`.
- High: that roster plus explicit operator sign-off recorded in the PR body.

Preserve an explicit user or repository roster and reuse review evidence only when the reviewed diff still matches.
