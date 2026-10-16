# /d design: session pick, Jev evidence

Deep reference for `/d` (`skills/meta/d/SKILL.md`). Load it when explaining,
tuning, or extending the router. SKILL.md's phases are enough to run it.

## Design in one table

| Step | Owner | Script |
|---|---|---|
| Force-route guard (`pr-workflow`, `pr-pipeline`, `security`) | code | `pre-route.py`, kept by `jev-route.py` prepare |
| Attachment evidence: 5 signal Nouls, 6 domain Nouls, one Jev call | Jev | `jev-route.py` prepare |
| Pick agent, skill, pipeline from the full manifest with `/do`'s rule text | session model | `print-route-rules.py`, `get-routing-manifest.sh --request-file` |
| Validate names against the live manifest, apply the safety force route, attach skills, derive complexity | code | `jev-route.py --finalize` |
| Check the restated outcome survives the route | Jev | `jev-intent-align.py` (Phase 2) |

Jev supplies evidence and a check. It does not pick the primary route.

## Why the pick moved to the session

The earlier design asked Jev two questions per request: a wide rank over the
catalog, then a shortlist rerank with a fits threshold. Every Jev answer saw
only a truncated catalog slice, and about a quarter of requests fell back to
`/do`.

A paired measurement on `scripts/routing-ab-corpus.json` v1.5 (269 rows) found
the Jev pick below `/do`'s rule text applied by a model. Both arms got the same
repo facts for the 91 rows recorded with a workload, and each arm ran twice.

| Arm | Pair correct (run 1 / run 2) | General-purpose or null picks |
|---|---|---|
| Jev two-stage pick (previous `/d`) | 146 / 146 | 67 / 69 |
| `/do` rules, model pick (proxy) | 172 | 55 |
| Session pick plus Jev attachments (this design) | 178 / 178 | 70 / 66 |

The structural cause: the pick needs the whole manifest and the cross-rule
reading (SECTION-INTEGRITY, SPECIFICITY, COMBINATION DOCTRINE, the two
greediness gates). A model reading `/do`'s text does that. Per-question Jev
calls over a shortlist cannot.

Paired change against the previous `/d`, counting a row only when both runs of
an arm agree: 38 rows recovered, 10 lost, McNemar p < 0.001. Against the `/do`
proxy, 23 rows only this design got right and 17 only the proxy did (p = 0.43).

Lost rows fall in three groups:

| Group | Rows | Cause |
|---|---|---|
| Sibling-skill choice | 61, 133, 211, 214, 245 | The pick chose a close skill (`review` for `assessment`, `workflow` for `domain`, `assessment` for `docs-sync-checker`). The agent was right. `/do` makes the same choice on 133, 211, and 214. |
| Out-of-catalog request | 21, 78 | The pick returned `general-purpose` and `workflow` for a request no catalog entry covers. Gold wants a content or no-op route. |
| Weak gold | 34, 123, 129 | Gold is `content`, or no pick at all, and a defensible `writing` or `research` pick scores wrong. |

### Held-out follow-up (not a gate)

A second set of 67 real requests from 11 repos, labelled before any router ran, scored the new `/d` at 42 and `/do` at 46 on rows right in both of two runs (Sonnet for both; means 44 and 49). The rows carried no repo facts, so `/d` had no `JEV_RESULT.project`; `/d` picked `general-purpose` more often on read-only Go questions. The corpus result above stays the basis for the change.

## Single-sourced rule text

`/do` Phase 2 holds the routing rules. `scripts/print-route-rules.py` prints the
span from `**Routing rules (ALL apply):**` up to `**Section validator (before
dispatch):**` straight from `skills/meta/do/SKILL.md`. `/d` never copies it, so
the two routers cannot drift. `scripts/tests/test_print_route_rules.py` fails when
an anchor moves or a rule leaves that span. The old hand-written Jev
instruction strings (the hidden coupling this document used to list as a known
limitation) are gone.

## What Jev still decides

### Attachment evidence (prepare)

One batched evaluation of 11 Nouls. State: the request, plus project facts
(languages, frameworks, datastores, names only) when a repo is known.

| Group | Nouls | Used for |
|---|---|---|
| Signals | `tests_requested`, `research_needed`, `comprehensive_review`, `local_only`, `objective_loop_worthy` | `SIGNAL_SKILLS` in `jev-route.py` and the complexity derivation |
| Domain | `programming`, `frontend`, `kubernetes`, `testing`, `building-with-jev`, `research` | Attach the domain skill when the score is 0.6 or higher |

`_noul` accepts a score only inside 0 to 1 and treats anything else as
missing. A Jev failure or a malformed answer sets `error`, leaves the evidence
empty, and routing continues.

