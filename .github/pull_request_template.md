## Summary

<!-- 1-3 sentences: WHAT changed and WHY. State the goal, not the diff. If this implements an ADR or closes an issue, name it. -->

## Changes

<!-- Bullet list of concrete changes, one per file or area: `path/or/area` — what changed. Keep each bullet to the actual edit, not intent. -->
- `path/to/file` — what changed

## Testing

<!-- Show EVIDENCE, not "tests pass". Paste the command AND its result: ruff exit, pytest counts, gate traces, dogfood output. The reviewer must be able to see the proof, not take your word for it. -->
```
$ <command>
<pasted output: counts / exit code / trace>
```

## Scope & Risk

<!-- Which limb/area this touches; what was deliberately NOT touched (name the files/limbs); how to roll back. -->
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
