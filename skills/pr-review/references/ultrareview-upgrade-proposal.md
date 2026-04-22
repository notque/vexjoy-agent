# ADR: Upgrade pr-review to Ultrareview-style Over-Generate + Verify + Dedupe Pipeline

## Status

**Proposed, shipping on PR #527 for combined methodology + proposal review.** Triggered by observation of Ultrareview executing against PR #527 on 2026-04-22. Previously drafted as a local working document under `adr/` (gitignored); relocated into `skills/pr-review/references/` on the same PR so reviewers see the proposal side-by-side with the methodology it proposes to change. Nothing here is implemented. The artifact exists to provoke a design conversation, not to land it.

Related branch: `refactor/pr-review-command-to-skill` (PR #527, in flight).

---

## How to review this proposal (meta)

This document lives on PR #527, which is explicitly a methodology-review pull request. The underlying ask on that PR: critique the current `skills/pr-review/SKILL.md` methodology and propose what would elevate it from "comprehensive" to "Ultra Review" quality. This proposal is a first attempt at that answer, informed by watching Ultrareview run against PR #527 itself. The recursion is intentional — the artifact being reviewed is a proposal for how to review things, observed by running the thing being proposed against the PR that proposes it.

**Review scope is dual. Reviewers are asked to critique both artifacts:**

1. **The current methodology in `skills/pr-review/SKILL.md`** — the 8-phase pipeline (scope → specialists → caller tracing → launch → aggregate → plan → fix → retro). What is missing? Where does the pass-through trust model fail? What would Ultra Review-grade rigor look like in that file?
2. **This proposal itself** — the over-generate + verify + dedupe architecture below. Is it the right answer, or a plausible-looking answer that would not survive a 2000-line diff? Is the observed Ultrareview schema faithful, or speculation dressed up as observation? Are the mechanics implementable as written?

**Neither artifact deserves rubber-stamp approval.** The skill has real gaps (enumerated in Context below). The proposal has real speculation (flagged inline under "Observations flagged as speculation vs observation"). Catching gaps in either is a successful review; catching gaps in both is a great one.

**Concrete things a reviewer should push back on** (seeded, not exhaustive):

- Is the severity taxonomy (`nit` / `normal` / `important` / `critical` / `blocker`) the right scale, or should it align with the toolkit's existing Critical / Important / Suggestion / Positive conventions?
- Is root-cause-key tuple-matching the right dedup mechanism, or does Ultrareview actually use semantic similarity, an LLM dedup judge, or something the UI trace did not expose?
- Is the 1:1 generation ratio (one candidate per changed line) realistic on a 2000-line diff, or does the pipeline need adaptive sampling before Find begins?
- Does the Verifier phase warrant a panel by default, or is single-agent + oracle-first the right economic tradeoff? The observed `corroborated_by` field suggests Ultrareview treats panel verification as first-class; this proposal currently treats it as optional. Which is right?
- Is the existing `parallel-code-review` skill subsumed by this pipeline, or does it retain independent value? If subsumed, migration must retire it.
- Is two weeks of shadow-running the right validation window, or should it be N PRs (e.g. the next 20) to normalize for size variance?

**Reviewers should feel free to reject this proposal's framing and counter-propose a different pipeline shape entirely.** The point of shipping this artifact on PR #527 is to provoke a better design, not defend this one. A reviewer who writes "the over-generate + verify + dedupe frame is wrong; here is what I would do instead" gives the highest-value review possible, even if — especially if — it invalidates every subsequent section of this document.

---

## Context

### What the current `skills/pr-review/SKILL.md` does

`skills/pr-review/SKILL.md` is an 8-phase comprehensive review pipeline:

1. Determine review scope (diff surface)
2. Identify applicable reviews (which specialists apply)
3. Detect languages and domain (Go/Python/TS/Md; org detection; gopls MCP integration)
3.5. **Caller tracing** (Go-only; mandatory for signature/semantic changes)
4. Launch review agents (`comment-analyzer`, `pr-test-analyzer`, `silent-failure-hunter`, `type-design-analyzer`, `code-reviewer`, `code-simplifier`) — sequential by default, parallel on request
5. Aggregate results (bucket by severity: Critical / Important / Suggestion / Positive)
6. Provide action plan
7. Apply fixes (if requested)
8. Retro learning (record reusable patterns to `learning.db` via `feature-state.py retro-record-adhoc`)

**Trust model: specialists own their domain; their output is the output.** Each reviewer is presumed calibrated. Findings pass straight through to the aggregation step. Deduplication is not an explicit phase — if two specialists find the same bug from different angles, the user sees two findings.

### What we observed Ultrareview doing

On PR #527 (the pr-review skill relocation, 16 changed lines), Ultrareview ran a four-phase pipeline visible as a live UI trace:

1. **Setup** (preparation; details not exposed in the UI)
2. **Find** — generated **15 candidate findings** for a 16-line diff. Ratio ≈ 1 candidate per line changed. Deliberately noisy.
3. **Verify** — each candidate independently checked against source. Real-time counter: `4 confirmed · 10 refuted · 1 verifying`.
4. **Dedupe** — visible as pending; had not started when captured.

Confirmed findings (4 of 15):

- `user-invocable: false breaks /pr-review slash invocation` — SKILL.md:4
- `allowed-tools renamed Agent→Task but body still references 'Agent tool'` — SKILL.md:4
- `Removing argument-hint leaves $ARGUMENTS placeholder with no substitution source` — SKILL.md:1
- `skills/INDEX.json not regenerated after skill scaffold` — SKILL.md:14

Refuted findings (10 of 15) — important to understand, because they fell into **two distinct categories**:

- **Category A — Weaker restatements of a confirmed finding.** Example: `argument-hint frontmatter dropped without replacement` was refuted; `Removing argument-hint leaves $ARGUMENTS placeholder with no substitution source` was confirmed. Same underlying issue, but only the claim with the causal chain survived. A bare observation ("it was dropped") was filtered out as not-a-defect without the "…and here's why that breaks things" clause.
- **Category B — Duplicates of other confirmed findings stated differently.** Example: `Body says 'Agent tool' but frontmatter renamed it to 'Task'` was refuted because `allowed-tools renamed Agent→Task but body still references 'Agent tool'` (semantically identical) was already confirmed.

The UI kept refuted findings visible (line-through styling) with expandable reasoning, so the reviewer could audit "why did you not flag X?" — no silent drops.

### What is structurally different

The current skill trusts specialists to self-censor. Ultrareview trusts a verifier to post-censor.

| Dimension | Current `pr-review` | Ultrareview |
|-----------|--------------------|-| 
| Generator posture | Precision-first (emit only high-confidence findings) | Recall-first (emit broadly, accept noise) |
| Filter mechanism | Implicit (in each specialist's prompt) | Explicit (separate Verify phase) |
| Dedup mechanism | Implicit (readers mentally merge) | Explicit (separate Dedupe phase) |
| Trust anchor | The specialist's judgment | The verifier's evidence against source |
| Failure mode | Silent false negatives (specialist self-censored) | Loud false positives filtered at Verify |
| Transparency | Findings appear at end | Findings stream with live verdicts |

The insight: **these compose.** Specialists can become Generate-phase candidate sources (encouraged to over-generate), a new Verify phase filters, a new Dedupe phase collapses, and the existing Aggregate phase reports.

---

## Decision

Adopt a three-layer review architecture that composes with the toolkit's existing specialist dispatch:

1. **Candidate generation** — existing specialists (and optionally additional narrow generators), re-calibrated to over-generate rather than self-censor. Their output is a candidate set, not a conclusion.
2. **Verification (NEW)** — each candidate is independently checked against source of truth. Produces a binary verdict (confirmed/refuted) with cited evidence.
3. **Dedupe (NEW)** — confirmed candidates that address the same root cause are merged, with evidence combined rather than either dropped.

The existing Aggregate, Action-Plan, Apply-Fixes, and Retro phases survive unchanged — they operate on the dedup'd set instead of raw specialist output.

**Why now**: the observed Ultrareview run on PR #527 produced 4 non-overlapping, actionable, well-substantiated findings from a 16-line diff. The current `pr-review` skill has never been benchmarked on this PR; we don't know whether it would have produced the same set, a subset, or a noisier set. This ADR proposes the architecture; the migration plan proposes the shadow-comparison experiment.

---

## The Proposed Pipeline

### Phase Catalog

| Phase | Input | Output | Success criterion | Failure mode |
|-------|-------|--------|-------------------|--------------|
| Scope | git diff or PR ref | `ChangedFiles[]`, `DomainTags[]`, language set | diff parsed, ≥1 language detected, scope non-empty | empty diff (abort with "nothing to review"); binary-only diff (degrade to metadata review) |
| Generate | `ChangedFiles[]`, `DomainTags[]`, retro context | `CandidateFinding[]` (over-generated) | candidate count ≥ `1 per K lines changed` (default K=1; floor 5, ceiling 200) | specialists silent on signal-bearing code (escalate: re-prompt with "you must surface at least N candidates in this file"); diff ≥ 1000 lines (batch) |
| Verify | `CandidateFinding[]` | `VerdictedFinding[]` | every candidate has a binary verdict with cited source lines | verifier disagrees with itself on re-run (flag as "needs human"); verifier unable to open cited file (candidate auto-refuted with `verdict-reason: uncitable`) |
| Dedupe | `VerdictedFinding[]` where `verdict=confirmed` | `DedupedFinding[]` | no two surviving findings share a `root-cause-key` | dedupe collapses distinct findings (detect: if root-cause-key collision has conflicting severities AND conflicting file:line, surface as "disputed" rather than merge) |
| Aggregate | `DedupedFinding[]` + `RefutedFinding[]` (for audit trail) | PR Review Report (severity-bucketed) | Critical / Important / Suggestion / Positive buckets present; refuted-set collapsed section included | aggregation drops a finding (forbid: every confirmed → bucketed) |
| Retro | review artifacts (confirmed + refuted + verdict reasons) | scoped learnings recorded via `retro-record-adhoc` | learnings map to detected domain tags; bare observations not recorded | learnings too generic (gate on quality rubric already in current Phase 8) |

### Data contracts

**`CandidateFinding`**

```jsonc
{
  "id": "cf-<uuid>",
  "file": "skills/pr-review/SKILL.md",
  "line": 4,
  "claim": "user-invocable: false breaks /pr-review slash invocation",
  "specialist_source": "code-reviewer",      // which Generate-phase agent emitted it
  "claim_strength_estimate": "causal",       // "observation" | "causal" | "evidential"
  "suggested_severity": "critical",
  "raw_evidence": "<optional: snippet the generator saw>"
}
```

`claim_strength_estimate` is a self-report from the generator. It is a hint to the verifier, not a truth. The verifier may override.

**`VerdictedFinding`** — schema aligned with observed Ultrareview output on PR #527.

Fields marked `// OBSERVED` appeared verbatim in the remote review's JSON payload. Fields marked `// PROPOSED` are toolkit-specific extensions where the live trace did not expose internal state.

```jsonc
{
  "bug_id": "bug_011",                       // OBSERVED — stable ID across phases
  "name": "skills/INDEX.json not regenerated — routing triggers unreachable", // OBSERVED — short label
  "severity": "normal",                      // OBSERVED — see taxonomy below
  "file_path": "skills/pr-review/SKILL.md",  // OBSERVED
  "start_line": 14,                          // OBSERVED
  "end_line": 20,                            // OBSERVED — note: line range, not single line
  "pr_comment": "...",                       // OBSERVED — user-facing comment (markdown)
  "reasoning": "### What the bug is ...",    // OBSERVED — structured proof (see Verify mechanics)
  "corroborated_by": null,                   // OBSERVED — panel support; null when single-verifier
  "source_bug_ids": ["bug_011"],             // OBSERVED — provenance; self-pointing if not merged
  "created_at": 1776888438.571896,           // OBSERVED — unix timestamp float
  "_file_path": "/tmp/work/reports/bug_011_report.json", // OBSERVED — per-bug artifact path

  // PROPOSED — toolkit extensions (not exposed in the final JSON):
  "verdict": "confirmed",                    // "confirmed" | "refuted"
  "verdict_reason": "confirmed-with-evidence", // see taxonomy in Verify mechanics
  "duplicate_of": null,                      // set when verdict_reason == duplicate-of
  "specialist_source": "code-reviewer"       // which Generate-phase agent emitted the candidate
}
```

**Severity taxonomy** (observed): `nit`, `normal`, `important`, `critical`, `blocker`. Only `nit` and `normal` appeared on PR #527's output; higher levels are inferred from Ultrareview's apparent scale. This differs from the current `skills/pr-review/SKILL.md` taxonomy (`Critical / Important / Suggestion / Positive`); the v2 pipeline must pick one. Recommend adopting the observed scale (`nit` / `normal` / `important` / `critical` / `blocker`) because it cleanly maps "it runs but it's ugly" (nit) from "it runs but with broken contracts" (normal) from "it fails" (critical/blocker), where the current scale conflates "important" with "critical" and lacks a lower-severity shelf for prose mismatches.

**Severity is assigned at Verify, not at Generate.** On PR #527, `bug_004` (prose says "Agent tool", frontmatter says "Task") and `bug_009` (missing README row) both landed as `nit`, while `bug_011` (INDEX not regenerated) landed as `normal`. These severities reflect observed impact *after verification* (cosmetic vs. functional break), which means the generator cannot assign them without doing verification's work. Move severity assignment into the Verify phase contract.

**`DedupedFinding`** — schema aligned with observed merge output (`merged_bug_001` on PR #527).

```jsonc
{
  "bug_id": "merged_bug_001",                // OBSERVED — "merged_" prefix indicates dedup
  "name": "Skill entry point broken: user-invocable:false + dead $ARGUMENTS", // OBSERVED
  "severity": "normal",                      // OBSERVED — max() of merged severities
  "file_path": "skills/pr-review/SKILL.md",  // OBSERVED
  "start_line": 4,                           // OBSERVED
  "end_line": 4,                             // OBSERVED
  "pr_comment": "...",                       // OBSERVED — merged comment
  "reasoning": "...",                        // OBSERVED — contains inline sibling-refutation rationale (see Dedupe mechanics)
  "corroborated_by": null,                   // OBSERVED
  "source_bug_ids": ["bug_001", "bug_005"],  // OBSERVED — provenance of merge
  "created_at": 1776888467.5077515,          // OBSERVED
  "_file_path": "/tmp/work/reports/merged_bug_001_report.json", // OBSERVED

  // PROPOSED — toolkit extensions:
  "root_cause_key": "frontmatter:user-invocable:breaks-slash-invocation",
  "contributing_specialists": ["code-reviewer", "comment-analyzer"],
  "merged_evidence": ["...", "..."]          // union of verdict_evidence from all merged survivors
}
```

Note: `source_bug_ids` is present on **all** findings, not just merged ones. Non-merged findings self-point (`source_bug_ids: ["bug_011"]`). This gives a uniform provenance trail — downstream consumers (Retro, docs, follow-up PRs) always know which generator output contributed, whether or not merging happened.

### Verify phase mechanics

**What the verifier does**:

1. Opens the cited file at the cited line range.
2. Reads enough surrounding context to understand whether the claim is true, false, or vacuous in context. For Go, this includes running `gopls` tools (`go_file_context`, `go_symbol_references`) on cited symbols. For TS, this includes consulting `ts-morph` or `tsc`. For Python, `pyright` or `mypy`. For config/markdown, full-file read + cross-reference grep.
3. Emits a verdict with cited evidence: the command it ran, the observed output, the expected behavior, and the resolved verdict.

**Verdict reason taxonomy** (names chosen to match observed Ultrareview categories):

| Reason | Meaning | Example from PR #527 |
|--------|---------|----------------------|
| `confirmed-with-evidence` | Claim is true and the consequence is a defect | `user-invocable: false breaks /pr-review slash invocation` |
| `bare-observation` (Category A) | Claim is literally true but the author did not articulate why it's a defect; a stronger claim with causal chain exists | `argument-hint frontmatter dropped without replacement` (refuted; stronger sibling `$ARGUMENTS has no substitution source` was confirmed) |
| `duplicate-of` (Category B) | Claim is semantically identical to a stronger claim already confirmed | `Body says 'Agent tool' but frontmatter renamed it to 'Task'` → duplicate of `allowed-tools renamed Agent→Task but body still references 'Agent tool'` |
| `not-a-defect` | Claim is true but describes intended behavior | e.g. "SKILL.md references internal-only skills" — true, but that's the point of a skill |
| `uncitable` | Verifier could not open or locate the cited code | rare; usually indicates hallucination |

A verdict is not valid unless `verdict_evidence.command_run` and `verdict_evidence.observed` are populated. This is a hard rule, because a verifier that only reasons about whether a finding is correct — without opening the file — is indistinguishable from the generator that produced the candidate. Verify must load source-of-truth context the generator didn't.

**What elevates a candidate from "claim" to "confirmed defect"**:

1. The claim is not a bare observation. It must include a causal chain to user-visible consequence, OR the verifier must supply one.
2. The claim is not a weaker restatement of another confirmed finding.
3. The cited file:line exists and the surrounding code behaves as the claim asserts.
4. The consequence is observable: a test would fail, a user workflow would break, a security invariant would be violated, or a maintainability metric would degrade. "Could theoretically be cleaner" is not a consequence.

**Verdict determinism**:

Verdicts should be deterministic across reruns on the same diff + same verifier. They will not always be. Mitigation:

- The verifier is instructed to cite command output (`command_run` + `observed`) rather than memory. Cited evidence is stable across runs in a way reasoning is not.
- If a rerun produces a different verdict on the same candidate, flag as `needs-human` and surface both verdicts in the report. Never silently pick one.
- Spot-check: periodically (e.g., every 10th PR) run a second-opinion verifier against the same candidate set; diverging verdicts are a signal to recalibrate.

**Tooling as oracle**:

For certain claim types, a deterministic tool can replace LLM verification:

| Claim type | Oracle | Example |
|-----------|--------|---------|
| "Caller not updated after signature change" | `gopls.go_symbol_references` | Go Phase 3.5 caller tracing folds into Verify |
| "Type error introduced" | `tsc --noEmit`, `pyright`, `mypy` | language-specific type-check |
| "YAML does not parse" | `yq`, `python -c 'yaml.safe_load(...)'` | frontmatter validation |
| "Referenced file does not exist" | `test -f` | cross-reference checking |
| "INDEX.json out of sync" | `scripts/generate-skill-index.py --check` | toolkit-specific |

When an oracle is available, Verify should prefer it over LLM reasoning. This follows the toolkit principle "everything that can be deterministic, should be" — the verifier is an LLM by necessity for soft claims, but oracles exist for hard claims, and using them where they apply collapses verification cost.

**Required output structure (derived from observed Ultrareview `reasoning` fields)**:

Every confirmed finding's `reasoning` field must satisfy the following structure. This is not stylistic — it is what makes the verdict auditable, and without it the Verify phase reduces to "a second LLM agreeing with the first" which is not verification.

1. **Numbered step-by-step proof**, with each step citing either a file:line read or a shell command.
   - Observed example from `bug_011`: *"(1) `skills/INDEX.json` line 3: `\"generated\": \"2026-04-21T20:19:43Z\"`. (2) This commit (`ffed6c9`) is dated `2026-04-22T12:51:44-07:00` — after the index timestamp. (3) `grep -c pr-review skills/INDEX.json` → `0`. (4) `grep -c pr-workflow skills/INDEX.json` → `3` (demonstrating INDEX.json is the authoritative manifest …). (5) A user typing \"review this PR\" therefore cannot be routed to `pr-review` by `/do` — the fallback handler runs instead."*
   - The proof is reproducible: any reader can run the same commands and see the same output. This is what distinguishes a verdict from a hunch.

2. **Cited shell commands with observable outputs**, not paraphrased reasoning.
   - Observed examples: `git diff b4c3e1d..HEAD --name-only`, `grep -c pr-review skills/INDEX.json`, `ls commands/pr-review.md`.
   - Rule: if the claim is "X is absent", cite a command whose output is empty. If the claim is "X is present with value Y", cite a command whose output shows Y.

3. **Cross-references to authoritative repo documents that establish contracts being violated.**
   - Observed on `bug_009`: cited `skills/docs-sync-checker/SKILL.md:140` as the authoritative rule classifying missing-README entries as HIGH severity. Cited `skills/README.md:52` as the section where the new skill would belong.
   - Observed on `bug_011`: cited `skills/skill-creator/SKILL.md:213-225` as the authoritative rule that INDEX regeneration is commit-gating.
   - Rule: the verifier must identify WHICH repo convention the finding violates, citing the document that defines the convention — not just "this looks wrong." Contract-violation claims without cited contracts are `bare-observation` refutations.

4. **Honest concession when the candidate's claim is partially overstated.**
   - Observed on `bug_009`: full subsection titled *"Addressing the refutation — it is partially correct"* where the verifier concedes the candidate overstated its case (claimed "every other top-level skill has a row" — false; 13 other skills are unindexed) and explicitly scales back the finding's framing accordingly. Final verdict is still confirmed, but with a truthful narrower claim.
   - Rule: the verifier is not a rubber stamp. When a candidate is right in spirit but wrong in specifics, the verifier must surface the specifics that are wrong and adjust the claim, not silently pass through. This is the Verify phase's adversarial posture on its own candidates — it is a feature, not a contamination.

5. **Explicit "How to fix" block with preferred vs. alternative paths.**
   - Observed on every finding: a *"### How to fix"* or *"### Fix"* section naming the exact change. On `merged_bug_001`, the verifier offered *"Preferred: change line 4 to `user-invocable: true`"* followed by *"Alternative: keep `user-invocable: false` but (a) rewrite line 61 ... and (b) update all callers listed above"*.
   - Rule: a finding without a fix path is incomplete. The Verify phase must produce an actionable remediation, not just a diagnosis.

6. **Uniform provenance via `source_bug_ids`.**
   - Observed: every finding carries `source_bug_ids` even when no dedup occurred (`bug_011` has `source_bug_ids: ["bug_011"]`).
   - Rule: Verify emits `source_bug_ids` as a single-element self-pointing array; Dedupe may later expand it. Downstream consumers see a uniform provenance trail.

These six requirements are collectively what elevates a verdict from "second LLM opinion" to "auditable conclusion." A Verify output that omits any of them is indistinguishable from a rephrased generator claim, and the pipeline loses its integrity.

### Dedupe mechanics

**Root-cause-key computation**:

Two findings collapse iff they share a `root_cause_key`, computed as a tuple of:

1. `file` (exact match)
2. `line_bucket` (5-line tolerance — findings within 5 lines of each other about the same file are candidates for merger)
3. `symbol_or_concept` — extracted noun phrase from the claim. Examples: `user-invocable`, `argument-hint/$ARGUMENTS`, `Agent→Task rename`. This is an LLM extraction, not a regex.
4. `diagnostic_category` — from a fixed enum: `frontmatter-field`, `body-code-drift`, `missing-error-handling`, `test-coverage-gap`, `naming-inconsistency`, `type-invariant-violation`, `caller-unupdated`, `convention-deviation`, `dead-code`, etc.

Two findings merge when `(file, line_bucket, symbol_or_concept, diagnostic_category)` match. Line-bucket tolerance is deliberately loose because specialists cite the same issue at different lines (the declaration line vs the usage line).

**Severity on merge**: keep the highest. Log the downgrades in the `DedupedFinding.merged_evidence` as a note ("code-reviewer suggested medium; silent-failure-hunter suggested high → kept high"). This preserves the calibration audit trail for Retro.

**Complementary evidence**: if specialist A cited the declaration site and specialist B cited the usage site, the merged finding contains both. This is strictly better than either original — the reader sees the full picture without chasing cross-references.

**Disputed merges**: if two candidates have a matching `(file, symbol_or_concept)` but different `diagnostic_category`, do NOT merge. Surface both. Category disagreement is diagnostic information (different specialists see different defects); collapsing it loses signal.

**What does NOT get merged**:

- Same file, different symbols → different root causes → keep separate.
- Same symbol, different diagnostic categories → keep separate.
- Same concept, different files → architectural smell distinct from a single-file defect → keep separate but cross-link.

**Merged findings must carry sibling-refutation rationale inline** (observed on PR #527's `merged_bug_001`):

When Dedupe merges two or more confirmed findings into one, the merged finding's `reasoning` field must include a named subsection explaining why the sibling candidates were subsumed. This is mandatory; without it, a downstream reader cannot reconstruct why seemingly-distinct observations collapsed into one claim.

Observed format on `merged_bug_001` (from bug_001 + bug_005 → merged): the reasoning field contained an italicized paragraph:

> *"(Addressing the duplicate-framing refutation: the refutation is correct that `$ARGUMENTS` substitution DOES work for other `user-invocable: true` skills like `workflow-help` — so this is not a separate defect. It is a symptom of the same root cause: the broken slash entry point. Flipping `user-invocable: true` restores both. I'm reporting it here because both symptoms share one fix and both concrete lines need review attention.)"*

Two things this paragraph does that the v2 pipeline must preserve:

1. **Names the sibling finding** that was subsumed (`$ARGUMENTS` substitution bug) and acknowledges that — *in isolation* — the sibling might have been refuted as "works fine for other skills."
2. **Reconstructs the root cause** (`broken slash entry point`) that makes both siblings the same defect when taken together.

Rule: the merged finding's reasoning must answer the question *"why is this one finding instead of two?"* in explicit prose the reader can audit. Dedupe that silently drops siblings loses the reasoning chain; the observed pattern is to keep the chain visible as a transparency mechanism.

**Merged severity rule** (observed): take `max()` of contributing severities. On `merged_bug_001`, bug_001 and bug_005 were both `normal`, so the merged severity is `normal`. If one had been `critical` and the other `nit`, the merged finding would be `critical`. This matches the Severity-on-Merge rule proposed above; the observed output confirms it.

### Generator prompt requirements (derived from Verify's demands)

Because Verify requires the 6 output characteristics listed above, the Generate phase must emit candidates with enough structural information for Verify to do its job without re-discovering the claim from scratch. Generator prompts must therefore instruct specialists to produce:

1. **A claim with a causal chain, not a bare observation.** A bare observation ("argument-hint frontmatter dropped") will be refuted by Verify as Category A (`bare-observation`), so the generator wastes tokens by emitting it. Specialists must be prompted to articulate *what user-visible consequence* follows from the observation, e.g. "argument-hint frontmatter dropped, which breaks the `$ARGUMENTS` substitution chain that Phase 1 relies on."

2. **A `file_path`, `start_line`, `end_line` range** (not a single line). Observed Ultrareview output uses line ranges even when `start_line == end_line`, because some defects span multiple lines and the verifier needs the full range to open the right context. Generators that emit only single lines force Verify to guess.

3. **A `claim_strength_estimate` self-report**: `"observation"`, `"causal"`, or `"evidential"`. This hints to the Verifier about the candidate's confidence level. Candidates self-reporting as `"observation"` are pre-flagged for Category A scrutiny; candidates self-reporting as `"evidential"` should include the cited evidence already in the candidate. The Verifier may override this estimate (it is a hint, not a verdict), but the hint helps route verifier effort.

4. **A `suggested_severity`** (`nit` / `normal` / `important` / `critical` / `blocker`). The Verifier will override if observed impact disagrees, but the generator's estimate is a useful prior. Specialists must be trained on the severity rubric: cosmetic prose mismatch = `nit`; broken contract with workaround = `normal`; broken contract with no workaround = `important` or higher.

5. **A diagnostic category tag** from the fixed enum (`frontmatter-field`, `body-code-drift`, `missing-error-handling`, `test-coverage-gap`, `naming-inconsistency`, `type-invariant-violation`, `caller-unupdated`, `convention-deviation`, `dead-code`, …). This is the same enum used by Dedupe to compute `root_cause_key`. If the generator does not emit this, Dedupe has no signal for merging and the pipeline degrades to text-similarity matching.

Implementation: the existing specialist prompts (`comment-analyzer`, `silent-failure-hunter`, etc.) currently produce free-form findings. They need a prompt revision to emit the structured candidate shape. The revised prompts should:

- Request JSON output matching the `CandidateFinding` schema (not markdown prose).
- Include a **calibration example** showing the difference between a bare observation and a causal claim.
- Instruct specialists to **over-generate**: "emit every candidate you see, even ones you're uncertain about — the Verify phase will filter. Under-generation costs recall; over-generation costs tokens. We're token-rich and recall-poor, so err toward emitting."

This is a prompt-engineering task substantial enough that it should be tracked as a separate ADR or feature ticket, but its requirements are dictated by this ADR's Verify contract.

### Transparency & auditability

- **Surface WIP state during Verify**: emit structured progress ("3 confirmed · 8 refuted · 4 verifying · 15 total") so the user sees the verifier actively doing work rather than waiting on an opaque blob. This matters for trust calibration — a review that outputs findings only at the end gives the reader no basis to assess how thorough the process was.
- **Keep refuted findings in the report**: collapse them behind an expandable section, do not drop them silently. Include `verdict_reason` so the reader can audit "why wasn't X flagged?". This is a direct port of Ultrareview's line-through UI — refuted findings are not failures to hide, they are the recall-first posture doing its job.
- **Per-finding artifact persistence** (observed): Ultrareview persists each bug to its own JSON file (`_file_path: "/tmp/bughunter_work/reports/bug_011_report.json"`) in a run-scoped work directory. The toolkit should mirror this pattern: write each `VerdictedFinding` to `<toolkit-state>/pr-review/<run-id>/<bug_id>.json` so individual findings are addressable by ID for tooling (link-back in PR comments, retro-record lookup, follow-up agent dispatch keyed on a specific finding). The current single-file `pr-review-findings.md` output is preserved as a human-readable aggregate but is not the authoritative store.
- **Log the full candidate set as an artifact**: also write `candidates.json` (pre-Verify), `verdicts.json` (post-Verify, including refuted), and `deduped.json` (post-Dedupe) at the run-scoped level. Retro consumes all three to learn both what got confirmed AND what got refuted — the refuted set carries generator-calibration signal that confirmed-only logs destroy.

---

## Composition with existing toolkit

### Pipeline-index registration

Register this as `pr-review` (reuse the existing pipeline identifier), incrementing version from implicit 1.x to `2.0.0`. Add a `phases` array to the existing entry in `skills/workflow/references/pipeline-index.json`:

```jsonc
"pr-review": {
  "file": "skills/pr-review/SKILL.md",
  "description": "Over-generate + verify + dedupe PR review with specialist generators and retro capture.",
  "triggers": ["pr review", "review pr", "pull request review", "comprehensive pr review", "review pull request"],
  "category": "code-review",
  "user_invocable": true,
  "version": "2.0.0",
  "phases": ["SCOPE", "GENERATE", "VERIFY", "DEDUPE", "AGGREGATE", "RETRO"],
  "pairs_with": ["parallel-code-review", "systematic-code-review", "full-repo-review", "sapcc-review"]
}
```

The phase names intentionally differ from the current skill's numbered phases — `pr-review-v2` is pipeline-shaped (named phases, explicit artifacts) rather than prose-shaped (numbered sections). This aligns with "Everything Should Be a Pipeline" in PHILOSOPHY.md.

### Specialist reuse

Existing review agents become Generate-phase candidate sources:

| Specialist | Current role | Role under v2 |
|-----------|-------------|---------------|
| `comment-analyzer` | Verifies comment accuracy | Generates candidates for comment-rot defects. Permitted to be noisy. |
| `pr-test-analyzer` | Reviews test coverage | Generates candidates for test-gap defects. Permitted to claim "this path is untested" without proving it's important — Verify will decide. |
| `silent-failure-hunter` | Finds silent failures | Generates candidates for error-swallowing defects. |
| `type-design-analyzer` | Rates type design | Generates candidates for type-invariant defects. |
| `code-reviewer` | General CLAUDE.md compliance | Generates candidates for general quality defects. |
| `code-simplifier` | Polishes code | Stays in the Apply-Fixes phase (not a generator). |

**Prompt change required**: each generator's prompt currently says something like "only flag issues you're confident about." This must flip to "surface every candidate finding you see; the verifier will filter. Self-censoring here is worse than over-generating, because you are the only one looking from this angle." This is a meaningful calibration shift — see Tradeoffs § for risk.

### Verifier agent

Proposed default: a new `review-verifier` agent (to be created in its own ADR, not this one). Rationale:

- The verifier's job is narrow and well-defined: given a candidate, open the cited file, run an applicable oracle if one exists, and emit a verdict with evidence. This is not generalist code review; it is adversarial claim-checking.
- Making it a separate agent means its prompt can include specific instructions ("you are trying to disprove each claim; your success metric is refutation with evidence, not confirmation"). Today's generalist agents drift toward helpful confirmation, which is exactly wrong for this role.
- Alternative considered: reuse `code-reviewer` with a `verify-mode` flag. Rejected: flag-driven agents rarely respect the flag under pressure, and the trust boundary is worth a separate agent file.

### Retro integration

Phase 6 (Retro, currently Phase 8) gains new signals to record:

- **Generator calibration**: for each specialist, track refutation rate over time. If `comment-analyzer` is 80% refuted on Go PRs, record `generator-calibration:comment-analyzer:go:refute-rate:0.80`. This becomes actionable: is the specialist miscalibrated, or is the verifier too strict?
- **Recurring `bare-observation` patterns**: if the same claim shape gets refuted as `bare-observation` across PRs, that's a generator prompt bug — the specialist is emitting observations without causal chains. Record as `generator-prompt-gap:<specialist>:missing-causal-chain`.
- **Oracle-detectable claims**: if a claim was verified by an oracle (not LLM reasoning), record `oracle-success:<claim-category>:<tool>`. This builds the oracle catalog over time and is a precondition for moving those categories from LLM verification to deterministic verification.

### Relationship to Caller Tracing (current Phase 3.5)

Caller tracing is already a verification-of-sorts for Go signature changes. Under v2, it folds in as follows:

- Caller tracing becomes a **mandatory Generate-phase step** when the diff modifies Go signatures. It emits candidates of category `caller-unupdated` with structured evidence (from `gopls.go_symbol_references`).
- Because `gopls` is deterministic, these candidates are verified by the oracle path in Verify, not LLM reasoning. They come in with `claim_strength_estimate: evidential` and pass Verify trivially.
- Generalizing to TS/Python/Swift/Kotlin/PHP is out of scope for this ADR — each language needs its own oracle choice and its own caller-tracing implementation. Tracked as "Not doing (yet)".

### Relationship to `parallel-code-review`

`parallel-code-review` is the 3-reviewer Fan-Out/Fan-In pattern (Security, Business Logic, Architecture). Two plausible integrations:

1. **`parallel-code-review` becomes a Generate-phase strategy.** Under v2, the user can select the specialist roster: the current `pr-review` specialists, OR the 3-reviewer panel, OR both. Verify and Dedupe are strategy-agnostic — they consume `CandidateFinding[]` regardless of source.
2. **`parallel-code-review` stays standalone.** Different trust model: 3-reviewer dedup is done by the aggregator in Phase 3 of that skill, without a Verify phase. Users who want the specialist roster use `pr-review`; users who want the 3-lens panel use `parallel-code-review`.

**Recommendation**: option 1. It preserves existing `parallel-code-review` surface area while making its findings benefit from Verify+Dedupe. This is tracked as an Open Question because it's a meaningful refactor of `parallel-code-review` itself.

### Relationship to `full-repo-review`, `sapcc-review`, `comprehensive-review`

These are out-of-scope for this ADR. They are wave-based, multi-agent, whole-repo reviews; `pr-review` is diff-scoped. The Verify+Dedupe pattern is applicable to them, but the token economics are very different (a 2000-file review cannot afford 1-per-line candidate generation). Separate ADR if/when the pattern graduates.

---

## Tradeoffs & risks

### Token cost

Verify visits every candidate. With 1-per-line candidate generation on a 200-line diff, that's 200 verify calls. At even 2k output tokens each, that's a measurable cost per review.

Mitigations:

- **Oracle preference**: oracles (gopls, tsc, etc.) are near-free compared to LLM verification. Every oracle-verifiable claim taken off the LLM path reduces cost linearly.
- **Batch verify**: bundle 5-10 candidates per Verify call when candidates are in the same file. The verifier reads the file once, emits N verdicts. Same accuracy at ~1/5 the call count.
- **Claim-strength gating**: if a generator self-reports `claim_strength_estimate: causal` (with cited evidence), skip LLM verification and accept with a perfunctory oracle check. Only `observation`-strength candidates enter full Verify. This makes generator self-reporting load-bearing, so the generators' prompts must be calibrated carefully.
- **Adaptive K**: default K=1 (one candidate per line) is for small diffs. For large diffs, scale K down — a 2000-line diff at K=1 is catastrophic. Propose K = `max(1, 50/sqrt(lines_changed))` or similar.

### Latency

Verify and Dedupe are sequential after Generate. On a review that previously took 2 minutes, this may become 5-7 minutes. Mitigations:

- **Stream verdicts**: Verify emits verdicts incrementally; the user sees progress in real time (Ultrareview's `4 confirmed · 10 refuted · 1 verifying` counter).
- **Parallel Verify**: candidates within a file can be verified in parallel if the verifier reads the file once and forks reasoning per candidate. This is an agent-architecture question (does the Task tool support fork-style dispatch?) — open question.

### Verifier drift

If the verifier has blind spots (e.g., systematically refutes security findings because the generator's security claims tend to include speculative framing), confirmed findings inherit those blind spots and the review silently misses defects.

Mitigations:

- **Diversity between generator and verifier context**: the verifier MUST load source-of-truth context the generator did not. If both are reading the same diff with the same instructions, Verify is LARP, not verification. This is why a separate `review-verifier` agent with a distinct prompt matters — not just instruction-level "verify this" but structural load-time difference.
- **Periodic second-opinion spot checks**: every Nth review, dispatch a second verifier with a different model or different prompt. Divergence between verifiers is the signal that calibration has drifted.
- **Refute-rate monitoring**: if the overall refute rate trends toward 100% or 0%, the verifier is broken. Healthy rate should sit around 60-80% refute (per the observed Ultrareview: 10/15 = 66%).

### Specialist calibration shift (false-positive fatigue)

Asking generators to over-generate shifts their error distribution from false-negative (miss bugs) toward false-positive (report non-bugs). If Verify catches them, the user never sees the noise. If Verify has any miss rate, the user's experience worsens, because noisy confirmed findings erode trust faster than missing findings do.

Mitigations:

- **Hold Verify accountable, not the generators**: if noise reaches the user, the fix is Verify calibration, not rolling back generator over-generation. Rolling back generators defeats the recall-first posture.
- **Update specialist prompts with examples**: include in each generator's prompt an example of a `bare-observation`-class finding, flagged as "this is the minimum quality bar; anything weaker than this will be refuted, but it's better to submit a weak one than suppress a real one." Teach calibration by example.
- **Maintain a "generator debt" retro topic**: if `comment-analyzer`'s refutation rate climbs over time on the `bare-observation` reason, that's a prompt-engineering debt item, not a per-PR problem.

### False sense of rigor

The most insidious risk. If the verifier uses the same context as the generator, the Verify phase is a rubber stamp wearing a lab coat. Users will trust the "confirmed" findings more because they passed verification — but the verification was content-free.

Mitigations:

- **Contract: verifier must cite a command output, not reasoning.** The `verdict_evidence.command_run` and `verdict_evidence.observed` fields are non-optional. This is the toolkit's "verifier pattern" principle applied concretely — a verifier that cannot produce a falsifiable check did not verify.
- **Audit the verifier's tool use**: if `command_run` is empty across N consecutive verdicts, the verifier is LARPing. Hook or script this check.
- **Oracle preference as enforcement**: where an oracle exists, use it. LLM-only verification on a claim that has an available oracle is a verification failure, not a verification.

### Integration risk with PR #527

PR #527 is relocating `pr-review` from a command to a skill. That refactor must land first. This ADR's implementation cannot start until #527 merges, because the pipeline described here targets the skill form.

### Scope creep risk

The Verify+Dedupe pattern is seductive and generalizes obviously to every other review skill (`parallel-code-review`, `systematic-code-review`, `full-repo-review`, `sapcc-review`). Each has different economics. Resist the temptation to change all of them at once. Land on `pr-review` first, prove the pattern, then propose per-skill extensions as separate ADRs.

---

## Open questions

These are genuine uncertainties, not TODOs:

1. ~~**Verifier: single agent or panel?**~~ **Resolved by observation.** Ultrareview's output schema includes a `corroborated_by` field, which was `null` on all four findings in the PR #527 run. This means panel verification is a real first-class feature of the upstream design, used selectively, not universally. Recommendation for v2: default to single verifier; gate panel activation on `severity >= important` candidates OR a `--paranoid` flag. The remaining open question is only *when* to activate the panel, not *whether* to support it.
2. **Over-generation parameterization**: should the user be able to tune aggressiveness via `/pr-review --noise-level=aggressive|moderate|conservative`? Aggressive = K=2 (2 candidates per line); moderate = K=1 (current proposal); conservative = falls back to today's specialist self-censor posture. Cheap to implement, hard to calibrate the defaults.
3. **Phase 3.5 generalization**: caller tracing is Go-only today (gopls). Extending to TS (ts-morph), Python (pyright), Swift (sourcekit-lsp), Kotlin (kotlin-lsp), PHP (phpactor) is each a separate ADR. In what order? Proposal: follow toolkit usage frequency — TS first, then Python, then Swift. But the toolkit doesn't currently surface usage telemetry, so this is a guess.
4. **`parallel-code-review` integration**: option 1 (fold as a Generate strategy) vs. option 2 (keep standalone). Option 1 is more architecturally coherent but requires reworking a skill that works well today. Option 2 preserves stability but creates two review pipelines with overlapping purpose. Decide after v2 is stable.
5. **Real-time UI trail**: the toolkit today outputs findings at end, not streamed. Ultrareview's live `N confirmed · M refuted` counter is a separate infra feature (requires streaming tool output through the skill layer). Is it worth building? Unclear; the user can also just wait.
6. **Retro learning from refuted findings**: today, Retro records confirmed patterns. Under v2, refuted findings also carry signal — specifically, `bare-observation`-refuted findings indicate generator prompts need a causal-chain example. Should Retro record at the generator-debt level, or stay at the claim-content level? Both are valuable; they differ in who consumes the learning (generator-prompt debt goes to the prompt author; claim-content learnings go to future reviewers).
7. **Token budget cap per review**: should the pipeline enforce a hard token ceiling (e.g., "stop Verify after 50k tokens regardless of remaining candidates")? If yes, which candidates get dropped first? If no, how does the pipeline handle a 5000-line documentation diff that generates 5000 candidates?

---

## Observations flagged as speculation vs observation

The ground-truth trace provided one concrete Ultrareview run (PR #527, 16 lines, 15 candidates, 4 confirmed, 10 refuted). Everything below is extrapolation from that single run and must be validated before production:

- **Generation ratio ≈ 1 candidate per line** — observed on this one PR. Unknown whether Ultrareview applies this ratio adaptively, or whether 1:1 is coincidental at this diff size. Large-diff behavior is unobserved.
- **Refute rate ~66%** — observed on this one PR. Healthy range is extrapolated. A 90% refute rate could mean "verifier is too strict" or "generator is working correctly by over-generating." Needs multiple observations to calibrate.
- **Verify uses independent source context** — inferred from the distinction between `bare-observation` refutations (which require reading past the cited line) and `duplicate-of` refutations (which require cross-finding comparison). The UI did not expose what context the verifier loaded; the inference is that it must have loaded the full file because a bare-observation refutation ("this observation lacks a causal chain") cannot be made without reading surrounding context.
- **Dedupe is a separate phase from Verify** — observed in the UI as a distinct pipeline stage (pending at capture time). What Dedupe actually does was not directly observed; the proposed root-cause-key mechanics are plausible design, not ground truth. Dedupe could also just be "merge findings with identical file:line+ claim hash" — simpler than the proposed scheme.
- **Verdict reason categories (A vs B)** — the two-category split is derived from post-hoc analysis of the refuted set, not from Ultrareview's own taxonomy. Ultrareview may internally use a single `refuted` verdict with free-form reason text. The categorical proposal here is an interpretation.
- **Refuted findings stay visible (line-through)** — observed in the UI. Whether they're persisted to an artifact file is not observed; the proposal to log them to `pr-review-verdicts.json` is a toolkit convention, not an Ultrareview match.
- **No direct observation of specialist composition** — Ultrareview's Generate phase may or may not use specialist agents. It may be a single monolithic generator. The proposal to use the existing `pr-review` specialists is a toolkit integration choice, not an Ultrareview pattern copy.

---

## Post-trace validation (added after final Ultrareview output landed)

After the above was drafted, Ultrareview's full output arrived as four structured findings (one of them a dedupe-merge of two candidates). That output resolves several of the speculation flags above and provides a concrete schema for the Verifier data contract. Evidence below cites specific `bug_id` values from the run against PR #527.

### Speculation flags now resolved

| Flag | Resolution | Evidence |
|---|---|---|
| Dedupe is a separate phase, mechanics unobserved | **Confirmed as a real phase that merges by root cause.** `merged_bug_001` was produced by fusing `bug_001` and `bug_005` — the finding explicitly lists `source_bug_ids: ["bug_001", "bug_005"]`. The merged finding's `reasoning` field addresses its sibling's refutation inline: *"Addressing the duplicate-framing refutation: the refutation is correct that $ARGUMENTS substitution DOES work for other user-invocable: true skills … so this is not a separate defect. It is a symptom of the same root cause."* This is root-cause dedup, not text-hash dedup. | `merged_bug_001` `source_bug_ids` field, `reasoning` |
| Verdict-reason A/B categories are post-hoc interpretation | **Partially validated.** The Verify step does distinguish "true but weak/duplicate" from "true and defect" — the dedup comment explicitly walks through sibling refutation logic. Whether Ultrareview internally labels these as A/B or uses free-form reason text is still unknown; the distinction is operational either way. | `merged_bug_001` reasoning, paragraph starting "Addressing the duplicate-framing refutation" |
| Verify uses independent source context | **Confirmed.** Every finding's `reasoning` contains step-by-step proof citing specific files, line numbers, and grep counts beyond the originating diff: `skills/README.md:5`, `skills/docs-sync-checker/SKILL.md:140`, `hooks/codex-auto-review.py:49`, etc. The verifier clearly loaded context outside the candidate's originating line. | `bug_009` cites 4 external files; `merged_bug_001` cites 7 external callers |
| Refuted findings persistence format | **Still unobserved** for the final report — the four delivered findings are all confirmed. Whether refuted items are persisted or only shown in the UI is unresolved. The proposed `pr-review-verdicts.json` log remains a toolkit convention choice. | (no evidence either way in the delivered JSON) |
| 1:1 generation ratio on small diffs | **Unchanged** — still n=1 observation. No new evidence. |

### Observations NOT in the original ADR that the output exposes

1. **Severity is a first-class field assigned post-verify, grounded in observed impact.** The delivered JSON has `"severity": "nit"` or `"normal"`. The two `nit`s (bug_004 "Agent vs Task" prose mismatch; bug_009 missing README row) are cosmetic. The two `normal`s (bug_011 INDEX not regenerated; merged_bug_001 broken slash entry) are functional breaks. The Verify phase appears to assign severity after confirming, not before — consistent with the proposed pipeline but not explicitly modeled. **ADR update required**: add `severity` to the `VerdictedFinding` contract (line ~96-130), assigned in Verify not Generate.

2. **The finding schema has a `corroborated_by` field that was null in all four outputs.** This strongly suggests Ultrareview supports multi-verifier panels but did not use one here. The ADR's Open Question #1 ("single-agent vs panel verifier") is therefore a real knob in Ultrareview's design, not a hypothetical. **ADR update required**: Open Question #1 can be closed — panel support exists upstream.

3. **Reasoning fields are book-length.** `merged_bug_001.reasoning` is ~2,500 chars with step-by-step proof, impact tables, and fix suggestions. `bug_011.reasoning` enumerates 5 numbered proof steps with shell commands. This is far beyond "short justification"; it's reproducible-proof rigor. **ADR update required**: the `VerdictedFinding.verdict_reason` field is more than a tag — it is a structured proof artifact. Update contract definition.

4. **Findings carry a `source_bug_ids: string[]` field in all cases, not just merged findings.** Non-merged findings have `source_bug_ids: ["bug_011"]` (self-pointing). This is a stable provenance trail regardless of whether dedup fired. **ADR update required**: add to `VerdictedFinding` contract; makes provenance uniform.

5. **Ultrareview honestly acknowledges its own weak arguments.** `bug_009`'s reasoning contains a full subsection titled "Addressing the refutation — it is partially correct" where it concedes an overstated claim ("Every other top-level skill under skills/ has a row" was factually wrong — 13 other skills are also unindexed) and scales back the finding's framing accordingly. The verifier is not a rubber stamp; it adversarially engages its own candidates. **ADR update required**: Verify phase mechanics should include "produce a partial-concession path when candidate is overconfident" — not just binary confirmed/refuted.

### Implications for the Verifier agent's prompt (concrete)

Based on the four delivered reasoning fields, the Verifier prompt must produce:

- Step-numbered proof referencing file:line and shell commands (`git diff b4c3e1d..HEAD --name-only`, `grep -c pr-review skills/INDEX.json`)
- Cross-reference to authoritative repo docs that establish contracts being violated (bug_009 cites docs-sync-checker's own rules; bug_011 cites skill-creator's mandatory step)
- Explicit fix path at end of each finding, distinguishing "preferred" from "alternative"
- Honest concession paragraphs when the candidate's claim is partially overstated
- `source_bug_ids` provenance whether merging occurred or not

This is a far more demanding verifier than the current draft implied. **ADR update required**: Verifier agent scope is larger; its own ADR should budget accordingly.

---

## Migration plan

1. **Prerequisite**: PR #527 lands (pr-review relocated from command to skill).
2. **Ship `review-verifier` agent** (separate ADR; covers verifier prompt, oracle integration, output contract). Cannot start this ADR's work without it.
3. **Add v2 as opt-in mode** on the existing skill: `/pr-review --ultra` (or `--v2`). Default stays on today's behavior.
4. **Shadow-run**: on every `/pr-review` invocation for 2 weeks, also run the v2 pipeline in the background and persist both outputs. Do not show v2 output to the user yet; write it to `pr-review-shadow-<pr>.json`.
5. **Compare**: at end of 2 weeks, diff confirmed-finding sets across N PRs. Questions:
   - Strictly better? (v2 finds a superset of v1's findings)
   - Strictly worse? (v2 finds a subset)
   - Complementary? (each finds things the other misses)
   - Does v2 have meaningfully different false-positive rates on the final report?
6. **If v2 is strictly better or meaningfully complementary, flip default**. Keep `--classic` flag for rollback.
7. **If v2 is complementary but not strictly better, consider running both modes and unioning results** — the token cost doubles but the review improves.
8. **If v2 is worse, keep it behind the flag and iterate on verifier prompt / generator calibration** before flipping.

---

## Not doing (yet)

- **Building the `review-verifier` agent** — needs its own ADR once this one is accepted. That ADR will cover the verifier's prompt, oracle catalog, output contract, and error handling.
- **Generalizing caller tracing to non-Go languages** — separate ADR per language. Each needs its own oracle choice and value-space analysis.
- **Real-time streaming UI for verdicts** — separate infra question. Requires changes to how skills emit incremental output through the tool layer. Value unclear vs. cost.
- **Extending Verify+Dedupe to `parallel-code-review`, `full-repo-review`, `sapcc-review`, `comprehensive-review`** — the economics differ enough that each needs its own ADR. Start with `pr-review`, prove the pattern, then extend deliberately.
- **Automated generator-prompt-debt recording in Retro** — Phase 6 gains generator-calibration recording as proposed, but automated prompt rewriting based on refute-rate is a future feature. Manual review of generator debt is sufficient for v2.
- **Token-budget hard caps on Verify** — proposed as Open Question #7. Punt to post-v2 unless shadow-run exposes cost problems.

---

## References

- Current skill: `skills/pr-review/SKILL.md`
- Contrast skills: `skills/parallel-code-review/SKILL.md`, `skills/systematic-code-review/SKILL.md`
- Pipeline registration: `skills/workflow/references/pipeline-index.json`
- Toolkit philosophy anchors: `docs/PHILOSOPHY.md` — "Everything Should Be a Pipeline", "Both Deterministic AND LLM Evaluation", "Verifier pattern"
- Observation source: live trace of Ultrareview against PR #527, captured 2026-04-22
- Blocking PR: #527 on branch `refactor/pr-review-command-to-skill`
