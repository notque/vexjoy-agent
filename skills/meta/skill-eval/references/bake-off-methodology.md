# Bake-Off Methodology

Head-to-head grading of two implementations of the same artifact (two voice profiles, two skills, two agents, two routing tables) on a numeric rubric with cited evidence per score. Produces a decisive winner and a short fold-list of features to lift from loser to winner.

This is the methodology reference for `skill-eval` Mode F (Head-to-Head Bake-Off). The SKILL.md tells you when to load this file; this file tells you what to do once loaded.

---

## When to use this mode

Load this reference when the user says: "bake-off", "head-to-head", "grade these two", "compare implementations", "is X or Y better", "which Feynman skill is better", "compare voice-X to voice-Y", or any other request whose intent is *score two artifacts that aim at the same goal and pick a winner*.

Do **not** use this for:
- Trigger evaluation of a single skill — use Mode A.
- A/B testing variants of the same author's skill — use `agent-comparison` Phase 5 OPTIMIZE or Mode E (self-improvement loop).
- Output benchmarks of with-skill vs without-skill — use Mode C.

The bake-off is for *peer artifacts*, not for *variants of one artifact*. If A and B were built by different authors (or different teams, or your-skill vs an external repo), this is the right mode.

---

## Phase 1: PREPARE — Gather both artifacts

**Step 1: Pin both artifacts to disk with concrete paths.**

Artifact A is normally the toolkit's own implementation; artifact B is the external comparison. Read both fully before scoring — do not score from memory or partial reads.

```bash
wc -l <artifact-A>/SKILL.md <artifact-A>/references/*.md
wc -l <artifact-B>/SKILL.md <artifact-B>/references/*.md
```

Translation step: if either side is in a non-English language, translate quoted evidence inline (original + English) so the scoring matrix is auditable.

**Step 2: Choose the verifier.**

Per the verifier pattern (`docs/PHILOSOPHY.md` "Both Deterministic AND LLM Evaluation"), the agent that grades MUST NOT be the agent that built either side. If either artifact came out of this session, dispatch a fresh agent — `research-coordinator-engineer` and `agent-evaluation` are common picks. Record the verifier's identity in the report header.

**Gate**: Both artifacts read in full. Verifier identity declared. Proceed only when gate passes.

---

## Phase 2: RUBRIC — Define the scoring criteria BEFORE looking for evidence

**Step 1: Define 5–12 criteria, each scored 0–10.**

Criteria depend on the artifact type. For voice profiles, the canonical 11-criterion rubric is:

1. Triple-validation discipline
2. Source quality + count
3. Mental-model exclusivity
4. Phrase fingerprint authenticity
5. Calibration examples
6. Anti-pattern coverage
7. Joy-check axis
8. Operational utility (cold pickup)
9. Ethical / source discipline
10. Modal/register breadth
11. Operational-runtime protocol

For skills generally, swap in: phase coverage, gate clarity, deterministic-vs-LLM split, error handling depth, reference-loading discipline, anti-rationalization presence, worked examples, output-template specificity, integration with toolkit conventions.

**Step 2: Pre-state the loser-of-each-criterion before reading evidence.**

Write down a one-line guess per criterion. This is the anti-rationalization gate. After scoring, you will compare the guess to the actual finding — if every criterion's loser matches your pre-guess and the totals come out exactly the way you expected, treat the result with suspicion and re-read the losing artifact for missed evidence.

**Step 3: Define confidence tags.**

Each score carries a confidence: **high** (multiple independent evidence points, both sides clearly differentiated), **medium** (a few evidence points, some interpretation), **low** (single evidence point or judgment call). Low-confidence scores are flagged in the report so the user knows where to push back.

**Gate**: Rubric written. Pre-stated losers recorded. Confidence vocabulary set. Proceed only when gate passes.

---

## Phase 3: GRADE — Score each criterion with cited evidence

**Step 1: Score each artifact on each criterion, side-by-side.**

Every score MUST cite either:
- A path + line range: `<artifact>/SKILL.md:281-294`
- An exact quote (translated if non-English): `"That's all there is to it." (QED, Cornell)`

A score without a citation is not a score; it is opinion. Strike it and re-read.

**Step 2: Build the scoring matrix.**

```markdown
| # | Criterion | Artifact A (toolkit) | Artifact B (external) | Winner |
|---|---|---|---|---|
| 1 | Triple-validation discipline | **9** / pattern-candidates.md applies rubric per pattern with explicit KEEP/FOOTNOTE/DROP verdicts (484 lines) | **5** / claims "5 parallel agents" methodology but no per-pattern triple-check tabulation in SKILL.md or references | A |
| ... | ... | ... | ... | ... |
| **Totals** |   | **86** | **74** | A by 12 |
```

**Step 3: Apply the anti-rationalization gate.**

Now compare actual losers per criterion to your pre-stated losers from Phase 2. If they match perfectly: re-read the under-scored side for at least three criteria, looking specifically for evidence you missed. If they diverge: note the divergence in the report — that divergence is the most interesting signal, because it caught you mid-bias-correction.

**Step 4: Compute the margin.**

```
margin = winner_total - loser_total
margin_pct = margin / max_possible_total
```

Decisiveness thresholds:
- **Decisive**: margin >= 10% of max (e.g., 11+ on a 110-point rubric)
- **Marginal**: margin 5–10%
- **Tie**: margin < 5%

Report the verdict word explicitly. "Decisive" claims invite scrutiny; "marginal" invites further test cases.

