# Generated Skill Template

Template used by `pipeline-scaffolder` (Phase 3: SCAFFOLD) to produce one SKILL.md per
subdomain from a Pipeline Spec JSON.

## Assembly

Run the assembler script to generate a skill scaffold:

```bash
python3 skills/workflow/references/pipeline-scaffolder/scripts/assemble-skill.py \
  --name <skill-name> --domain <domain> --subdomain <subdomain> \
  --task-type generation --agent <agent-name> --profile personal
```

Use `--list` to see all available templates (main + 13 phase family templates).
Use `--help` for full parameter documentation.

## Template Files

| File | Purpose |
|------|---------|
| `templates/skill-template.md.tmpl` | Main SKILL.md skeleton with `{{variables}}` |
| `templates/phases/*.md.tmpl` | Phase templates per step family (13 families) |

## Variable Reference

All `{{variables}}` map to Pipeline Spec fields. See `pipeline-spec-format.md` for
authoritative field definitions. Key variables: `skill_name`, `domain`, `subdomain_name`,
`task_type`, `agent_name`, `operator_profile`, `complexity`, `phase_count`.

## Phase Generation Rules

Phase family templates in `templates/phases/`:
research-gathering, structuring, generation, validation, review, safety-guarding,
domain-extension, synthesis-reporting, decision-planning, observation, interaction,
git-release, learning-retro.

## Task Type Defaults

Task types (generation, review, debugging, operations, configuration, analysis, migration,
testing) have default error tables and failure mode tables embedded in the main template.
The scaffolder selects applicable rows based on `subdomain.task_type`.
