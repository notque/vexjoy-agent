# /do routing telemetry

Hooks record routing automatically. The router records one case by hand: an observed route failure (below).

| Capture | Hook | Event |
|---|---|---|
| Routing decision (`{agent}:{skill}`) + right-sizing feedback | `routing-decision-recorder` | PostToolUse:Agent |
| Outcome — validate pending | `routing-outcome-recorder` | SubagentStop |
| Outcome — finalize (boost/decay) | `routing-outcome-finalizer` | UserPromptSubmit |
| Outcome — errored and stale (over 6 hours) fallback | `routing-outcome-stop-fallback` | Stop |
| Outcome — resolve every pending entry | `routing-outcome-stop-fallback` | SessionEnd |
| Review findings | `review-capture` | PostToolUse:Agent |

These feed the route health report:

```bash
python3 ~/.claude/scripts/learning-db.py route-health
```

**Outcome fidelity.** The next-turn finalizer scores acceptance: on the next user turn, deterministically and at zero LLM cost, three ways: failure on errors or rejection (decay); success on explicit acceptance (boost); neutral otherwise. Silence counts as neutral, never as acceptance. `Stop` fires after every turn, before the next prompt exists, so there the fallback scores only two kinds of entry: an errored dispatch as failure at once, and a clean one as neutral after 6 hours with no user turn. It leaves every other entry pending for the finalizer. On `SessionEnd` no next prompt can come, so the same hook resolves every entry still pending: errored as failure, clean as neutral. `.claude/settings.json` registers the hook under both `Stop` and `SessionEnd`.

**Report route failures.** Report only a failure you are confident about:

```bash
REASON_FILE=$(mktemp); printf '%s' "<cause>" > "$REASON_FILE"
python3 ~/.claude/scripts/learning-db.py route-failure AGENT:SKILL --reason-file "$REASON_FILE" --routing-relevant yes --session $SESSION --marker $DISPATCH_ID
rm -f "$REASON_FILE"
```

Triggers: re-route, lazy re-dispatch, validator misroute, harness reject. A right route with bad execution takes `--routing-relevant no`. Skip ambiguous cases. One decay per dispatch key. The temp file keeps the reason text off the shell command line.

---

## Re-deriving routing figures

SKILL.md quotes no telemetry figures since the specialist agents retired (plans/009). Before quoting one, measure it again: a figure is a DATED observation, not an invariant, and no test pins it, because pinning a live DB read would make CI depend on runtime data.

Source: `evidence_route_decisions` in `~/.claude/learning/learning.db` (two other learning.db files exist and lack this table). Read-only.

**The agent column after retirement.** `agent` reads `main` (work run in the /do thread) or `general-purpose` (the normal worker) on new rows, and the schema is unchanged. A `general-purpose` share is no longer a fallback rate: it is about 100% of dispatches by design. Rows before the retirement still name specialist agents, so split any trend at the retirement date. Count real fallbacks from the marker's `fallback=` token instead (the recorder's fallback reason; after retirement `build-dispatch.py` emits it only for a coerced agent name, as the `invalid` reason with the name appended):

```bash
DB=~/.claude/learning/learning.db
sqlite3 "$DB" "SELECT agent, COUNT(*) FROM evidence_route_decisions GROUP BY agent ORDER BY 2 DESC;"
python3 ~/.claude/scripts/learning-db.py route-health   # fallback reasons and route health
```

State the metric as the query computes it. "Named domain skill, fallbacks excluded" is reproducible; "correct skill" is not.

**Combination depth — the definition decides the number.** Depth counts filled slots with fallbacks excluded: skill named and other than `workflow` (the fallback skill; `process` before #993), pipeline present, stack present. The agent slot no longer counts: every dispatch names `general-purpose`, so counting it would score every route one deeper for no routing work. Counting any value present instead of excluding fallbacks returned a healthier number for identical data (2.48 vs 2.01 on the 2026-08-15 rows, when the agent slot still counted), which is why a depth figure quoted without its definition is worthless.

```bash
sqlite3 "$DB" "SELECT ROUND(AVG(depth),2), ROUND(100.0*SUM(depth<=1)/COUNT(*),1) FROM (
  SELECT (skill IS NOT NULL AND skill NOT IN ('','-','workflow'))
       + (pipeline IS NOT NULL AND pipeline NOT IN ('','-'))
       + (stack IS NOT NULL AND stack NOT IN ('','-','[]')) AS depth
  FROM evidence_route_decisions);"
```

Report depth against a REACHABLE maximum (3 slots). On the 2026-08-15 rows `pipeline` and `matched_components` were NULL on all 301, so those rows cannot exceed 2. Confirm the ceiling before quoting the mean.