**Gate**: Every criterion has cited evidence. Anti-rationalization comparison done. Margin computed and named. Proceed only when gate passes.

---

## Phase 4: FOLD — What survives philosophy filtering

**Step 1: List the loser's wins.**

Even a losing artifact usually beats the winner on 1–3 criteria. Name them with citations.

**Step 2: Filter folds against `docs/PHILOSOPHY.md`.**

For each loser-win, ask: would folding this feature into the winner violate a toolkit principle? Common rejections:

- Loser-win is "ethical caveats embedded in the skill body" — REJECT under "Skills Contain Execution Context Only" (PHILOSOPHY.md: ethical judgment happens at the moment of use, not at build time).
- Loser-win is "runtime tool-use protocol" inside a voice profile — REJECT if the toolkit's home for that is a separate orchestration skill, not the voice profile itself.
- Loser-win is "per-model limits subsections" — KEEP if it adds runtime decision criteria the model uses while generating.
- Loser-win is "more dissenter sources" in working notes — KEEP if it improves the extraction quality of the next rebuild; relevant to `references/`, not SKILL.md body.

**Step 3: Name 1–2 specific folds.**

The output is a short, concrete fold-list. Each fold names the file to change, the lines to add or replace, and the principle that justifies it. If zero folds survive philosophy filtering, say so plainly — that is also a finding.

**Gate**: Loser-wins identified. Each filtered against PHILOSOPHY.md with verdict. Survivor list produced. Proceed only when gate passes.

---

## Phase 5: REPORT — Land the artifact

**Output path**: `tmp/<topic>-bakeoff-report.md` (gitignored — `tmp/` is in `.gitignore`).

**Required sections**:

1. **Executive Verdict** — one paragraph. Winner, score, margin, decisiveness word. One sentence on each side's biggest comparative win. Optionally one sentence on the most surprising finding.
2. **Methodology** — rubric source, verifier identity, anti-rationalization gate disclosure, translation note if applicable.
3. **Scoring Matrix** — the table from Phase 3 Step 2.
4. **Per-Criterion Grading** — one short subsection per criterion with cited evidence, both sides scored, confidence tag.
5. **What Each Implementation Does Better** — two bulleted lists naming the loser-wins and winner-wins.
6. **Final Verdict + Folds** — winner, margin, fold-list (or "no folds survive philosophy filtering").

**The report is the artifact.** Downstream consumers (the user, the next session, a PR description) read it instead of replaying the bake-off. Make it self-contained.

---

## Worked example: Feynman voice-profile bake-off (2026-04-27)

**Subjects**: A — toolkit `skills/content/voice-feynman/SKILL.md` (428 lines, English) vs B — `alchaincyf/nuwa-skill` Feynman (447 lines, primarily Chinese).

**Verifier**: research-coordinator-engineer (separate from the toolkit-feynman builder).

**Rubric**: 11 criteria, each 0–10, max 110.

**Result matrix**:

| # | Criterion | A (toolkit) | B (external) | Winner |
|---|---|---|---|---|
| 1 | Triple-validation discipline | 9 | 5 | A |
| 2 | Source quality + count | 8 | 9 | B |
| 3 | Mental-model exclusivity | 8 | 6 | A |
| 4 | Phrase fingerprint authenticity | 9 | 5 | A |
| 5 | Calibration examples | 9 | 6 | A |
| 6 | Anti-pattern coverage | 9 | 5 | A |
| 7 | Joy-check axis | 8 | 8 | tie |
| 8 | Operational utility (cold pickup) | 9 | 7 | A |
| 9 | Ethical / source discipline | 5 | 9 | B |
| 10 | Modal/register breadth | 9 | 5 | A |
| 11 | Operational-runtime protocol | 3 | 9 | B |
| **Totals** | | **86** | **74** | A by 12 |

**Margin**: 12 / 110 = 10.9% → **Decisive**.

**Folds considered**:

- Fold "ethical-boundaries subsection" (criterion 9 loser-win) → **REJECTED** under "Skills Contain Execution Context Only". Ethical judgment lives at the moment-of-use, not in the skill body. The salience-by-negation argument applies: telling the generator "do not claim X about Feynman's personal life" biases generation toward those exact topics.
- Fold "per-model limits subsections" (loser-win) → **CANDIDATE**. Adds runtime decision criteria. Worth a separate eval before accepting.
- Fold "runtime fact-research protocol" (criterion 11 loser-win) → **REJECTED** for voice-feynman specifically. Belongs in a separate orchestration skill if it belongs anywhere; the voice profile is for content generation, not runtime fact-finding.

**Net survivors after philosophy filter**: 1 candidate, 0 immediate folds. Reported as such.

The full worked report lives at `tmp/feynman-bakeoff-report.md` while it remains relevant; reproduce it with the methodology above against any voice-skill peer.

---

## Failure modes

**The verdict matches your pre-stated guess perfectly across every criterion.** You scored what you expected to score. Re-read the underdog with fresh eyes for at least three criteria; look specifically for evidence that contradicts your prior. If the totals don't move, note the convergence in the report and lower confidence by one tag.

**One side has no readable artifact** (e.g., obfuscated, undocumented, behind an API). Bake-off cannot proceed; downgrade to a feature-list comparison and say so. Do not invent evidence.

**Both sides tie within 5%.** The rubric is not discriminating. Either add criteria that target the actual differentiators, or report the tie honestly — a tie is a finding, not a failure.

**A criterion has no evidence on either side.** Drop it from the rubric and recompute totals. Document the drop. A criterion neither side addresses is not measuring anything about *these two* artifacts.
