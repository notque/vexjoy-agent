# Workflow Terminology Migration Plan

Additive migration. No big-bang rename. "workflow" is canonical in all new/updated prose; "pipeline" stays a valid legacy alias for back-compat. Every existing "pipeline" code identifier is frozen so the live router never breaks. This is a prose + docs + plan change only.

## Strategy

Canonicalize "workflow" as the umbrella term. Keep "pipeline" as a documented legacy alias. The live router keeps every "pipeline" identifier unchanged: the Haiku contract field, manifest section headers, JSON keys, `.js` `meta.name` exports, sentinel files, and hook type-dispatch strings.

## Steps

1. Land the new reference files (`workflow-patterns.md`, `tournament-workflow.md`, `quarantine-pattern.md`, `lazy-completion-detector.md`) using "workflow" as canonical; each carries a one-line note that "pipeline" is the legacy alias.
2. Apply surgical prose edits to `skills/workflow/SKILL.md` (canonical-term statement + legacy-alias note + new table rows) and `skills/meta/do/SKILL.md` (patterns-catalog pointer + lazy-completion check). Change no routing field, JSON key, manifest section, `meta.name`, sentinel name, or hook type string.
3. In future prose-only passes, prefer "workflow" for new sentences and headings; leave existing "pipeline" identifiers and JSON keys in place. Rename a code identifier ONLY behind a separate reviewed change with registry re-scan + conformance tests green — never as part of this terminology migration.
4. Before any push: `ruff check .` + `ruff format --check .` (if .py touched); `python3 scripts/validate-workflow-conformance.py` and `python3 scripts/workflow-registry.py` to confirm the registry still resolves every existing pipeline key. (`validate-references.py` scans only `agents/**/references/`, so it does not cover these new skill-reference files.)
5. All work on `feat/workflow-patterns-and-terminology`; keep main protected.

## Do Not Touch (frozen identifiers)

- JSON field `pipeline` in the Haiku routing response (`skills/meta/do/SKILL.md` routing contract).
- `PIPELINE-SELECTION RULE` and the Phase 4 Step 1b dispatch conditional in `skills/meta/do/SKILL.md`.
- Root key `pipelines` in `skills/workflow/references/pipeline-index.json`.
- Each pipeline entry's `phases` array names in `pipeline-index.json`.
- Section headers `AGENTS:` / `SKILLS:` / `PIPELINES:` in `scripts/routing-manifest.py`.
- `e["type"] == "pipeline"` classification in `scripts/routing-manifest.py` (≈ lines 100, 148).
- `INDEX_PATHS["pipelines"]` key load in `scripts/routing-manifest.py`.
- `.pipeline-phase` sentinel file read by `hooks/pipeline-phase-gate.py`.
- `meta.name` exports `fan-out-workflow` and `comprehensive-review-workflow` in `skills/workflow/references/*.js` (used by `workflow-registry.py`).
- Skill identifier names containing "pipeline" in `skills/INDEX.json` (e.g. `research-pipeline`, `game-pipeline`, `game-sprite-pipeline`, `motion-pipeline`).
- Pipeline Spec JSON identifiers in the `pipeline-scaffolder` spec schema.
