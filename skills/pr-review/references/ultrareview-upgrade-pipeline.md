# Ultrareview Upgrade: Pipeline Spec

> Companion detail for `ultrareview-upgrade-proposal.md`. Split out of the main proposal to respect the 500-line per-reference progressive-disclosure budget. Read the main proposal first for context, decision, and review-ask framing; read this file when you need the concrete phase mechanics.

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

