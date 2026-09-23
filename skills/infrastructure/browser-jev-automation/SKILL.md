---
name: browser-jev-automation
description: "Jev-driven browser automation: Jev picks operations, programs execute, a text model writes field values only when Jev cannot pick one from the goal."
version: 1.1.0
context: fork
routing:
  category: infrastructure
  pairs_with:
    - testing
  triggers:
    - "browser automation"
    - "browser use"
    - "web scraping with jev"
    - "jev browser"
    - "automated browsing"
    - "fill form"
    - "click through"
    - "navigate site"
  not_for: "Manual browser testing, Playwright E2E test suites, or screenshot comparison. Use e2e-testing or testing-preferred-patterns for those."
---

# Browser Jev Automation

Zero-dependency browser harness. Programs read the DOM and execute actions, Jev makes every judgment call, an LLM writes text only when the goal does not already contain the value. Built in-house; no pip or npm packages.

## Quick start

```bash
python3 scripts/jev-browser-agent.py \
  --url http://127.0.0.1:8000/ \
  --goal "Sign in with username alice, choose country Canada, and submit." \
  --check-text-contains "Welcome alice" --json-compact
```

Requires `TYPESAFE_API_KEY`, Node 22+, and a local Chromium (Playwright cache or `CHROME_PATH`). Output is one JSON object: `status` (`done|blocked|budget|error`), `reason`, `steps`, `requests`, `final_url`, `verify`, `log` (full probability distributions per step), `usage`.

Measured on a local login form: 5 steps, 7 Jev calls, 1.4 s wall, zero LLM tokens, goal verified.

## Architecture: three tiers applied to browser control

| Tier | Role | Cost |
|---|---|---|
| Programs (tier 1) | Snapshot DOM, extract goal candidates, execute actions, deterministic checks, secret scrubbing | CPU only |
| Jev (tier 2) | Pick operation + target, pick field value from goal candidates, verify goal | ~$0.042/M tokens, <300 ms |
| LLM (tier 3) | Compose text for TYPE_TEXT only when Jev says no goal candidate fits | Per-token, rare |

One Jev call per decision cycle. Speculative fan-out: operation Choice + per-operation target Choices evaluated in one forward pass. Only the target matching the selected operation executes.

## Components

| File | Role |
|---|---|
| `scripts/lib/jev_browser/snapshot.js` | In-page snapshot: viewport-visible controls, labels, values, operations, code-owned node ids, freshness guards |
| `scripts/lib/jev_browser/cdp_driver.mjs` | Node ESM, `node:` builtins only. Launches Chromium, speaks CDP over the built-in `WebSocket`, evaluates in an isolated world, serves JSON-lines commands: `open`, `observe`, `fresh`, `act`, `navigate`, `screenshot`, `close` |
| `scripts/jev-browser-decide.py` | One Jev call: operation + target with speculative fan-out, validated against observed ids |
| `scripts/jev-browser-verify.py` | Independent Jev goal check (`goal_met` Noul, evidence Score, `has_error`, `page_loaded`, `evidence_element` Choice) plus deterministic `url_contains` / `text_contains` checks that veto |
| `scripts/jev-browser-agent.py` | Loop: preflight, observe, scrub, decide, text (secret, Jev pick, LLM), freshness, act, log, verify |

## CLI

| Flag | Meaning |
|---|---|
| `--url`, `--goal` | Required. Loopback URLs only unless `--allow-remote` |
| `--check-url-contains X`, `--check-text-contains Y` | Deterministic checks that must pass for DONE |
| `--secret-env LABEL=ENV_VAR` | Type the variable's value into fields whose label contains `LABEL`; unset variable fails preflight |
| `--allow-host HOST` | Permit one host and its subdomains (repeatable). Off-origin navigation elsewhere is reverted |
| `--allow-remote` | Permit any host. Page text then reaches Jev and, for composed text, the text model |
| `--header NAME=ENV_VAR` | Send a header on every request with the variable's value (staging bypass tokens). Never logged |
| `--trace FILE` | Write every observed, scrubbed snapshot to FILE |
| `--headed` | Show the browser window |
| `--max-steps` (60), `--max-requests` (120) | Budgets; requests count Jev calls including text picks and verifies |
| `--json-compact` | Single-line output |

| Env | Meaning |
|---|---|
| `TYPESAFE_API_KEY` | Required |
| `JEV_KEY_ONLY=1` | Skip the Claude Code plugin toggle check (cron, standalone) |
| `CHROME_PATH` | Chromium binary; default is the newest Playwright cache build |
| `JEV_BROWSER_SANDBOX=1` | Forbid the `--no-sandbox` fallback |
| `TEXT_MODEL` (`claude-opus-4-6`), `TEXT_MODEL_BACKEND` (`auto` \| `api` \| `claude-cli`), `TEXT_MODEL_BASE_URL` (`https://api.anthropic.com`), `TEXT_MODEL_API_KEY` (falls back to `ANTHROPIC_API_KEY`), `TEXT_MODEL_REASONING` (`none`) | Tier 3 text model. `auto` uses the API when a key is set, else `claude -p` (logged-in CLI, run from `/tmp`, no tools). Owner prefers opus 4.6 here |
| `JEV_BROWSER_DEBUG=1` | Enables the driver's `debug_eval` command for development |

