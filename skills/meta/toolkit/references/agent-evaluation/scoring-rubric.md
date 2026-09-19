# Agent/Skill Structural Scoring Rubric

`scripts/score-component.py` is the source of truth. It runs eight static checks worth 90 points. This is a structural health score, not a complete judgment of usefulness or behavioral quality.

## Point Allocation

| Check | Max | What the script measures |
|---|---:|---|
| Valid YAML frontmatter | 10 | Parseable frontmatter with non-empty `name` and `description` |
| Referenced files exist | 15 | Backtick-quoted file-like paths resolve; partial credit is proportional |
| Patterns section | 10 | A heading contains `pattern`, `preferred pattern`, or `anti-pattern` |
| Error handling section | 10 | A heading contains `error` or `failure mode` |
| Registered in routing | 10 | Agent is in `agents/INDEX.json`; skill is in the `/do` skill or `skills/INDEX.json` |
| Reference files | 10 | A `references/` directory exists |
| Workflow instructions | 15 | `Instructions`, a numbered Phase/Step heading, and a `**Gate**` marker; 5 points each |
| No broken internal links | 10 | Markdown internal links resolve; partial credit is proportional |
| **Maximum** | **90** | Before an optional secret penalty |

`--check-secrets` subtracts 10 points per detected secret, capped at 20 points. Scores never fall below zero.

## Grade Boundaries

Grades use percentage of `total / max_total`, not raw points:

| Percentage | Grade |
|---:|:---:|
| 90-100 | A |
| 75-89 | B |
| 60-74 | C |
| 40-59 | D |
| 0-39 | F |

The CLI exits 0 only when every scored component earns A or B. It exits 1 when any component earns C or below, and 2 for invocation or file errors.

## JSON Contract

With `--json`, each result contains:

```json
{
  "file": "skills/example/SKILL.md",
  "type": "skill",
  "total": 75,
  "max_total": 90,
  "grade": "B",
  "checks": [
    {
      "name": "Valid YAML frontmatter",
      "status": "PASS",
      "earned": 10,
      "max": 10,
      "detail": ""
    }
  ],
  "secret_penalty": 0,
  "secrets_found": []
}
```

Use `checks[*].earned` and `checks[*].max`. The scorer does not emit `earned_points`, `max_points`, line references, content-depth points, Operator Context compliance, `version` compliance, or CAN/CANNOT scoring.

## Qualitative Review

After the deterministic precheck, inspect whether the component is accurate, useful, proportionate, and behaviorally effective. Report those findings separately with file and line evidence. Do not add subjective points to the 90-point structural score.
