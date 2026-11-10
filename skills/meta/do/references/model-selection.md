# Explicit model selection

Task-to-model choice lives in `skills/meta/d/references/model-task-fit.md`. Use this reference for the builder's policy tiers, override rules, prices, and legacy measurement tables. `inherit` remains valid when no task type fits. The builder produces a prompt; the dispatcher must apply that instruction.

## Anthropic policy (2026-11-09)

Owner order 2026-11-01 plus the effort ladder from Anthropic's model guide (2026-11-09). Owner, verbatim, 2026-11-09: "Also I prefer opus 5.5 medium over high". Opus runs at medium on every tier, high-risk included. `scripts/build-dispatch.py` enforces this table for `provider="anthropic"`, the default.

| `model_policy` | Selection | Use for |
|---|---|---|
| deterministic | no LLM | Run the script directly. |
| low-risk | `haiku` / `low` | Read-only gathering only (locate, lookup, cite lines, excerpts, research fetch, log reading). An Opus thread judges the result. |
| standard | `opus` / `medium` | Code writing and edits, debugging, features, deciding reviews, decisions, and any task no other row fits. Start at medium, then high. |
| high-risk | `opus` / `medium` | Auth, data, security, concurrency, irreversible changes. Start at medium, then high. |
| max-power | `fable` / `high` | Major refactor or migration, architecture planning, lead of a many-agent fan-out, deep research synthesis, quantitative analysis, a long unattended run, or Opus at high fell short. Requires `manual_model_override=true`; state the justification in task_spec intent. Start an explicit `fable` pick at medium, then high. |

`opus`/`high` is no tier's default. It stays valid as an explicit pick and as the escalation step after a failed `opus`/`medium` attempt: pass `model: "opus"` with `model_effort: "high"` and no `model_policy`.

Sonnet is no tier's default. Anthropic suggests Sonnet for well-scoped coding, documents, chat, and repeated agent tasks; the owner's experience (2026-11-01: Sonnet code work needed redo) supersedes that. Re-measure with the loop in `skills/meta/d/references/model-task-fit.md` before changing it.

Escalate on a miss (an objective check fails, or a Jev blocker Noul is 0.6 or higher), in this order:

1. Give the agent a way to verify its work: a test, build, or script.
2. Raise effort one level, up to high.
3. Move to the next model up at a lower effort: `haiku` -> `opus`/`medium` -> `opus`/`high` -> `fable`/`medium` -> `fable`/`high`.

Never raise Opus past high before trying Fable. Fable at high scores about the same as Opus at max for about half the cost per task (FrontierCode 2.0: 45.3 vs 45.5). Effort cannot add knowledge or skill a model lacks.

### Prices

Anthropic list price in USD per 1M tokens, 2026-11-09. Every model has a 1M-token context and a 128K-token maximum output. `scripts/agent-scheduler.py` uses the input and output columns for cost estimates.

| Alias | Model | Input | Output | Cache read |
|---|---|---|---|---|
| `haiku` | Haiku 5.5, prompt up to 100K tokens | 0.10 | 0.50 | 0.01 |
| `haiku` | Haiku 5.5, prompt over 100K tokens | 0.50 | 2.50 | 0.05 |
| `sonnet` | Sonnet 5.5 | 2.00 | 10.00 | 0.10 |
| `opus` | Opus 5.5 | 4.00 | 20.00 | 0.20 |
| `fable` | Fable 5.2 | 8.00 | 40.00 | 0.20 |

## Override rules

`scripts/build-dispatch.py` owns accepted model names, provider policies, effort validation, and override rules. Set `provider` from the actual harness, not the first installed scripts directory. `model_policy` selects the provider's table; provider `other` requires a supported explicit model instead. `deterministic` means run a script, not an LLM dispatch.

- **Owner per-task override:** when the owner names a model for the task ("use fable for everything"), pass that `model` with `manual_model_override=true` on every dispatch. The builder accepts it for every model, `inherit` included, and records the model in the route marker.
- `max-power` requires `manual_model_override=true`.
- A model or effort different from a named policy's choice requires `manual_model_override=true`. A different model also requires an explicit `model_effort`. So `model_policy: "high-risk"` with `model_effort: "high"` is rejected without the override; the error names the explicit `opus`/`high` pick.
- Explicit `haiku`, `sonnet`, `opus`, and `fable` need no override, with two exceptions. `opus`/`xhigh` requires `manual_model_override=true`: test `fable` at high first. `opus`/`max` and `fable`/`max` require `manual_model_override=true`.
- `inherit` takes no `model_policy` and no `model_effort`.
- Explicit GPT-5.6 choices require effort and manual override. GPT-5.5 requires manual override.
- Claude effort is advisory when the agent tool has no effort parameter. Only pass options the tool supports.
- Cross-provider calls remain deliberate, explicit choices. Do not infer a cross-provider upgrade from historical scores.
- A route marker records a requested selection. It does not establish which model ran. Report actual identity only from harness execution metadata.

