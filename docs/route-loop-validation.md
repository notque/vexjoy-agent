# Outcome-Routing-Loop: Validation Evidence Package

Branch: `feat/outcome-routing-loop`. Date: 2026-06-07. Audience: a skeptical
reader who wants proof, not prose.

This document's credibility rests on what it does **not** claim. Every number is
either re-derivable from a command below or copied from a named artifact. No
claim appears without an artifact path or a command. Production value is
**UNMEASURED** — see [What is NOT claimed](#what-is-claimed-vs-not-claimed) and
[Limitations](#limitations).

---

## Purpose

The outcome-routing-loop lets `/do` demote or tie-break a semantically-picked
route using observed route outcomes (learning.db weights), with safety routes
hard-exempt. This package reports whether the mechanism works (yes, by
construction and tests) and whether it has helped a live route (not measured —
structurally unmeasurable on the current corpus). It exists so the loop can be
judged on evidence and deleted by a pre-registered kill switch if it never acts.

---

## What is claimed vs NOT claimed

| Statement | Status | Evidence |
|-----------|--------|----------|
| The demote/tie-break/exemption mechanism behaves to spec | CLAIMED | `route-value-eval.py` mechanism=pass; synthetic demote help=24 harm=0; exemption 49/49 |
| Force-route/security routes are never demoted | CLAIMED | `route_policy.py:180` exemption checked before floor; 49/49 held |
| The failure channel decays weight on routing-relevant failures only | CLAIMED | temp-DB dogfood: 0.65→0.57, idempotent per (session,marker); `routing-dogfood-results.md` |
| Haiku routing beats the free pre-route baseline | CLAIMED | dogfood 80%/95% vs 30%/75%; `routing-dogfood-results.md` |
| The loop has improved a live production route | **NOT claimed** | k=0; value UNMEASURED; `route-value-eval.py` exit 2 |
| Value thresholds (D>0, CI>0, McNemar p<0.05) are met | **NOT claimed** | k=0; metrics null, not computed |
| Judge reliability is validated | **NOT claimed** | inter-judge agreement UNDEFINED at k=0 |
| Results generalize beyond one user | **NOT claimed** | single-user corpus, 117 cases |
| Stage-1/Stage-3 weight numbers are real | **NOT claimed** | labeled SYNTHETIC-WEIGHTS everywhere |

---

## Mechanism

`/do` routes via a Haiku semantic pick. Step 1.5 re-ranks against route weights
read from learning.db and may adjust the pick.

| Action | Condition | Notes |
|--------|-----------|-------|
| Demote | `conf < 0.30` AND `fail >= 3` AND `n >= 5` | the demote floor |
| Tie-break | semantic `conf < 0.35` AND an evidenced alternate with `n >= 5` | swaps to the evidenced route |
| Exempt | force-route / security skill | hard-exempt; checked first (`route_policy.py:180`) |

Shadow instrumentation records gate inputs on every dispatch via the
`[do-route]` marker, written as decision events to `route-events.jsonl`.
Outcomes finalize three-way — failure / success / neutral, neutral censored —
through a deterministic finalizer plus an orchestrator-reported route-failure
channel (`learning-db.py route-failure`; ADR: orchestrator-reported-route-failures).

---

## Methodology

### Two-verdict contract (pre-registered)

`scripts/route-value-eval.py` reports two independent verdicts. Mechanism
conformance and production value are never collapsed into one gate.

| Exit | Meaning |
|------|---------|
| 0 | value pass |
| 1 | mechanism fail OR value fail (stderr names which) |
| 2 | value UNMEASURED |

### Pre-registered value thresholds (fixed before any run)

Value PASS requires ALL of the following, computed ONLY over the `k`
health-affected cases (Arm B != Arm A):

| Threshold | Value | Source |
|-----------|-------|--------|
| Effect | `D > 0` | `route-value-eval.py:597` |
| Bootstrap CI lower bound | `> 0` | `route-value-eval.py:414-418` |
| Resamples | `>= 10000` (pre-registered) | `stage3-live-results.md:123` |
| McNemar | `p < 0.05` (two-sided exact) | `route-value-eval.py:418` |
| Harm | `== 0` | `route-value-eval.py:414` |

> **Note:** The harness default is 5000 resamples (`route-value-eval.py:369`).
> The pre-registered floor is 10000. At `k=0` the resample loop never executes,
> so the resample count is moot (`stage3-live-results.md:123`).

### Blinding and judges (Stage 3)

| Control | Detail |
|---------|--------|
| Corpus | 117 live Haiku answers |
| Judges | claude (primary, pre-registered) + codex (replication) |
| Blinding | `[do-route]` markers stripped from all eval calls |
| Isolation | temp-DB only; live `~/.claude/learning` never written |
| Judge-unreliable rule | agreement < 80% on overlapping scored cases ⇒ verdict `judge-unreliable` regardless of D |

All Stage-1 and Stage-3 weight numbers carry the **SYNTHETIC-WEIGHTS** label.

---

## Results by stage

### Stage 1 — mechanism (synthetic weights)

| Arm | Result | Reading |
|-----|--------|---------|
| REAL replay | changed = 0 | No-harm control by design. No alternates were offered, so it CANNOT show value — only the absence of harm. State this limitation explicitly. |
| SYNTHETIC demote | help = 24, harm = 0 | Constructed wrong-pick + gold alternate; the loop corrected the pick. SYNTHETIC-WEIGHTS. |
| Force-route exemption | 49 / 49 held | Every safety route survived demotion pressure. |

### Stage 2 — live telemetry (post-fix)

| Metric | Value |
|--------|-------|
| non_null_health | 5 |
| recorded_failures | 0 |
| value_measured | false |

`recorded_failures` counts ONLY routing-relevant failure outcome events. The
pre-fix counter conflated decision-history fields; it was fixed in review.

### Stage 3 — live blind A/B (2026-06-07)

| Metric | Value | Source |
|--------|-------|--------|
| Live answers | 117 | `stage3-live-results.md` |
| Scored picks | 97 | `stage3-k0-diagnosis.md:28` |
| `k` (health-affected cases) | 0 | Arm B never diverged from Arm A |
| D / CI low / McNemar p | null | not computed at k=0 |
| Inter-judge agreement | UNDEFINED | 0 overlapping scored cases |
| Force-route exemption held | 49 / 49 | `stage3-live-results.md:49` |
| Regression of 4 fixed misroutes | 3 / 4 pass | `stage3-live-results.md:17` |
| Verdict | UNMEASURED, exit 2, mechanism pass | per pre-registration |

The judge-unreliable rule did NOT fire: agreement is UNDEFINED (0 overlapping
cases), not below 80%. Judge reliability is therefore **not validated**.

Regression detail: r13 picks the correct skill (`research-pipeline`) but the
wrong agent slot (`general-purpose` vs gold `research-coordinator-engineer`).
Open item; outside the scope of the skill-sibling fix (`97feda42`).

---

## k=0 root cause

The cause is **structural**, not a silent failure
(`research/forward-plan/stage3-k0-diagnosis.md`).

| Finding | Count | Source |
|---------|-------|--------|
| Scored picks | 97 | `stage3-k0-diagnosis.md:28` |
| Picks on the demote floor (`conf<0.30, fail>=3, n>=5`) | 39 | `stage3-k0-diagnosis.md:30` |
| Of those, force-route exempt | 39 (all) | `stage3-k0-diagnosis.md:31` |
| Floor-matched kept by exemption (correct) | 39 | `stage3-k0-diagnosis.md:33` |
| Tie-break low-confidence cases | 1 | `stage3-k0-diagnosis.md` |
| Low-confidence AND evidenced alternate (tie-break fuel) | 0 | `stage3-k0-diagnosis.md:37` |
| Counterfactual demotes if exemption stripped | 26 / 39 | `stage3-k0-diagnosis.md:18` |

Force-route skills on the 39 floor-matched picks: pr-workflow x19,
go-patterns x12, skill-creator x5, agent-creator x2, security-review x1
(`stage3-k0-diagnosis.md:11`).

Reading: under fabricated failure data, the loop refused to second-guess
safety-critical routes (hard exemption), and had no evidenced alternate
anywhere else. The counterfactual (exemption stripped) demotes 26/39 — proof
the floor logic is live and the exemption is the sole reason `k=0`. The loop
**fails safe, not silent**.

---

## Router worth-it dogfood

20 tasks, 3 arms, blind-evaluated (`research/forward-plan/routing-dogfood-results.md`).

| Arm | Exact-pair | Agent-level |
|-----|-----------|-------------|
| Haiku router | 80% (16/20) | 95% (19/20) |
| Codex | 80% (16/20) | 85% (17/20) |
| Deterministic pre-route alone | 30% (6/20) | 75% (15/20) |

Conclusion: Haiku routing is worth the token cost against the free pre-route
baseline (the genuine production alternative). Within n=20 the Haiku-vs-Codex
gap is noise; the win is against pre-route.

Failure channel, proven on a temp DB (`CLAUDE_LEARNING_DIR`):

| Property | Result |
|----------|--------|
| Decay per routing-relevant failure | 0.65 → 0.57 |
| Idempotency | per (session, marker) |
| Non-relevant failures | decay nothing |
| Live DB | untouched |

---

## Review provenance

Dual-track review, 2026-06-07.

| Track | Scope | Output |
|-------|-------|--------|
| Claude | 26 reviewers, 3 waves (12 foundation + 10 deep-dive + 4 adversarial) | 112 findings; 19 actionable Critical/High; 0 contested |
| Codex | codex-cli 0.135.0, read-only sandbox, 3 chunks | 16 distilled findings; 2 false positives caught by source verification |

Three findings converged independently across both tracks: dedup-commit
ordering, readiness conflation, whole-prompt marker parsing. ALL Critical/High
fixed in commit `a5b2e50d`. Tests: 4291 passed. `ruff check` + `ruff format`
clean repo-wide.

Review artifacts: `/tmp/codex-branch-review-{1,2,3}.md`,
`/tmp/tier4-{actionable,all}.json` (volatile; see Limitations).

---

## Kill criterion (pre-registered)

`scripts/route-decommission-check.py` is the falsifiable kill switch: if the
loop never acts, it gets deleted.

DELETE iff ALL of:

| Condition | Constant | Source |
|-----------|----------|--------|
| Age OR volume | `>= 90 days` from STAGE0_FIX_EPOCH OR `>= 3000` post-fix decisions | `route-decommission-check.py:118-119` |
| Clock start | epoch 1780780867, commit `d943ba74` | `route-decommission-check.py:114-115` |
| Real demote | `== 0` | interventions counter |
| Real tie-break | `== 0` | interventions counter |
| Shadow demote | `== 0` | interventions counter |
| Clock valid | instrumented_rate `>= 95%` AND unknown_rate `<= 5%` | `route-decommission-check.py:127-128` |

Clock validity uses a three-state `gate_inputs_present` contract: (a) numeric
gate inputs, (b) no-row, (c) legacy pre-marker events. Only state (c) counts
against the 95% rate. Shadow tie-break is excluded as unmeasurable — semantic
confidence is unrecorded (documented).

Today: **CLOCK-INVALID, exit 4**, accruing. At the time of writing the
instrumented rate is below 95% because legacy pre-marker events dilute it; the
rate rises as instrumented dispatches accrue. Re-run for current counts; the
verdict (CLOCK-INVALID) and exit code (4) are stable until the clock validates.

---

## Reproduce

```bash
# Value eval: expect exit 2, mechanism pass, value UNMEASURED
python3 scripts/route-value-eval.py --out-dir /tmp/eval-out

# Decommission check: expect exit 4 CLOCK-INVALID today
python3 scripts/route-decommission-check.py

# Full in-scope test suite: expect 4291 passed
python3 -m pytest hooks/tests scripts/tests -q
```

Verified this session:

| Command | Result |
|---------|--------|
| `route-value-eval.py` | exit 2; mechanism=pass; value UNMEASURED; Stage 2 non_null_health=5 recorded_failures=0 |
| `route-decommission-check.py` | exit 4 CLOCK-INVALID |
| `pytest hooks/tests scripts/tests` | 4291 passed, 1 skipped, 75 xfailed, 0 failures |

Stage-3 fixture rebuild: `/tmp/stage3-live/build_fixture.py` +
`build_judge.py` import `route-value-eval` symbols and write only to `/tmp`.

Artifacts:

| Path | Content | Durability |
|------|---------|-----------|
| `/tmp/stage3-live/` | cases, arm-picks, synthetic-weights, judge outputs, harness stdout | volatile |
| `/tmp/codex-branch-review-{1,2,3}.md` | codex review chunks | volatile |
| `/tmp/tier4-{actionable,all}.json` | tier-4 findings | volatile |
| `research/forward-plan/stage3-live-results.md` | Stage-3 official result | durable |
| `research/forward-plan/stage3-k0-diagnosis.md` | k=0 root cause | durable |
| `research/forward-plan/routing-dogfood-results.md` | dogfood + failure channel | durable |

---

## Limitations

This section is the credibility core. Every limitation below is owned, not
buried.

1. **Production value is UNMEASURED.** We do NOT claim the loop has helped a
   single live route yet.
2. **k=0.** Value is structurally unmeasurable on the current corpus. The
   pre-registered criteria stand and will declare value or trigger deletion.
3. **Synthetic weights.** Every Stage-1 and Stage-3 number is labeled
   SYNTHETIC-WEIGHTS.
4. **Single-user corpus.** 117 cases from one user's tasks. No population claim.
5. **Judge reliability unvalidated.** Inter-judge agreement is UNDEFINED at k=0.
6. **`/tmp` artifacts are volatile.** Durable copies are listed in the
   [Reproduce](#reproduce) table.
7. **Clock validity is currently failing honestly.** Legacy pre-marker events
   dilute the instrumented rate; it rises as instrumented dispatches accrue.
8. **`recorded_failures = 0`.** The failure channel is proven mechanically
   (temp-DB dogfood) but has zero live signal yet.
9. **REAL replay arm is a no-harm control,** not a value measurement — no
   alternates were offered, so it cannot show value.