Measured on the corpus: p50 549 ms, p95 666 ms, mean 820 input and 210 output
tokens per call.

The measurement ran on the `jev-latest` alias, which pointed at `jev-1.13.0`. TypeSafe moves the alias to `jev-1.14.0` about a week after its 2026-10-14 release. Rerun the `d-prepare` arm (see "Re-running the measurement") after the move before trusting the 0.6 attachment floor, and read `model` in each response to see which version answered.

### Attachment policy (finalize)

`_attachments` builds `attach` in this order and stops at three skills: the
pre-route stack, the agent's domain floor (`DOMAIN_SKILL_BY_AGENT`), domain
Nouls at 0.6 or higher by score, then `SIGNAL_SKILLS`. Names outside the live
manifest drop out. `_default_agent` fills a null or `general-purpose` agent from
the skill's owner (`AGENT_BY_SKILL`).

### Intent alignment (Phase 2)

Unchanged: one batched `jev-intent-align.py` evaluation of the agent's
`PROPOSED_INTENT` against the route. The route is the finalized `ROUTE`.

## What code enforces

| Rule | Where |
|---|---|
| A safety force route (`pr-workflow`, `pr-pipeline`, high-confidence `security`) overrides the picked skill and pipeline | `finalize`, matching `/do` Step 1(a) |
| Other force matches and suggestions are not passed to the pick | `_forced`, matching `/do` Step 1(b) |
| A name outside `AGENTS:`, `SKILLS:`, or `PIPELINES:` is dropped and listed in `problems` | `finalize` |
| The router entry points `d` and `do` are never valid skills | `finalize` |
| A skill name in the agent slot moves to the skill slot | `finalize` |
| An empty skill becomes `workflow` (`skill_source: "fallback"`), the skill-greediness gate's default | `finalize` |
| `general-purpose` without a `fallback_reason` is a problem | `finalize` |

## Cost per request

| Part | Previous `/d` | This design |
|---|---|---|
| Jev calls before the pick | 2 (rank, rerank), about 9k Jev tokens | 1, about 800 input and 210 output tokens |
| Jev intent alignment | 1 batched call | 1 batched call |
| Session context for the pick | route JSON only | `/do` rules (about 2k tokens) plus the manifest (about 10k tokens), read once |
| Fallback to `/do` | 26% of requests, then the full `/do` read | none |
| Pick cost in the eval (`claude -p`, prompt cache warm) | n/a | $0.019 per request on Sonnet |

The session pays the manifest read on every Simple-and-above request. The
previous `/d` paid it on the 26% that fell back, plus two Jev calls on all of
them.

## Gateway presence

`scripts/jev_transport.py` selects the transport (`JEV_TRANSPORT=auto|vercel|direct`).
Auto prefers `AI_GATEWAY_API_KEY`, then `TYPESAFE_API_KEY`. The presence check is
not a health check: a configured Jev that is down still attempts the call and
sets `error` on the failure.

## Confident-wrong risk

The session pick has no independent verifier. A confident wrong pick is
dispatched as-is, and the Phase 2 intent check sees only the restated outcome and
the route, not the catalog. The membership check catches invented names, not
wrong real ones.

The backstop is the eval gate: `SAFETY_BUCKETS` (`benchmark-force_route`,
`false-positive-guard`, `paraphrase-git`, `paraphrase-security`) are checked
bucket by bucket on every full run. `benchmark-force_route`, `paraphrase-git`,
and `paraphrase-security` are also protected at runtime, because `pre-route.py`
catches them before the session picks and `finalize` pins the result.
`false-positive-guard` has no runtime backstop in `/d` or `/do`: idiom traps rely
on the model reading means, not words.

On this design: `paraphrase-git` 6/6 and `paraphrase-security` 4/4 in both runs,
`benchmark-force_route` 5/7 in both runs (two rows where the pick chose a
language agent and a close skill), `false-positive-guard` 6/7 in both runs.

## Data egress

Prepare sends the request text and, when a repo is known, project facts (names
only) to the Jev gateway. Intent alignment sends the request, the restated
intent, and the route. Catalog text never leaves the machine: the manifest goes
to the session model only. Before this design, every request also sent catalog
names and descriptions to Jev in both pick stages.

## Re-running the measurement

```bash
python3 scripts/jev-eval.py --out-dir <fresh-dir> --workload-dir <name>=<dir-with-requirements.txt>
python3 scripts/router_attachment/run_eval.py --router d-prepare --out <fresh>/d-prepare.json
python3 scripts/router_attachment/run_eval.py --router d-model --jev-results <fresh>/d-prepare.json --out <fresh>/d-model.json
```

Run each arm twice. A rerun with unchanged code changes the pick on about 11%
of rows, so count a row as changed only when both runs agree.
