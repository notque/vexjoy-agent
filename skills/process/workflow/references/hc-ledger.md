# Hill-climb ledger schema

```markdown
# Hill climb: <slug>
| metric/direction | measure | target | fixture+hash | floors |
| samples | variance tolerance | budget | plateau K |
## Baseline
<raw samples, median, spread, environment>
## Profile
<hot spot and evidence>
## Iterations
### <n> — ACCEPTED | REVERTED | INCONCLUSIVE
- hypothesis written before edit:
- exact change:
- floor commands and exit codes:
- raw samples, median, spread:
- delta vs best and decision:
## Stop
<trigger, best retained variant, unresolved limits>
```

Resume from the best accepted variant. Never compare against a rejected variant
or change fixture, sample count, or environment without starting a new baseline.
