# Route event contract

Source of truth: `hooks/lib/route_events.py`. Log: `${CLAUDE_LEARNING_DIR:-$HOME/.claude/learning}/route-events.jsonl`, append-only UTF-8 JSONL. Write failures are swallowed, so missing events are possible; aggregate learning rows remain authoritative for aggregates, while this log uniquely records per-dispatch history.

`decision` fields include `ts`, `session`, private `request_snippet`, `agent`, `skill`, `complexity`, `health_at_decision`, `n`, `failure`, `action`, `alternates`, and `gate_inputs_present`.

Health has three distinct states:

- numeric health + `gate_inputs_present: true`: evaluated weight row; gate inputs may be populated.
- null health + `gate_inputs_present: true`: instrumented route with no weight row; valid expected data.
- null health + false/absent `gate_inputs_present`: legacy or missing instrumentation.

An `outcome` includes `ts`, `session`, routing `key`, `outcome` (`success | failure | neutral`), and optional `reason` / `routing_relevant`. Join only when session matches and outcome `key == f"{agent}:{skill}"`; adjacency is invalid under concurrent appends. An unmatched decision may still be pending. Missing additive fields on older lines mean “not recorded,” not corruption.

Sort by `ts`, not file grouping. Keep `request_snippet` within the originating user session.
