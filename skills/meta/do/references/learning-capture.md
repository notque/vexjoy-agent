# /do Learning Capture (automatic)

Hooks capture everything. Router records one case manually: observed route failures (below).

| Capture | Hook | Event |
|---|---|---|
| Routing decision (`{agent}:{skill}`) + right-sizing feedback | `routing-decision-recorder` | PostToolUse:Agent |
| Outcome - validate pending | `routing-outcome-recorder` | SubagentStop |
| Outcome - finalize (boost/decay) | `routing-outcome-finalizer` | UserPromptSubmit |
| Outcome - session-end fallback | `session-learning-recorder` | Stop |
| Tool errors | `error-learner` | PostToolUse |
| Review findings | `review-capture` | PostToolUse:Agent |

Feeds the route health report in `learning-db.py`.

**Outcome fidelity.** Deterministic on next user turn, zero LLM cost, THREE-WAY: failure on errors/rejection (decay); success on explicit acceptance (boost); neutral otherwise. No complaint ≠ acceptance. Stop fallback: errors→failure, clean→neutral.

**Report route failures** (HIGH-CONFIDENCE only):

```bash
REASON_FILE=$(mktemp); printf '%s' "<cause>" > "$REASON_FILE"
python3 ~/.claude/scripts/learning-db.py route-failure AGENT:SKILL --reason-file "$REASON_FILE" --routing-relevant yes --session $SESSION --marker $DISPATCH_ID
rm -f "$REASON_FILE"
```

Triggers: re-route, lazy re-dispatch, validator misroute, harness reject. Right route + bad execution → `--routing-relevant no`. Ambiguous → skip. Decays one per dispatch key. Temp file avoids shell splicing.

**Optional:** curated insight via `retro`: `learning-db.py learn --skill <name> "insight"` or `--agent <name> "insight"`. Routing rows (`category=effectiveness`) excluded from `retro graduate`.
