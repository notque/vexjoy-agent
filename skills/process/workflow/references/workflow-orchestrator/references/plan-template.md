# Workflow Plan Templates

Example plans and structure guidelines for common development scenarios.

## Assembly

Generate a plan skeleton from parameters:

```bash
python3 skills/workflow/references/workflow-orchestrator/scripts/assemble-plan.py \
  --category DB --number 001 --description "Add user_preferences table" --tasks 4
```

Use `--list` to see available example plans.
Use `--example <name>` to view a specific example.
Use `--guidelines` to see plan structure requirements.

## Available Examples

| Name | Description | Tasks | Pattern |
|------|-------------|-------|---------|
| db-schema | Database schema change with migration | 4 | Linear |
| api-endpoint | REST API endpoint with auth | 4 | Linear |
| frontend-component | React component with tests + stories | 4 | Diamond |
| bug-fix | Bug fix with regression test (test-first) | 3 | Linear |
| config-change | Config change with backup + validation | 4 | Linear |

## Template Files

| File | Purpose |
|------|---------|
| `templates/plan-template.json.tmpl` | JSON skeleton with `{{variables}}` |

## Plan Structure Requirements

Every plan requires: plan_id (PLAN_[CATEGORY]_[NUMBER]), description, approach,
estimated_total_time, tasks array, dependencies object. Every task requires: task_id,
title, estimated_duration, dependencies, files, operations, verification, rollback.
