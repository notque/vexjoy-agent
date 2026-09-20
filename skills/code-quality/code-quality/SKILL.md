---
name: code-quality
description: "Run this repository's configured cleanup and multi-language quality gates; use for linting, formatting, or technical-debt cleanup, not review findings or security audits."
user-invocable: true
allowed-tools: [Read, Write, Bash, Grep, Glob, Edit, Task, Skill]
agent: python-general-engineer
routing:
  force_route: true
  not_for: "code review with findings (use review), security scanning (use security)"
  triggers: [code cleanup, clean up code, dead code, unused imports, lint code, run ruff, run biome, format code, Python quality, quality gate, technical debt scan]
  category: code-quality
  pairs_with: [review, testing, comment-quality]
---

# Code Quality

Prefer project-defined commands and configuration. Inspect repository instructions and the working tree before acting. Run checks without mutation first; use fix/format modes only when the request authorizes edits, then inspect the diff and rerun the same checks. A lint pass does not imply that tests, builds, or behavior passed.

## Repository quality gate

The local wrapper delegates language detection and required-tool policy to `hooks/lib/quality_gate.py` and `hooks/lib/language_registry.json`:

```bash
python3 skills/code-quality/code-quality/scripts/run_quality_gate.py [path]
```

Useful filters: `--staged`, `--lang <name>`, `--tools lint,format`, `--no-patterns`, `--json`, `-v`. `--fix` authorizes the wrapper's supported mutations; it does not authorize unrelated cleanup.

The wrapper exits 0 only when its configured required checks pass. Missing optional tools and skipped checks remain visible in the report; do not restate them as passes.

## Cleanup requests

Keep the requested scope. Use configured analyzers before heuristic searching, and verify suspected dead code against dynamic imports, reflection, generated entry points, framework registration, and public APIs. Report evidence at `file:line`; distinguish safe mechanical fixes from behavior-changing proposals. Apply only requested fixes.
