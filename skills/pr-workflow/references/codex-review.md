# Codex Review Intent

Invoke OpenAI's Codex CLI (GPT-5.4 with maximum reasoning effort) to get an independent second opinion on code changes.

## Reference Loading

Load these files when the corresponding signals appear:

| Signal | Load |
|--------|------|
| Constructing or debugging `codex exec` command; flag errors; mktemp issues; model errors | `${CLAUDE_SKILL_DIR}/references/codex-review-cli-patterns.md` |
| Classifying findings; adjusting severity; filtering Codex output; writing the report | `${CLAUDE_SKILL_DIR}/references/codex-review-methodology.md` |
| Looking up specific anti-patterns to verify; needs detection grep commands for Go/TS/Python | `${CLAUDE_SKILL_DIR}/references/codex-review-anti-patterns.md` |
| Executing Phase 2-4 (invoke, assess, report); error handling; what NOT to do | `${CLAUDE_SKILL_DIR}/references/codex-review-invocation.md` |

Claude orchestrates the review: scoping what to review, constructing the prompt, invoking Codex in a read-only sandbox, then critically assessing the feedback before presenting it to the user.

The value is cross-model perspective. Codex has access to the git repo and filesystem directly, so it can read diffs, browse files, and understand context without Claude having to embed everything in the prompt.

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

If the user mentioned specific concerns (performance, security, error handling), note them for the prompt. If not, let Codex do a general review.

**Step 3: Gather context summary.**

Build a brief context block for Codex that includes:
- What the project is (language, framework, purpose) in 1-2 sentences to 1-2 sentences
- What the changes are trying to accomplish, in 1-2 sentences
- Any specific focus areas the user mentioned

This context block goes into the Codex prompt. Keep it short because Codex can read the actual code itself. The context just orients it.

**Gate**: You know what to review and have a context summary. Proceed to Phase 2.

---

### Phase 2-4: Invoke, Assess, Report

Load `${CLAUDE_SKILL_DIR}/references/codex-review-invocation.md` for detailed steps:
- Phase 2: construct prompt, run `codex exec` with correct flags, check exit code
- Phase 3: read output, assess each finding, classify agree/modify/disagree
- Phase 4: produce unified report and clean up temp file

The reference also covers "What NOT to Do" pitfalls and the error-handling catalog (missing command, non-zero exit, empty output, malformed output).
