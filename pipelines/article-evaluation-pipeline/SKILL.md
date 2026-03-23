---
name: article-evaluation-pipeline
description: |
  Wabi-sabi-aware 4-phase article evaluation: Fetch, Validate, Analyze,
  Report. Use when user wants to evaluate an article for voice authenticity,
  check voice quality, review article voice patterns, or validate content
  against a voice profile. Use for "evaluate article", "check voice",
  "is this authentic", "review my article", or "voice evaluation". Do NOT
  use for writing articles, editing content, or generating voice profiles
  without an existing article to evaluate.
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
    - voice-orchestrator
  complexity: medium
  category: content-validation
---

# Article Evaluation Pipeline Skill

## Operator Context

This skill operates as an operator for voice authenticity evaluation, configuring Claude's behavior for deterministic validation combined with wabi-sabi-aware analysis. It implements the **Pipeline** architectural pattern -- Fetch, Validate, Analyze, Report -- with **Domain Intelligence** embedded in voice authenticity classification.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before evaluation
- **Over-Engineering Prevention**: Evaluate the article as-is. No speculative corrections, no "while I'm here" rewrites
- **Deterministic Validation Required**: Always use `scripts/voice_validator.py` for pattern matching. Never self-assess voice quality
- **Wabi-Sabi Awareness**: Natural imperfections are FEATURES, not bugs. See `skills/shared-patterns/wabi-sabi-authenticity.md`
- **Em-Dash Zero Tolerance**: Em-dashes are an absolute prohibition, always flagged as errors
- **No False Positives on Authenticity**: Do NOT flag typos, run-ons, fragments, self-corrections, or trailing thoughts as errors
- **Artifact Persistence**: Save evaluation report to file, not just context

### Default Behaviors (ON unless disabled)
- **Full Pipeline Execution**: Run all 4 phases: FETCH -> VALIDATE -> ANALYZE -> REPORT
- **Voice Auto-Detection**: Detect voice based on source context or explicit `--voice` flag
- **Wabi-Sabi Report Section**: Include dedicated analysis of intentional imperfections
- **Banned Pattern Check**: Run zero-tolerance check for AI tells alongside voice validation
- **Line Number Attribution**: Report all findings with specific line numbers
- **Artifact Saving**: Save fetched content to `/tmp/article-evaluation-[timestamp].md`

### Optional Behaviors (OFF unless enabled)
- **Quick Mode**: Skip wabi-sabi analysis, only run validators (`--quick`)
- **Fix Suggestions**: Generate revision suggestions for failing content (`--suggest-fixes`)
- **Specific Voice Override**: Force voice profile instead of auto-detect (`--voice {name}`)

## What This Skill CAN Do
- Evaluate articles for voice authenticity through deterministic validation
- Classify imperfections as wabi-sabi markers (keep) vs actual violations (fix)
- Run banned pattern checks with zero tolerance for AI tells
- Generate comprehensive evaluation reports with line-level attribution
- Auto-detect which voice profile to validate against

## What This Skill CANNOT Do
- Write or generate articles (use voice-orchestrator or research-to-article instead)
- Edit or fix articles (use anti-ai-editor instead)
- Create voice profiles (use voice-calibrator instead)
- Skip the validation phase and self-assess quality
- Run without `scripts/voice_validator.py` available

---

## Instructions

### Phase 1: FETCH

**Goal**: Obtain article content in a format suitable for validation.

**Step 1: Identify source**

Determine whether input is a URL or local file path.

**Step 2: Fetch content**

For URLs: Use WebFetch or curl to retrieve content, extract article body as markdown.
For local files: Read the file directly.

**Step 3: Save artifact**

Save content to `/tmp/article-evaluation-[timestamp].md` for subsequent phases.

**Step 4: Detect voice**

Detect voice profile from source or context:
- Known domain/path -> mapped voice profile
- Unknown -> require explicit `--voice` flag

**Gate**: Article content saved to temp file AND voice profile identified. Proceed only when gate passes.

### Phase 2: VALIDATE

**Goal**: Run deterministic validation against voice profile and banned patterns.

**Step 1: Voice pattern validation**

```bash
python3 $HOME/claude-code-toolkit/scripts/voice_validator.py validate \
  --content /tmp/article-evaluation.md \
  --voice [voice-name] \
  --format json
```

Pass criteria: Score >= 60, zero hard errors.

**Step 2: Banned pattern check**

```bash
python3 $HOME/claude-code-toolkit/scripts/voice_validator.py check-banned \
  --content /tmp/article-evaluation.md
```

Pass criteria: Score = 100 (no banned patterns found).

**Step 3: Record results**

Capture both scores, all errors, and all warnings with line numbers.

**Gate**: Both validation runs complete with captured output. Proceed only when gate passes.

### Phase 3: ANALYZE (Wabi-Sabi)

**Goal**: Classify imperfections as authentic markers or actual violations.

**Step 1: Scan for imperfections**

Review content for all deviations from "perfect" writing: typos, run-ons, fragments, self-corrections, trailing thoughts, casual contractions.

**Step 2: Classify each finding**

For each imperfection found, classify as:
- **WABI-SABI** (KEEP): Intentional imperfection matching the writer's authentic patterns
- **ERROR** (FIX): Actual voice violation or banned pattern
- **WARNING** (REVIEW): Minor rhythm or pattern issue worth noting

Use `references/wabi-sabi-classification.md` for the full classification guide and decision tree.

**Step 3: Check for suspicious perfection**

