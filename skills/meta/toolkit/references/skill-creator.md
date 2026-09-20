# Skill creation contract

Use the repository's canonical skill creator instructions when available in the
active harness. This reference adds only local integration requirements.

1. Search the live index and filesystem for overlapping coverage.
2. Preserve the repository frontmatter dialect: routing metadata stays under
   `routing`; `name` matches the directory; referenced `pairs_with` names exist.
3. Keep workflow-specific constraints in `SKILL.md`; put conditional local
   schemas or failure knowledge in references. Do not copy general tutorials.
4. Add positive, negative, and near-miss activation cases. Evaluate behavior,
   not headings or wording.
5. Run the applicable index generators, reference validation, and the active
   skill validator. Check generated routing-map drift.

Bundled evaluation scripts under `scripts/skill-creator/` own their CLI and
artifact shapes. Inspect `--help` and source rather than using prose copies.
