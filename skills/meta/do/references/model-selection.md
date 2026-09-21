# Model selection

The default is `model: "inherit"`; this records requested inheritance but does
not prove the worker's runtime model. Never infer provider/model identity from
installed script directories or historical benchmark tables, and never pass the
literal `inherit` as an agent-tool model name.

Use an explicit supported override only when the user requested one or a
measured task requirement justifies it. If the harness cannot inherit or expose
the requested model, report that limitation rather than silently substituting.

## Retained Anthropic benchmark points

These historical DeepSWE cells are Pass@1 / average USD per task / output
tokens / steps. They document compatibility data used by the dispatch tests;
they do not describe Opus 5 or the active session.

| Variant | max | xhigh | high | medium | low |
|---|---|---|---|---|---|
| Opus-4.8 (prior measurement) | 59 / 13.22 / 135k / 120 | 54 / 8.01 / 86k / 95 | 52 / 4.28 / 50k / 73 | 49 / 3.44 / 41k / 66 | 41 / 2.29 / 29k / 54 |
| Sonnet-5 (prior measurement) | 54 / 26.40 / 214k / 268 | 50 / 11.89 / 121k / 186 | 48 / 7.43 / 87k / 147 | 40 / 4.08 / 57k / 108 | 31 / 2.19 / 36k / 77 |

## Builder compatibility gates

`scripts/build-dispatch.py` owns accepted names, provider policies, and effort
validation. `provider` names the active harness, never an installed directory.
Provider `other` needs an explicit supported model when using a policy.
`deterministic` means execute a program, not select an LLM worker.

- `max-power` requires `manual_model_override=true`.
- A model differing from a policy choice requires manual override and explicit
  `model_effort`.
- Explicit GPT-5.6 selections require effort and manual override; GPT-5.5 and
  Sonnet require manual override; Opus/max requires manual override.
- Pass only tool-supported effort/model options. Cross-provider choices must
  be deliberate; historical scores never authorize them automatically.
