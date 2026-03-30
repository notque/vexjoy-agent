---
name: codex-code-review
description: |
  Get a second-opinion code review from OpenAI Codex CLI (GPT-5.4 xhigh reasoning).
  Invokes codex exec in read-only sandbox mode, structures feedback as CRITICAL /
  IMPROVEMENTS / POSITIVE / SUMMARY, and requires Claude to assess before presenting.
  Use when user says "codex review", "second opinion", "code review codex",
  "GPT review", "get another perspective on this code", or "cross-model review".
  Do NOT use for writing code, implementing features, or reviews that don't
  involve the Codex CLI.
version: 1.0.0
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
  - Edit
  - Write
  - AskUserQuestion
routing:
  triggers:
    - "codex review"
    - "second opinion"
    - "code review codex"
    - "gpt review"
    - "cross-model review"
  pairs_with:
    - systematic-code-review
    - parallel-code-review
    - go-code-review
  complexity: Medium
  category: code-review
---

# Codex Code Review

Invoke OpenAI's Codex CLI (GPT-5.4 with maximum reasoning effort) to get an
independent second opinion on code changes. Claude orchestrates the review:
scoping what to review, constructing the prompt, invoking Codex in a read-only
sandbox, then critically assessing the feedback before presenting it to the user.

The value is cross-model perspective. Codex has access to the git repo and
filesystem directly, so it can read diffs, browse files, and understand context
without Claude having to embed everything in the prompt.

---

## Instructions

### Phase 1: Scope the Review

**Goal**: Determine exactly what Codex should review before constructing the prompt.

**Step 1: Ask the user what to review** (if not already clear from context).

Common scoping patterns:

| User says | Scope |
|-----------|-------|
| "review my changes" | `git diff` (unstaged) or `git diff --staged` |
| "review the last commit" | `git diff HEAD~1` |
| "review this PR" / "review this branch" | `git diff main...HEAD` (or appropriate base branch) |
| "review [file or directory]" | Specific paths |
| "review everything" | Full `git diff main...HEAD` |

**Step 2: Identify focus areas** (optional).

If the user mentioned specific concerns (performance, security, error handling),
note them for the prompt. If not, let Codex do a general review.

**Step 3: Gather context summary.**

Build a brief context block for Codex that includes:
- What the project is (language, framework, purpose) -- keep to 1-2 sentences
- What the changes are trying to accomplish -- keep to 1-2 sentences
- Any specific focus areas the user mentioned

This context block goes into the Codex prompt. Keep it short because Codex can
read the actual code itself -- the context just orients it.

Gate: You know what to review and have a context summary. Proceed to Phase 2.

---

### Phase 2: Invoke Codex

**Goal**: Run `codex exec` with the right flags and a well-constructed prompt.

**Step 1: Create temp file for output.**

```bash
TMPFILE=$(mktemp /tmp/codex-review.XXXXXXXX)
```