## Standalone page checks and audits

`jev-browser-verify.py` also opens pages itself:

```bash
python3 scripts/jev-browser-verify.py --url http://127.0.0.1:8002/five-star \
  --goal "at least 8 promotions can be toggled" --goal "there is a Start button"
python3 scripts/jev-browser-verify.py --audit-file pages.json   # {"base": "...", "pages": {"/path": ["goal", ...]}}
```

One browser per audit, one snapshot per page, one Jev call per goal (~100-200 ms each). `passed` needs `goal_met` and evidence score >= 0.5. Same `--allow-host`, `--header`, `--check-*` flags as the agent.

## Safety invariants

- Model output never becomes selectors, coordinates, or JavaScript. Every action carries an integer node id issued by `snapshot.js`; the driver resolves geometry itself and rejects covered, hidden, disabled, or read-only targets.
- The node registry lives in a CDP isolated world. Page scripts cannot see or rewrite it (live test asserts `typeof window.__jevBrowser === "undefined"` from the page).
- Loopback URLs only by default. `--allow-host` widens per host. If a click leaves the allowed origin (sign-in redirect, external link), the agent returns to the last good URL, tells Jev which action caused it, and blocks after three such trips.
- Secrets: the log shows `(secret)`; after a secret is typed, every later snapshot is scrubbed before Jev, the text model, or the log sees it. Password inputs never expose their value (`(filled)`).
- Page text reaches Jev and the text model as untrusted data. Instructions say so explicitly.
- Chromium runs a throwaway profile. Sandboxed launch first; `--no-sandbox` only when Chromium reports "No usable sandbox" (user namespaces disabled). The ready line reports `sandbox: true|false`.

## Key patterns (learned from jev-ultrafast)

- **Speculative fan-out**: one request asks "which operation?" and "which target for CLICK/TYPE_TEXT/SELECT?" at once. Unused heads are discarded.
- **One read per cycle**: `observe` runs `snapshot.js` once. Jev sees that snapshot.
- **Semantic freshness guards**: `act` compares `page_key` + the target's guard (value, enabled state, position, nearby text) for targeted actions, or the page `marker` for scroll/wait. A stale page returns `stale: true`; the loop re-observes without a stall penalty, capped at `STALE_LIMIT` (5).
- **Decision consumed before mutation**: the log entry is written before `act`, so a navigation cannot erase the record.
- **Independent verification**: DONE is a claim. `jev-browser-verify.py` runs as a separate question set; a rejected DONE goes back into history so Jev re-decides with that evidence. Three rejected DONEs mean BLOCKED.
- **Full distributions logged**: every step records `operation_probabilities` and `target_probabilities`.
- **Text reuse only on identical context**: cached by `(url, target, label, current value)`.
- **Transient Jev errors retry as WAIT** up to `STALL_LIMIT` (3); `unavailable` blocks at once.
- **Low-confidence picks are held**: a non-DONE operation under `LOW_CONFIDENCE` (0.45) is not executed; the loop re-observes and counts toward the stall guard.
- **Settle before judging**: `observe` waits for the DOM to be quiet (600 ms, capped at 3 s) and reports `quiet`; WAIT pauses 1.5 s then settles up to 8 s; a rejected DONE triggers a WAIT before the next decision. Jev sees `page.settled` and history notes when content was still changing.
- **Whole-page element table**: rendered controls below the fold are offered too, marked `offscreen`; the driver scrolls them into view. Covered controls (modal backdrop, sticky header) are dropped at snapshot time, so an open modal leaves only its own controls.
- **Links say where they go**: `navigates away to /path` or `leaves this site`, and decide's rules forbid them unless the goal names that page.

## Text value selection

Order for a TYPE_TEXT target:

1. `--secret-env` match on the field label.
2. Program extracts candidate literals from the goal (quoted strings, emails, `username X`, `search for X`, numbers).
3. Jev Choice over candidates plus `NONE`. Accepted at confidence >= 0.5.
4. LLM via Anthropic Messages API (`urllib`, no SDK). Strict `{"text": "..."}` reply.

The text model writes one value. It never picks actions or judges progress.

---

## Phase 1: OBSERVE

`observe` evaluates `snapshot.js` in the isolated world. Output:

