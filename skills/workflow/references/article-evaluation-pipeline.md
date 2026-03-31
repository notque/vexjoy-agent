---
name: article-evaluation-pipeline
description: "Wabi-sabi-aware 4-phase article evaluation for voice authenticity."
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - WebFetch
context: fork
routing:
  triggers:
    - evaluate article
    - check article voice
    - is this authentic
    - review my article
    - voice evaluation
    - article evaluation
    - check my voice
  pairs_with:
    - voice-writer
  complexity: medium
  category: content
---

# Article Evaluation Pipeline Skill

## Overview

This skill evaluates articles for voice authenticity through a deterministic 4-phase pipeline: **Fetch**, **Validate**, **Analyze**, **Report**. It combines voice pattern validation via `voice-validator.py` with wabi-sabi-aware analysis to distinguish authentic imperfections from actual violations. The evaluation produces a structured report with verdict (AUTHENTIC / NEEDS WORK / FAILED) and line-specific recommendations.

**Default behaviors (always enabled)**:
- All 4 phases execute in sequence with explicit gates between phases
- Voice profile auto-detection from source context or manual `--voice` override
- Banned pattern zero-tolerance checking alongside voice validation
- Wabi-sabi analysis distinguishing natural imperfections from AI tells
- Line number attribution for all findings
- Evaluation report saved to file artifact

**Optional behaviors (off unless triggered)**:
- Quick mode: Skip wabi-sabi analysis, report scores only (`--quick`)
- Fix suggestions: Generate revision items for NEEDS WORK/FAILED verdicts (`--suggest-fixes`)
- Force voice: Override auto-detection with explicit profile (`--voice {name}`)

**Scope boundaries**: This skill evaluates existing articles only. Do not use for writing (use voice-writer), editing (use anti-ai-editor), or creating voice profiles (use voice-calibrator).

---

## Instructions

### Phase 1: FETCH

**Goal**: Obtain article content and identify the target voice profile.

**Step 1: Identify source**
Determine whether input is a URL or local file path.

**Step 2: Fetch content**
- For URLs: Use WebFetch or curl to retrieve content, extract article body as markdown
- For local files: Read the file directly using Read tool

**Step 3: Save artifact**
Store content to `/tmp/article-evaluation-[timestamp].md` for use in subsequent phases. This persistent artifact is non-negotiable — all downstream validators reference this file.

**Step 4: Detect voice**
Identify voice profile from source context:
- Known domain/path mapping → fetch corresponding voice profile
- Unknown source → require explicit `--voice {name}` flag

Do not guess voice profiles. Wrong profile produces meaningless scores and invalidates downstream analysis.

**Gate**: Article content exists in temp file AND voice profile identified. Proceed only when gate passes.

### Phase 2: VALIDATE

**Goal**: Run deterministic validation against voice profile and banned patterns using `scripts/voice-validator.py`.

**Step 1: Voice pattern validation**

```bash
python3 $HOME/claude-code-toolkit/scripts/voice-validator.py validate \
  --content /tmp/article-evaluation.md \
  --voice [voice-name] \
  --format json
```

Pass criteria: Score >= 60, zero hard errors.

**Step 2: Banned pattern check**

```bash
python3 $HOME/claude-code-toolkit/scripts/voice-validator.py check-banned \
  --content /tmp/article-evaluation.md
```

Pass criteria: Score = 100 (no banned patterns detected).

Em-dashes are absolutely prohibited and must always be flagged as errors. This is a zero-tolerance policy.

**Step 3: Record results**
Capture both validation scores, all errors with line numbers, and all warnings. Trust the script output over subjective assessment — deterministic validation is non-negotiable.

**Gate**: Both validation runs complete with output captured and line numbers recorded. Proceed only when gate passes.

### Phase 3: ANALYZE (Wabi-Sabi)

**Goal**: Classify imperfections as authentic markers or actual violations. This phase distinguishes whether deviations from "perfect" writing are intentional stylistic features or genuine problems.

**Step 1: Scan for imperfections**
Review content for all deviations from grammatical perfection: typos, run-ons, fragments, self-corrections, trailing thoughts, casual contractions, natural rhythm breaks.

**Step 2: Classify each finding**