Use exactly this pattern (no extension after the X's). macOS `mktemp` breaks
when you append an extension like `.md` after the template characters.

**Step 2: Construct the prompt.**

The prompt to Codex should have four parts:

1. **Context** -- the brief summary from Phase 1
2. **What to review** -- tell Codex which git command to run or which files to
   read. Let Codex access the filesystem directly rather than embedding diffs in
   the prompt, because Codex runs in its own sandbox with repo access and
   embedding large diffs wastes tokens and loses formatting.
3. **Focus areas** -- any specific concerns (or "general review" if none)
4. **Output format** -- request the structured format below

Tell Codex to structure its output as:

```
## CRITICAL ISSUES
[Issues that would cause bugs, security vulnerabilities, data loss, or crashes.
Empty section if none found.]

## IMPROVEMENTS
[Suggestions for better code quality, performance, readability, or maintainability.
Not blocking but worth considering.]

## POSITIVE NOTES
[What's done well -- good patterns, clean abstractions, solid test coverage.
Reinforcing good practices matters.]

## SUMMARY
[2-3 sentence overall assessment: is this change ready, what's the biggest risk,
what's the biggest strength.]
```

**Step 3: Run codex exec.**

**Preferred: Use `codex exec review`** (purpose-built review subcommand):

```bash
codex exec review \
  --base main \
  -m gpt-5.4 \
  -c 'model_reasoning_effort="xhigh"' \
  --ephemeral \
  --dangerously-bypass-approvals-and-sandbox \
  -o "$TMPFILE"
```

The `review` subcommand handles diff computation internally. Use `--base` for
branch reviews, `--commit <SHA>` for single commits, or `--uncommitted` for
unstaged changes. Note: `--base`/`--commit` and a custom `[PROMPT]` argument
are mutually exclusive -- you cannot pass both.

**Fallback: Use `codex exec` with a custom prompt** when you need focus areas
or custom instructions:

```bash
codex exec \
  -m gpt-5.4 \
  -c 'model_reasoning_effort="xhigh"' \
  --ephemeral \
  --dangerously-bypass-approvals-and-sandbox \
  -o "$TMPFILE" \
  "YOUR_CONSTRUCTED_PROMPT_HERE"
```

For multi-line prompts, use a heredoc:

```bash
codex exec \
  -m gpt-5.4 \
  -c 'model_reasoning_effort="xhigh"' \
  --ephemeral \
  --dangerously-bypass-approvals-and-sandbox \
  -o "$TMPFILE" \
  "$(cat <<'PROMPT'
[Your constructed prompt here]
PROMPT
)"
```

Flag explanation:
- `-m gpt-5.4` -- use GPT-5.4 for maximum review quality
- `-c 'model_reasoning_effort="xhigh"'` -- maximize reasoning depth so Codex
  doesn't shortcut analysis of complex code paths
- `--ephemeral` -- don't persist the Codex session (this is a one-shot review)
- `--dangerously-bypass-approvals-and-sandbox` -- bypass the bwrap sandbox
  which fails in containerized/VM environments with "loopback: Failed
  RTM_NEWADDR: Operation not permitted". This is safe because Claude Code
  already provides external sandboxing and the review is read-only by nature.
  The `-s read-only` flag is incompatible with this bypass (use one or the
  other, not both)
- `-o "$TMPFILE"` -- capture Codex's output to the temp file for processing

**Step 4: Check exit code.**

If `codex exec` exits non-zero, report the error to the user and stop. Do not
retry automatically because Codex failures are typically due to API issues,
authentication problems, or prompt-length limits that won't resolve on retry.

Read the stderr output and include it in your error report so the user can
diagnose (e.g., rate limiting, invalid API key, model unavailable).

Gate: Codex exited 0 and `$TMPFILE` contains review output. Proceed to Phase 3.

---

### Phase 3: Assess and Filter

**Goal**: Critically evaluate Codex's feedback before presenting it. Claude is
the reviewer of the reviewer -- Codex provides signal, not authority.

**Step 1: Read the output.**

```bash
cat "$TMPFILE"
```

**Step 2: Assess each finding.**

For every issue Codex raised, evaluate:

| Question | Action |
|----------|--------|
| Is this actually correct? | Read the relevant code yourself. Codex may have misread the logic, missed context from other files, or misunderstood the intent. |
| Is this already handled elsewhere? | Check if the concern is addressed in code Codex didn't examine (e.g., middleware, error handling upstream). |
| Does this apply to this project's conventions? | Check the project's CLAUDE.md or style guides. What's an anti-pattern generally may be the accepted convention here. |
| Is the severity right? | Codex may flag a style preference as critical, or miss that a "minor" issue is actually a data-loss risk in this context. |

**Step 3: Classify each finding.**

After assessment, classify each Codex finding into one of:

- **Agree** -- finding is correct and properly scoped. Include it in the report.
- **Agree with modification** -- finding is directionally right but needs nuance
  (different severity, narrower scope, additional context). Include the modified
  version.
- **Disagree** -- finding is incorrect, not applicable, or already handled.
  Mention it briefly with your reasoning so the user understands why it was
  filtered, because silently dropping findings erodes trust.

**Step 4: Add Claude's own observations.**

If you noticed issues that Codex missed, add them. The cross-model approach works
both ways -- each model catches things the other doesn't.

Gate: Every Codex finding has been assessed. Proceed to Phase 4.

---

### Phase 4: Report

**Goal**: Present the unified review to the user.

Structure the report as:

```markdown
## Codex Code Review (GPT-5.4 xhigh)

**Scope**: [what was reviewed -- e.g., "git diff main...HEAD (12 files)"]

### Critical Issues
[Agreed findings at critical severity, with Claude's assessment]

### Improvements
[Agreed suggestions, modified suggestions with Claude's notes]

### Positive Notes
[What both models agree is well-done]

### Filtered Findings
[Findings Claude disagreed with, plus reasoning -- keep brief]

### Claude's Additional Observations
[Issues Claude found that Codex missed, if any]

### Summary
[Combined assessment from both models]
```

**Clean up** the temp file:

```bash
rm -f "$TMPFILE"
```

---

## What NOT to Do

### Do not treat Codex output as authoritative

Codex is a second opinion, not a senior reviewer with merge authority. Its
findings need the same scrutiny you'd apply to any automated tool output. It can
hallucinate issues, misread control flow, or flag patterns that are intentional
in this codebase.

### Do not loop or retry on failure

If Codex fails (non-zero exit, empty output, garbled response), report it to the
user and let them decide. Automatic retry loops burn API quota and rarely fix the
underlying problem (auth issues, rate limits, model errors).

### Do not embed large diffs in the prompt

Codex has filesystem access in its sandbox. Tell it which git command to run
(e.g., "run `git diff main...HEAD` to see the changes") rather than pasting the
diff into the prompt. Embedded diffs waste tokens, lose formatting, and hit
prompt length limits on large changes.

### Do not skip the assessment phase

The entire value of this skill is cross-model triangulation. If Claude just
passes through Codex output verbatim, the user could have run `codex exec`
themselves. The assessment phase is where Claude adds context, catches errors,
and filters noise.

### Do not apply fixes without user confirmation

Even if a finding is clearly correct and the fix is obvious, present it to the
user and let them decide. The user invoked this skill for a review, not for
autonomous code changes.

---

## Error Handling

**Error: `codex: command not found`**
- Cause: Codex CLI is not installed or not in PATH
- Solution: Tell the user to install it: `npm install -g @openai/codex`
  (or check their installation docs). Verify with `codex --version`.

**Error: Non-zero exit code from `codex exec`**
- Cause: API authentication failure, rate limiting, model unavailable, or
  prompt too long
- Solution: Read stderr, report the specific error to the user. Do not retry.

**Error: Empty output file**
- Cause: Codex ran but produced no output (possible timeout or model error)
- Solution: Report to user. Check if `$TMPFILE` exists but is empty vs.
  doesn't exist. Include any stderr output.

**Error: Output is not in expected format**
- Cause: Codex didn't follow the structured output format requested
- Solution: Still process the output -- extract what findings you can and
  assess them. Note in the report that Codex output was unstructured.