```text
[1] heading  Sign in                          []
[2] textbox  Username                         [CLICK, TYPE_TEXT]
[3] combobox Country (value=USA)              [SELECT]   options 3:1 USA, 3:2 Canada
[4] checkbox Remember (checked=False)         [CLICK]
[5] button   Sign in                          [CLICK]
```

Plus `actions` (`e2:fill`, `e3:sel:ca`, `scroll_down`, `wait`), `page_key`, `guards`, `marker`, and page text (<= 6000 chars).

**Gate**: snapshot captured and scrubbed. Phase 2.

## Phase 2: DECIDE

`jev-browser-decide.py` returns `operation`, `target`, `confidence`, `needs_text`, and both probability maps. Invalid targets resolve to BLOCKED. Jev unavailable resolves to BLOCKED with `source: unavailable`.

**Gate**: operation and target decided and logged. Phase 3.

## Phase 3: EXECUTE

1. Resolve the observed action by `(kind, index)`. Missing action: record, count toward stall.
2. TYPE_TEXT: pick text per the order above.
3. `act` with the snapshot's `page_key`, `guards`, `marker`. Stale: re-observe.
4. Driver settles: two animation frames or 50 ms; combobox fills wait up to 200 ms for visible options.

**Gate**: action executed. Phase 4.

## Phase 4: VERIFY

- DONE: `jev-browser-verify.py` with deterministic checks. Verified: stop `done`. Rejected: history entry, re-decide.
- BLOCKED: stop.
- Stall guard: `STALL_LIMIT` (3) consecutive non-WAIT actions with an unchanged marker: stop `blocked`.
- Budget: `MAX_STEPS` 60, `MAX_REQUESTS` 120.

**Gate**: loop or stop. Every exit carries `reason`.

---

## Long tasks: checkpoint search

The loop above picks every step with Jev. For tasks longer than a few steps, use checkpoint search: an LLM or the caller sets subgoals, and Jev beam-searches between them (`../../meta/building-with-jev/references/composition-patterns.md`, Checkpoint search; `scripts/jev_search.py`). Branching needs a way back to a kept state (re-navigate to the checkpoint URL and replay); count that cost. The agent loop does not run checkpoint search yet. Adopt it only after this eval:

| Arm | Planner | Step picker |
|---|---|---|
| a | LLM plans every step | LLM |
| b | none | Jev picks every step (current loop) |
| c | LLM sets checkpoints | Jev beam search between them |

- Run the same task set through all three arms, bucketed by task length (for example 1–5, 6–15, 16+ steps).
- Report per bucket: success rate (verified DONE), total tokens (Jev plus LLM), and wall time.
- Price and pace the eval per rule 7 of the production rules; use a held-out task set for the final report.

## Request sizing and retries

Apply [Jev production rules](../../shared-patterns/jev-production-lessons.md) when you change the decide, text, or verify calls:

- Keep each request at or under the reliable size from `python3 scripts/jev-size-probe.py --payload <dumped requests>` (2.5–4k tokens via Gateway until measured). Large pages grow the element table: bound it by the priority sort and field limits rather than sending the whole page.
- Use Vercel AI Gateway. Too much context is the most common failure, and page snapshots are the usual cause: estimate each request before sending and trim the element table or split questions rather than send an oversized request. A ~100-token probe that returns proves the cause is size.
- Retry a lone fast Gateway 503 after 50–150 ms. Back off exponentially on 429/529. Never retry 401/402/422.
- Every retry counts against `--max-requests`.

## Error handling

Every Jev failure resolves to BLOCKED or a bounded WAIT retry. Scripts exit 0 with JSON. Preflight fails before Chromium launches on: remote URL without `--allow-remote`, Jev unavailable, unset secret variable, malformed `--secret-env`. A failed text tier blocks the run and names the cause in `reason`. Driver failures return `status: error` with the Node stderr tail.

## Tests

| File | Covers |
|---|---|
| `scripts/tests/test_jev_browser_harness.py` | Offline: decide payload/parse, verify parse and veto, agent loop with fake driver (secrets, stale, stall, budget, rejected DONE, Jev-error retry, preflight, scrub) |
| `scripts/tests/test_jev_browser_live.py` | Real Chromium on a loopback fixture: snapshot contract, password masking, isolated world, covered-target rejection, stale guard, select/checkbox/scroll/submit, end-to-end secret scrubbing. Skips without Node + Chromium |

Field-tested on 5 Star Booker (loopback dev server): closes the help modal, selects promotions, picks a mode, starts booking, spins the venue; the three-page audit from `mmr-ratings-dev/scripts/jev_browser_validate.py` runs through `--audit-file` unchanged.

## References

- [jev-ultrafast](https://github.com/browser-use/jev-ultrafast): patterns studied, code not reused
- `docs/PHILOSOPHY.md`: three execution tiers
- `scripts/jev_router_common.py`: `validated_call_jev`, `bound_text`, `typesafe_available`
