# Routing Examples and Dispatch Reference

Worked routing examples, Combination Doctrine reference, and `build-dispatch.py` field guide for `/do` (and `/d`).

## Phase 2 Semantic Routing Examples

### FORCE-ROUTE: Intent vs Keyword

Match what the user means, not isolated words:

| Request | Route | Why |
|---|---|---|
| "push my changes" | `pr-workflow` | Genuine git push |
| "push back on this design" | Not `pr-workflow` | Metaphorical resistance |
| "configure my fish shell" | `deploy` | Fish shell configuration |
| "fish for bugs" | Not `deploy` | Idiom meaning search |
| "commit these files" / "merge the PR" | `pr-workflow` | Genuine version-control operation |
| "commit to a decision" / "merge ideas in your head" | Not `pr-workflow` | Metaphorical phrasing |
| "send my commits to the server" | `pr-workflow` | Plain phrasing for git push |

### PIPELINE-SELECTION Examples

Pick a pipeline when intent matches a pipeline's description/triggers, the shape is multi-phase (3+ steps, gather-then-synthesize, mixed script+LLM, durable intermediate artifacts), or Phase 1 classified the request Complex:

| Request | Pipeline | Why |
|---|---|---|
| "write an article in vexjoy voice about X" | `null` (skill `writing`) | Voice writing lives inside `writing` |
| "write structured docs for X from the source" | `doc-pipeline` | Source-to-doc multi-phase survey |
| "comprehensive review of these 8 files" | `comprehensive-review` | Outranked by `right-size-review.py` when a real diff exists (`tier_signal: true`) |
| "add caching to the API and update the docs" | `quality-loop` | Implement → review → document (multi-phase without saying "pipeline") |
| "help me understand how auth works across this repo" | `explore-pipeline` | Parallel exploration earns a plain pipeline on shape alone |
| "fix the typo on line 42 of foo.py" / "debug this failing test" / "review this 10-line function" | `null` | Single step for one worker |

## Combination Doctrine Reference

Four surfaces compose and fill every slot the request earns:

| Surface | Answers | Slot |
|---|---|---|
| Workers | Parallel `general-purpose` dispatches for fan-out, each with its own skill and scope | `workers` |
| Skill | Which domain or methodology runs | `skill` |
| Pipeline | Which phase structure holds the work | `pipeline` |
| Stack | Which extra rigor rides along | Phase 3 `stack` |

Combine upward from the floor (one surface filled; a fallback skill counts as unfilled):
- **Simple**: `skill` (main thread on Anthropic lane unless dispatch pays).
- **Medium**: `skill` + `stack` (domain skill plus methodology, e.g. `"Go tests"` → `testing` + stack `programming`).
- **Complex**: 2+ workers (primary plus `workers`), 2+ skills (`skill` plus Phase 3 `stack`), and a `pipeline` when multiple phases apply.

## Phase 3 Step G: Context Modes and Evidence Reuse

- **`summary`** (recommended default for dispatched workers): includes current git status, diff stat, and recent commits alongside the Task Spec.
- **`files`** (legacy default): includes initial excerpts for named files when excerpts help the worker act immediately.
- **`none`**: skips fresh git/file gathering while retaining a notice that no fresh state was gathered so the handoff envelope stays complete. Prefer `none` over legacy `--no-gather` for Medium+ handoffs.
- Context modes always preserve the supplied Task Spec and required injections.
- Reuse reads while their source and task context stay unchanged; pass fresh workers relevant summaries and evidence paths rather than copying full investigations.
- For worker transitions, follow `process`. For verification evidence, follow `testing` and re-run checks when inputs or environment change.

## Phase 4: `build-dispatch.py` Field Guide

| Field | Contract |
|---|---|
| `skill` | Phase 2 pick (`"-"` for Trivial main-thread runs). Validated against `skills/INDEX.json`. |
| `agent` | Omit for default `general-purpose`. Pass only a private overlay agent from the manifest's `AGENTS:` section; any unindexed name coerces to `general-purpose` with `fallback=invalid-agent:<name>`. |
| `pipeline` | Phase 2 pick; omit when `null`. Pipelines stay out of Skill-tool calls. |
| `complexity` | `trivial`, `simple`, `medium`, or `complex`. |
| `model` | Required Medium+; pick from Model choice (`haiku`, `opus`, `fable`, or Google AI tiers with `provider: "google"`). Override rules: `references/model-selection.md`. |
| `provider` | Active harness (`anthropic`, `openai`, `google`, `antigravity`, `other`), not an installed directory. |
| `health` | `"-"` (in-context weights read retired; see `docs/route-loop-validation.md`). |
| `stack` | Phase 3 enhancement skills and shared patterns. Callable skills emit `Call the Skill tool with \`<skill>\`.` once per skill (primary first, de-duplicated); shared-pattern entries inject inline. |
| `task_spec` | Mandatory Simple+; rejected if empty at Medium+. Creation routes add `"match ADR"`. |
| `flags.thinking_override` | `"slow"` for security/arch/5+ files; `"fast"` for lookups; `null` otherwise. |
| `execution` | `"main"` for Anthropic-lane Trivial/Simple main-thread runs (emits `agent=main exec=main` for telemetry; `--no-record` skips recording). |

## Complex (3+ Sources) Dispatch Matrix

| Verbs | Mode |
|---|---|
| list / count / extract / inventory / search / check / find / grep | Scripts when deterministic; otherwise parallel readers → synthesis, model per Model choice |
| review / audit / assess / analyze / debug / investigate / evaluate | Single worker (or planned fan-out), model per Model choice |

## Multi-Part Fan-Out Notes

- Sequential stages pass relevant prior results and evidence locations; synthesis receives findings and evidence paths from every required stage.
- Emit one `build-dispatch.py` call and one `general-purpose` Agent dispatch per worker (`N` workers = `N` calls = `N` markers) in a single message for parallel parts.
- Packing multiple markers into one Bash/Workflow script records them but forfeits per-route fit scoring (which reads a lone marker per event).
