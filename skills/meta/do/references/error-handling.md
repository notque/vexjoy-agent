# /do Error Handling

| Error | Cause | Solution |
|---|---|---|
| No Agent Matches | No agent covers domain | INDEX near-matches → closest agent + verification-before-completion. Report gap. |
| Force-Route Conflict | Multiple force-route triggers match | Most specific first; stack compatible secondaries. |
| Plan Required | Simple+ without task_plan.md | Create plan, resume. |
| Router Script Failed | Non-zero exit or non-JSON | Fallback: `general-purpose` + `verification-before-completion`. |
