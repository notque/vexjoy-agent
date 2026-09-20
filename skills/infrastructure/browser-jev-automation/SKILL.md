---
name: browser-jev-automation
description: "Run or modify the repository's Jev-driven browser harness, where programs own DOM actions, Jev selects bounded operations, and a text model only supplies missing field text."
version: 1.1.0
context: fork
routing:
  category: infrastructure
  triggers: ["browser automation", "jev browser", "automated browsing", "fill form", "click through"]
  not_for: "Playwright test suites, manual browser testing, or screenshot comparison."
---

# Browser Jev Automation

Use the in-house, zero-package harness. Node 22+, Chromium, and `TYPESAFE_API_KEY` are required.

```bash
python3 scripts/jev-browser-agent.py --url http://127.0.0.1:8000/ \
  --goal "Sign in with username alice, choose country Canada, and submit." \
  --check-text-contains "Welcome alice" --json-compact
```

Output is one JSON object: `status` (`done|blocked|budget|error`), `reason`, `steps`, `requests`, `final_url`, `verify`, `log`, and `usage`. Scripts normally exit 0 with status in JSON.

## Local architecture

| File | Contract |
|---|---|
| `scripts/lib/jev_browser/snapshot.js` | Visible/actionable elements, integer node IDs, guards, page marker |
| `scripts/lib/jev_browser/cdp_driver.mjs` | Builtins-only CDP driver; JSONL commands `open`, `observe`, `fresh`, `act`, `navigate`, `screenshot`, `close` |
| `scripts/jev-browser-decide.py` | One Jev request: operation plus speculative target choices; validates IDs |
| `scripts/jev-browser-verify.py` | Independent Jev goal check; deterministic URL/text checks veto success |
| `scripts/jev-browser-agent.py` | Preflight, observe, scrub, decide, text selection, freshness check, act, verify |

One cycle reads the DOM once. Operation and per-operation target heads run in one Jev request; only the chosen operation's target executes. Code, never model output, resolves selectors and geometry.

## Important controls

- Remote navigation is denied by default. Use repeatable `--allow-host HOST` or broader `--allow-remote`; off-origin navigation is reverted and blocks after three trips.
- `--secret-env LABEL=ENV_VAR` types the environment value into matching fields. Unset variables fail preflight. Logs show `(secret)` and all later snapshots are scrubbed; password values are always `(filled)`.
- `--header NAME=ENV_VAR` sends a secret header without logging it.
- `--max-steps` defaults to 60; `--max-requests` to 120 and counts decide, text-pick, and verify calls.
- `--trace FILE`, `--headed`, `CHROME_PATH`, and `JEV_BROWSER_DEBUG=1` support diagnosis. `JEV_KEY_ONLY=1` skips the plugin-toggle check for standalone/cron use.
- Chromium tries sandboxed launch first. `--no-sandbox` is only a fallback for the explicit "No usable sandbox" failure; `JEV_BROWSER_SANDBOX=1` forbids that fallback.

## Execution invariants

- The node registry is in an isolated CDP world. The driver rejects covered, hidden, disabled, read-only, or stale targets.
- Freshness compares `page_key` plus a target guard, or the page marker for scroll/wait. Stale results re-observe without a stall penalty, capped at 5.
- Write the decision log before mutation. Store full operation and target probability maps.
- A non-DONE pick below confidence 0.45 is held and counts toward the stall guard. Transient Jev errors become bounded WAIT retries (3); unavailable blocks immediately.
- DONE is only a claim. The independent verifier must accept it; deterministic checks veto. Three rejected DONEs block.
- Observe settles for DOM quiet (600 ms, capped at 3 s). WAIT sleeps 1.5 s and may settle for 8 s.
- Cache generated text only for identical `(url, target, label, current value)`.

TYPE_TEXT value order is: matching secret; literals extracted from the goal; Jev Choice over candidates plus `NONE` at confidence >= 0.5; finally the text model. The text model returns strict `{"text":"..."}` and never chooses actions or judges completion. Backend controls are `TEXT_MODEL`, `TEXT_MODEL_BACKEND=auto|api|claude-cli`, `TEXT_MODEL_BASE_URL`, `TEXT_MODEL_API_KEY` (then `ANTHROPIC_API_KEY`), and `TEXT_MODEL_REASONING`.

## Standalone verification

```bash
python3 scripts/jev-browser-verify.py --url http://127.0.0.1:8002/five-star \
  --goal "at least 8 promotions can be toggled" --goal "there is a Start button"
python3 scripts/jev-browser-verify.py --audit-file pages.json
```

Audit JSON is `{"base":"...","pages":{"/path":["goal"]}}`. One browser and snapshot are reused per page. Passing requires `goal_met` and evidence score >= 0.5.

Run offline coverage in `scripts/tests/test_jev_browser_harness.py`; live Chromium/security coverage is in `scripts/tests/test_jev_browser_live.py`.