Zero wabi-sabi markers is itself a red flag. If no markers found, note this as suspicious -- authentic writing always contains imperfections.

**Gate**: All imperfections classified with line numbers and rationale. Proceed only when gate passes.

### Phase 4: REPORT

**Goal**: Generate comprehensive evaluation report.

**Step 1: Compile findings**

Aggregate validation scores, wabi-sabi markers, errors, and warnings into the report structure defined in `references/report-template.md`.

**Step 2: Determine verdict**

| Verdict | Conditions |
|---------|------------|
| AUTHENTIC | Voice >= 60, banned = 100, wabi-sabi markers present |
| NEEDS WORK | Voice >= 60, banned < 100 (minor violations) |
| FAILED | Voice < 60, or major banned pattern violations |

**Step 3: Write recommendations**

For NEEDS WORK or FAILED verdicts, list specific items to fix with line numbers. For AUTHENTIC, note what makes it work.

**Step 4: Output report**

Display report to user and save to file if requested.

**Gate**: Complete report generated with verdict, scores, and recommendations. Evaluation complete.

---

## Examples

### Example 1: URL Evaluation
User says: "Evaluate this article https://example.com/posts/my-article/"
Actions:
1. Fetch article content, save to temp file, detect voice from context (FETCH)
2. Run voice_validator.py validate + check-banned (VALIDATE)
3. Classify imperfections as wabi-sabi or violations (ANALYZE)
4. Generate report with verdict (REPORT)
Result: Comprehensive evaluation with AUTHENTIC/NEEDS WORK/FAILED verdict

### Example 2: Local File Quick Check
User says: "Quick check on ~/myblog/content/posts/draft.md"
Actions:
1. Read local file, save to temp, detect voice from context (FETCH)
2. Run both validators (VALIDATE)
3. Skip wabi-sabi analysis (quick mode) (ANALYZE skipped)
4. Generate abbreviated report with scores only (REPORT)
Result: Fast pass/fail with scores, no wabi-sabi breakdown

---

## Error Handling

### Error: "Voice validator script not found"
Cause: `scripts/voice_validator.py` not at expected path or not executable
Solution:
1. Verify path: `ls $HOME/claude-code-toolkit/scripts/voice_validator.py`
2. Check permissions: `chmod +x` if needed
3. If missing, cannot proceed -- deterministic validation is non-negotiable

### Error: "Cannot determine voice profile"
Cause: Source does not match any known site mapping and no `--voice` flag provided
Solution:
1. Ask user which voice to validate against
2. Use `--voice {name}` explicit flag
3. Do NOT guess -- wrong profile produces meaningless scores

### Error: "Article content empty or too short"
Cause: WebFetch failed, URL is paywalled, or file path incorrect
Solution:
1. Verify URL is accessible (check for paywalls, auth walls)
2. Try alternative fetch method (curl vs WebFetch)
3. Ask user to provide content directly if URL inaccessible

---

## Anti-Patterns

### Anti-Pattern 1: Flagging Wabi-Sabi as Errors
**What it looks like**: Reporting typos, run-ons, and fragments as issues to fix
**Why wrong**: These are authenticity markers. Fixing them makes content more synthetic.
**Do instead**: Classify using the wabi-sabi decision tree. Only flag items on the banned list.

### Anti-Pattern 2: Expecting Perfect Scores
**What it looks like**: Treating 70/100 as a failing score, aiming for 95+
**Why wrong**: Over-polished content is an AI tell. A score of 70-90 with wabi-sabi markers is more authentic than 95+ with none.
**Do instead**: Pass threshold is 60. Expect authentic articles in the 70-90 range.

### Anti-Pattern 3: Self-Assessing Voice Quality
**What it looks like**: "This sounds like the target voice to me" without running the validator
**Why wrong**: LLM assessment is inconsistent and biased. Deterministic scripts are reproducible.
**Do instead**: Always run `voice_validator.py`. Trust the script over your judgment.

### Anti-Pattern 4: Skipping Wabi-Sabi Analysis
**What it looks like**: Running validators only and reporting scores without imperfection analysis
**Why wrong**: Misses the key insight -- whether imperfections are features or bugs. Two articles with 75/100 can be very different.
**Do instead**: Complete Phase 3 unless explicitly in quick mode.

### Anti-Pattern 5: Fixing Articles During Evaluation
**What it looks like**: "Let me also fix these issues I found" during evaluation
**Why wrong**: Evaluation and editing are separate workflows. Mixing them loses objectivity.
**Do instead**: Report findings only. If fixes needed, redirect to anti-ai-editor skill.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
- [Wabi-Sabi Authenticity](../shared-patterns/wabi-sabi-authenticity.md) - Imperfection classification principles
- [Pipeline Architecture](../shared-patterns/pipeline-architecture.md) - Pipeline design patterns

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "I can tell it's authentic without the validator" | Subjective assessment is unreliable | Run voice_validator.py, trust the script |
| "The typos are errors, I should flag them" | Typos in natural positions are wabi-sabi markers | Classify with the decision tree first |
| "Score is close to 60, probably fine" | Probably is not proven | Report exact score, let threshold decide |
| "No need for wabi-sabi analysis, scores tell the story" | Scores miss the authenticity texture | Complete Phase 3 unless quick mode |
| "I'll fix the issues while evaluating" | Evaluation and editing are separate concerns | Report only, redirect to anti-ai-editor |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/report-template.md`: Full report format with verdict criteria and examples
- `${CLAUDE_SKILL_DIR}/references/wabi-sabi-classification.md`: Complete marker tables and classification decision tree