## Historical measurements and policy tables

These are the previously recorded DeepSWE measurements, retained for reference. They are not measurements of the current session or proof of current model quality. The Claude rows measure earlier models (Opus 4.8, Sonnet 5): do not read them as Opus 5.5, Sonnet 5.5, or Fable 5.2 scores. No DeepSWE run exists for the current Claude lineup; the Anthropic policy above rests on the owner's order and Anthropic's guide. The OpenAI policy table below is still the builder's `provider="openai"` table.

Measurement cells: Pass@1 / average USD per task / output tokens / steps. Higher Pass@1 is better; the other values are lower-is-better.

| Variant | max | xhigh | high | medium | low |
|---|---|---|---|---|---|
| Opus-4.8 (prior measurement) | 59 / 13.22 / 135k / 120 | 54 / 8.01 / 86k / 95 | 52 / 4.28 / 50k / 73 | 49 / 3.44 / 41k / 66 | 41 / 2.29 / 29k / 54 |
| Sonnet-5 (prior measurement) | 54 / 26.40 / 214k / 268 | 50 / 11.89 / 121k / 186 | 48 / 7.43 / 87k / 147 | 40 / 4.08 / 57k / 108 | 31 / 2.19 / 36k / 77 |

Superseded Anthropic tiers: under the owner order of 2026-11-01, standard and high-risk were `opus`/`high` and max-power was `opus`/`xhigh`. The current table is under "Anthropic policy" above; the tier history is in `skills/meta/d/references/model-task-fit.md`.

| Variant | max | xhigh | high | medium | low |
|---|---|---|---|---|---|
| GPT-5.6 Sol | 73 / 8.39 / 60k / 61 | 71 / 4.70 / 41k / 44 | 69 / 3.47 / 28k / 37 | 61 / 1.86 / 18k / 31 | 45 / 1.07 / 11k / 23 |
| GPT-5.6 Terra | 70 / 4.95 / 72k / 76 | 60 / 2.13 / 40k / 43 | 54 / 1.13 / 22k / 34 | 35 / 0.58 / 12k / 25 | 24 / 0.43 / 8.6k / 21 |
| GPT-5.6 Luna | 67 / 3.03 / 73k / 102 | 57 / 1.54 / 45k / 71 | 44 / 0.78 / 26k / 49 | 11 / 0.22 / 8.2k / 24 | 2 / 0.07 / 3.1k / 12 |
| GPT-5.5 legacy | n/a | 67 / 7.23 / 46k / 82 | 64 / 5.10 / 31k / 62 | 54 / 2.75 / 20k / 46 | 27 / 1.20 / 9.4k / 28 |

| Task class | Selection | pts/$ | Why |
|---|---|---|---|
| deterministic | no LLM | — | Run the script directly. |
| low-risk | `gpt-5.6-terra` / `high` | 47.8 | 54 Pass@1 at 1.13, 22k tokens, 34 steps. |
| standard | `gpt-5.6-sol` / `high` | 19.9 | 69 Pass@1 at 3.47, 28k tokens, 37 steps. |
| high-risk | `gpt-5.6-sol` / `xhigh` | 15.1 | 71 Pass@1 at 4.70, 41k tokens, 44 steps. |
| max-power | `gpt-5.6-sol` / `max` | 8.7 | 73 Pass@1 at 8.39, 60k tokens, 61 steps; `manual_model_override=true`; state justification in task_spec intent. |

## Google AI / Antigravity CLI (`provider="google"` or `"antigravity"`)

When running in Antigravity CLI (`agy`) with Google AI models (`gemini-4-argon`, `gemini-3.8-flash`), `build-dispatch.py` maps `model_policy` to the Argon/Flash tiers below. Subagent dispatches (`invoke_subagent` and `run_workflow` `agent()`) map to `"flash_lite"`, `"flash"`, `"inherit"`, or `"pro"`. See `skills/meta/do/references/antigravity-execution.md` for full execution details.

| Task class | `build-dispatch.py` Selection | `invoke_subagent` `Model` | Why |
|---|---|---|---|
| deterministic | no LLM | — | Run the script directly. |
| low-risk | `gemini-3.8-flash` / `low` | `flash` / `flash_lite` | Fast mechanical edits, lookups, scouting, formatting. |
| standard | `gemini-4-argon` / `medium` | `inherit` | Standard feature work, debugging, and test implementation. |
| high-risk | `gemini-4-argon-high` / `high` | `pro` | Multi-file architecture, concurrency, security-critical paths. |
| max-power | `gemini-4-argon-high` / `max` | `pro` | `manual_model_override=true`; escalation tier after an objective verification miss. |