For each imperfection found, classify as one of:
- **WABI-SABI** (KEEP): Intentional imperfection matching the writer's authentic patterns. Natural-sounding deviations that enhance authenticity.
- **ERROR** (FIX): Actual voice violation, banned pattern, or content that contradicts the authentic voice.
- **WARNING** (REVIEW): Minor rhythm issue or pattern inconsistency worth documenting but not blocking.

Use `references/wabi-sabi-classification.md` for the full decision tree. Do not flag typos, run-ons, or fragments as errors automatically — evaluate them against the writer's authentic voice patterns first.

**Step 3: Check for suspicious perfection**
Zero wabi-sabi markers is itself a red flag. If no imperfections found, note as suspicious — authentic writing always contains natural imperfections. Over-polished content suggests synthetic generation.

**Gate**: All imperfections classified with line numbers and rationale. Document the wabi-sabi verdict (markers present / absent). Proceed only when gate passes.

### Phase 4: REPORT

**Goal**: Generate comprehensive evaluation report with verdict and recommendations.

**Step 1: Compile findings**
Aggregate validation scores, wabi-sabi markers, errors, and warnings into the structured report format defined in `references/report-template.md`. All findings must include line numbers and context.

**Step 2: Determine verdict**

| Verdict | Conditions |
|---------|------------|
| AUTHENTIC | Voice >= 60, banned = 100, wabi-sabi markers present |
| NEEDS WORK | Voice >= 60, banned < 100 (minor violations) |
| FAILED | Voice < 60, or major banned pattern violations |

A passing score is not about over-polishing (95+). Expect authentic articles to score 70-90 with visible wabi-sabi markers. Scores below 60 or banned pattern violations require remediation.

**Step 3: Write recommendations**
- For NEEDS WORK or FAILED verdicts: List specific items to fix with line numbers and rationale
- For AUTHENTIC verdicts: Document what makes it work — which wabi-sabi markers contribute to authenticity

**Step 4: Output report**
Display report to user and save to file. The report must include verdict, both scores, wabi-sabi analysis, and specific recommendations.

**Gate**: Complete report generated with verdict, scores, wabi-sabi analysis, and recommendations. Evaluation complete.

---

## Examples

### Example 1: URL Evaluation
User says: "Evaluate this article https://example.com/posts/my-article/"

Actions:
1. Fetch article content, save to temp file, detect voice from context (FETCH)
2. Run voice-validator.py validate + check-banned (VALIDATE)
3. Classify imperfections as wabi-sabi or violations (ANALYZE)
4. Generate report with verdict (REPORT)

Result: Comprehensive evaluation with AUTHENTIC/NEEDS WORK/FAILED verdict and line-specific findings

### Example 2: Local File Quick Check
User says: "Quick check on ~/myblog/content/posts/draft.md"

Actions:
1. Read local file, save to temp, detect voice from context (FETCH)
2. Run both validators (VALIDATE)
3. Skip wabi-sabi analysis (quick mode enabled) (ANALYZE skipped)
4. Generate abbreviated report with scores only (REPORT)

Result: Fast pass/fail with scores, no wabi-sabi breakdown

---

## Error Handling

### Error: "Voice validator script not found"
Cause: `scripts/voice-validator.py` not at expected path or not executable

Solution:
1. Verify path: `ls $HOME/claude-code-toolkit/scripts/voice-validator.py`
2. Check permissions: `chmod +x` if needed
3. If missing, cannot proceed — deterministic validation via the script is a non-negotiable requirement

### Error: "Cannot determine voice profile"
Cause: Source does not match any known site mapping and no `--voice` flag provided

Solution:
1. Ask user which voice to validate against
2. Use `--voice {name}` explicit flag
3. Do NOT guess or assume — wrong profile produces meaningless scores and invalidates the entire evaluation

### Error: "Article content empty or too short"
Cause: WebFetch failed, URL is paywalled/auth-walled, or file path incorrect

Solution:
1. Verify URL is accessible (check for paywalls, auth walls, redirects)
2. Try alternative fetch method (curl vs WebFetch)
3. Ask user to provide content directly if URL remains inaccessible

---

## References

- `${CLAUDE_SKILL_DIR}/references/report-template.md`: Full report format with verdict criteria and examples
- `${CLAUDE_SKILL_DIR}/references/wabi-sabi-classification.md`: Complete marker tables and classification decision tree
