## Summary

<!-- State the goal plainly in 1-3 sentences (or a few crisp bullets). Say WHAT changed and WHY, in plain words. Name the ADR or issue if one applies. Write for a reviewer scanning in ~15 seconds: one fact per line, declarative. Keep metrics to the single number that matters; let the diff carry the rest. -->

## Changes

<!-- One line per change: verb + what + where, declaratively (`path/or/area` — what changed). Keep each line to a single fact a reviewer needs. When a change has many sub-items, state the SHAPE and count ("add 21 PR-creation trigger phrases") and let the diff list them. One line per change keeps rationale terse. -->
- `path/to/file` — what changed

## Testing

<!-- Paste the SUMMARY of evidence: the command and its final result line (counts, exit code, the verdict). e.g. `pytest -q` → 55 passed; `ruff check` → All checks passed!. A few lines of proof read fast and prove the work. Let the command and its result line stand in for the full run. -->
```
$ <command>
<result line: counts / exit code / verdict>
```

## Scope & Risk

<!-- One line each, terse: what this touches, what stays untouched (name the files/limbs), how to roll back. Each line states a fact a reviewer needs to gauge blast radius. Keep it to facts; skip defensive prose. -->
- **Touches:** <limb / area>
- **NOT touched:** <files/limbs deliberately left alone — e.g. router, Phase 2, execution-limb .js>
- **Rollback:** <revert the commit; no data migration / state change> 

## Checklist

<!-- Check the gates that apply. These mirror this repo's CI (.github/workflows/test.yml). Omit a line only if it genuinely does not apply. -->
- [ ] `ruff check . --config pyproject.toml` clean (excl `venv.312.bak`) — *if any `.py` touched*
- [ ] `ruff format --check . --config pyproject.toml` clean (excl `venv.312.bak`) — *if any `.py` touched*
- [ ] `python -m pytest --tb=short -q` green (paste counts above)
- [ ] `python scripts/validate-doc-counts.py` → 0 drift
- [ ] `python scripts/validate-workflow-conformance.py` passes — *if any workflow `.js` touched*
- [ ] `python scripts/validate-skill-frontmatter.py` / `validate-references.py --check-do-framing` clean — *if any skill/agent touched*
- [ ] joy-check / positive-instruction prose floors untouched — *if any prose floor touched*
- [ ] No forbidden files staged (no `git add -A`; no `INDEX.json`, `venv.312.bak/`, chmod-only churn, or untracked junk)
