# /do Error Handling

| Error | Cause | Solution |
|---|---|---|
| No Skill Matches | No skill covers domain | `skills/INDEX.json` near-matches → closest skill, else `workflow`. Report gap. |
| Force-Route Conflict | Multiple force-route triggers match | Most specific first; stack compatible secondaries. |
| Plan Required | Simple+ without task_plan.md | Create plan, resume. |
| Router Script Failed | Non-zero exit or non-JSON | Fallback: `general-purpose` + `process`. |
