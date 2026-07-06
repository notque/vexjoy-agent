# Executor-Ready Plan Template

Plans consumed by subagent executors (via `subagent-driven-development`) must be self-contained. An executor runs in a fresh context with no memory of the planning session. Everything the executor needs — code excerpts, file paths, verification commands, stop conditions — must be inline in the plan. "See file X" is not a plan step; it is a token-burning detour.

"Executor" here is SDD's implementer subagent; the two terms name the same role.

When loaded alongside `plan-files.md`: for SDD-executed plans this skeleton replaces the plan-files skeleton. Keep plan-files' Status line for resumability; the other plan-files sections (Phases, Key Questions) are covered by Steps and STOP Conditions here.

---

## Plan Structure

Every executor-ready plan follows this skeleton. Sections marked **(required)** cause executor failure when absent.

````markdown
# Plan: [Title]

## Metadata (required)
- **Created**: YYYY-MM-DD
- **Base SHA**: [output of `git rev-parse --short HEAD` at plan creation time]
- **Branch**: [branch name]
- **Author**: [who created the plan]

## Goal (required)
[One sentence: the end state this plan produces.]

## Scope (required)

### In-scope files
[Exhaustive list of files this plan creates or modifies. One per line.]
- `path/to/file-a.go`
- `path/to/file-b.go`

### Out-of-scope files
[Files the executor must leave untouched. Touching these triggers a STOP.]
- `path/to/unrelated.go`
- `config/production.yaml`

## Steps (required)

### Step 1: [Title]

**What**: [Concrete description of the change.]

**Context** (inlined):
```[language]
// Current state of the code being changed.
// Paste the relevant excerpt here — 10-30 lines, enough to act on.
// The executor reads this, not the file.
```

**Do**:
1. [Specific instruction]
2. [Specific instruction]

**Verify**:
```bash
[command that confirms this step succeeded]
```
**Expected output**: [exact string, pattern, or exit code]

---

### Step N: [Title]
[Same structure as Step 1]

## STOP Conditions (required)

Executor must STOP and escalate (report status, request human decision) when
any of these triggers fire:

1. **Drift detected**: the Base SHA in Metadata is no longer an ancestor of
   HEAD (`git merge-base --is-ancestor <base-sha> HEAD` fails), or a step's
   Context excerpt no longer matches the current file content. Commits made by
   the plan's own earlier steps move HEAD forward and are NOT drift; a rebase,
   reset, branch switch, or edited excerpt means the plan's assumptions may be
   stale.
2. **Verification fails twice**: A step's verify command fails, the executor
   retries once, and it fails again. Two failures signal a plan defect, not a
   transient error.
3. **Out-of-scope touch required**: Completing a step requires modifying a file
   listed in "Out-of-scope files." The plan's boundary was drawn wrong; a human
   must decide whether to expand scope.
4. **Ambiguous or missing instruction**: A step's "Do" section is unclear
   enough that two reasonable interpretations exist, or a section marked
   (required) is absent from the plan. Guessing risks rework.
5. **Test regression**: A previously passing test fails after a step. The change
   broke something outside the step's intent.

## Completion Criteria (required)
[How to verify the entire plan succeeded — final command + expected output.]
````

---

## Drift Check Protocol

The Base SHA is the plan's anchor to a specific codebase state. Every code excerpt, file path, and verification command assumes that state.

**Plan author** stamps the SHA at plan creation:
```bash
git rev-parse --short HEAD
```

**Executor** verifies before starting each dispatch:
```bash
if ! git merge-base --is-ancestor <base-sha> HEAD; then
  echo "DRIFT DETECTED: base <base-sha> is not an ancestor of HEAD"
  echo "STOP: plan assumptions may be stale"
  exit 1
fi
```

The check is an ancestry test, not an equality test, because SDD runs plans as a per-task loop: each task commits and moves HEAD forward, so only the first dispatch can expect HEAD to equal the Base SHA. Commits produced by the plan's own earlier steps keep the Base SHA an ancestor and are not drift. Before editing a file, the executor also confirms the step's inlined Context excerpt still matches the file; a mismatch is drift even when ancestry holds.

If either check fails: STOP. Report the mismatch. The planner must update the plan against the current state or confirm the plan still applies.

---

## Per-Step Verification Rules

Every step ends with a verify block. The verify block is a contract: if the command produces the expected output, the step succeeded. If not, the step failed.

**Good verification** (deterministic, specific):
````markdown
**Verify**:
```bash
go test ./auth/... -run TestTokenRefresh -count=1
```
**Expected output**: `ok  auth  0.XXXs` (exit code 0)
````

**Bad verification** (vague, untestable):
```markdown
**Verify**: "Check that the code looks correct"
```

Rules:
1. Every verify command must be runnable without human judgment.
2. Expected output must be specific enough to distinguish pass from fail.
3. Prefer exit codes and grep-able strings over visual inspection.
4. When no command can verify the step (pure refactor with no behavioral change), use: `git diff --stat` + expected file list.

---

## Inlining Context

Executor subagents run in fresh context. File references ("see `auth/token.go` lines 45-60") cost the executor a Read tool call, token budget, and risk reading stale content if another step modified the file.

**Inline instead**:
- Paste 10-30 lines of the relevant code excerpt directly in the step's Context block.
- Include enough surrounding context (function signature, imports) for the executor to orient.
- Mark the excerpt's source: `// from auth/token.go:45-60 at base SHA abc1234`.

**When NOT to inline**:
- File is > 100 lines and the entire file is relevant: reference the file path but note "read this file in full before starting this step."
- File will be created from scratch: provide the full intended content in the "Do" section instead.

---

## Scope Boundaries

Explicit scope prevents executor drift — the most common failure mode in multi-step plans.

**In-scope files**: Every file the plan touches. The executor treats this as a whitelist. Creating or modifying a file absent from this list is a scope violation.

**Out-of-scope files**: Files related to the work but intentionally excluded. Naming them prevents the executor from "helpfully" fixing adjacent issues.

**Why both lists**: In-scope alone leaves a gray area — is an unlisted file fair game or forbidden? The out-of-scope list removes ambiguity. Together they form a complete boundary.

---

## Integration with Subagent-Driven Development

SDD's executor loop (Phase 2) consumes plans in this format. The plan's Base SHA (stamped at plan creation, anchors drift detection) is distinct from SDD's `{BASE_SHA}` (captured at execution start, anchors the final integration-review diff); do not conflate them. The contract:

1. **Drift check**: Executor runs the ancestry drift check from Metadata before touching any file, and confirms each step's Context excerpt before editing. Failure triggers STOP condition 1.
2. **Step-by-step execution**: Executor follows steps in order, running each verify block before proceeding. Failure triggers STOP condition 2.
3. **Scope enforcement**: Executor checks every file it modifies against the in-scope list. Out-of-scope touch triggers STOP condition 3.
4. **Escalation path**: On any STOP, the executor reports what it completed, what triggered the stop, and what decision it needs. It waits for human direction rather than improvising.

The planner's job is to make the executor's job mechanical. If the executor needs judgment, the plan is underspecified.
