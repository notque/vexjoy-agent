---
name: debugging
description: "Debugging: guided diagnosis of application bugs, and post-mortem of failed agent sessions."
user-invocable: false
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
routing:
  not_for: "code review (use review), building features (use workflow)"
  triggers:
    - "guide debugging"
    - "question-based"
    - "teach debugging"
    - "ask me questions"
    - "help me think through"
    - "guide me"
    - "coaching mode"
    - "teach me to find it"
    - forensics
    - "what went wrong"
    - "why did this fail"
    - "stuck loop"
    - "diagnose workflow"
    - post-mortem
    - "workflow failure"
    - "session crashed"
    - "why is this stuck"
    - "investigate failure"
    - "why did this break"
    - "incident review"
  category: process
  pairs_with:
    - workflow
    - review
---

# Debugging Skill

Two modes. Pick one based on the request:

| Signal | Mode |
|---|---|
| Guide me, teach debugging, ask me questions, coaching | **Socratic** |
| What went wrong, post-mortem, stuck loop, session crashed | **Forensics** |

---

## Mode 1: Socratic Debugging

Guide the user to discover root causes through structured inquiry. Never give
the answer -- the user must arrive at it. Read relevant code with Read/Grep/Glob
before formulating questions; code knowledge makes questions precise.

### Question Progression

Follow these 9 phases in order. Each builds evidence for the next.

| Phase | Purpose | Example |
|-------|---------|---------|
| 1. Symptoms | Gap between expected and actual | "What did you expect?" / "What happened instead?" |
| 2. Reproducibility | Deterministic or intermittent | "Can you reproduce this consistently?" |
| 3. Prior Attempts | Avoid retreading | "What have you already tried?" |
| 4. Minimal Case | Reduce search space | "What is the smallest failing input?" |
| 5. Error Analysis | Extract signal from output | "Which part of the error message is most informative?" |
| 6. State Inspection | Ground in actual data | "What is the value of X right before the error?" |
| 7. Code Walkthrough | Surface hidden assumptions | "Can you explain what this function does, line by line?" |
| 8. Assumption Audit | Challenge mental model | "What are you assuming that you haven't verified?" |
| 9. Hypothesis | Build investigative instinct | "Where do you think the problem is? Why there?" |

### Execution

1. User describes the bug. Read relevant code silently.
2. Ask one Phase 1 question. No preamble, no diagnosis, no code references.
3. Listen. Acknowledge briefly. Ask the next question toward root cause.
4. After 12 questions without progress, offer escalation (see below).
5. When user identifies root cause, confirm and ask what fix they would apply.

**One question at a time.** Mirror user terminology. Acknowledge discoveries
before the next question. Open-ended questions that narrow focus are good hints;
leading questions that contain the answer are violations.

### Escalation

After 12 questions without progress, offer: "Would you like to switch to direct
debugging mode?" If accepted, call `workflow` with systematic-debugging,
passing: symptoms, what was tried, current hypothesis, relevant files/lines.

### Error Handling

| Situation | Action |
|-----------|--------|
| User says "just tell me" | Offer mode switch. If accepted, hand off to `workflow`. |
| User frustrated | Acknowledge. Offer escalation. If continuing, read more code and sharpen questions. |
| Bug trivially obvious | Still ask Phase 1, but make the question pointed enough that the user sees it immediately. |

---

## Mode 2: Forensics (Post-Mortem)

Investigate failed or stuck agent sessions through git history, plan files, and
session artifacts. Read-only -- never modify state. Even when asked to fix, complete
the report and recommend remediation instead.

**Key distinction**: Tool errors ("ruff found 3 lint errors") are harness-level.
Forensics handles workflow-level patterns ("agent edited the same file 5 times
and never progressed").

### Phase 1: GATHER

Collect raw evidence. Determine branch, plan, and time range.

**Step 1: Identify target.** Priority: explicit branch > current branch > explicit plan.
Read CLAUDE.md if present -- conventions define "normal."

**Step 2: Locate plan file.** Check `task_plan.md`, `.feature/state/plan/`,
`plan/active/`. Record whether found. Three of five detectors work without a
plan (stuck loop, crash, degraded abandoned work), so never skip analysis for
a missing plan.

**Step 3: Collect git history.** Run `git log main..HEAD --name-only --format="COMMIT %H %ai %s"`.
Check file change frequency, retry/fix language in messages, and commit message
uniqueness ratio. Focus on most recent 50 commits if the branch has hundreds.

**Step 4: Check working tree.** Run `git status --short`, check for orphaned
worktrees (`git worktree list --porcelain | grep "prunable"`), and locate plan files.

**GATE**: Git history available, branch identified. Proceed to DETECT.

### Phase 2: DETECT

Run all 5 anomaly detectors. Always run every detector -- anomalies correlate
(stuck loop causes missing artifacts causes abandoned work). Each finding needs
a confidence level (High/Medium/Low).

Run in order: Stuck Loop, Missing Artifacts, Abandoned Work, Scope Drift,
Crash/Interruption. Load detector specs and failure signatures from
the deep references below.

**GATE**: All 5 detectors ran. Each produced zero or more findings with
confidence levels.

### Phase 3: REPORT

Every claim must trace to specific evidence.

**Step 1: Scrub.** Scan evidence for `sk-`, `ghp_`, `token=`, `password=`,
`secret=`, `key=`, bearer tokens, base64 credentials. Replace with `[REDACTED]`.
Replace absolute home paths with `~/`.

**Step 2: Anomaly table.** Order by confidence (High first), then detector number.

**Step 3: Root cause hypothesis.** Connect anomalies into a causal chain.
Must be specific, testable, evidence-grounded.
- Bad: "Something went wrong"
- Good: "Agent entered a lint fix loop on server.go (4 commits with 'fix lint'),
  consuming context before VERIFY could run, leaving test artifacts missing"

**Step 4: Remediation.** Advisory only -- never execute fixes.

| Anomaly | Typical Fix |
|---------|-------------|
| Stuck loop | Identify root cause of loop. Fix manually, resume from last successful phase. |
| Missing artifacts | Re-run the failed phase. Clarify artifact definitions. |
| Abandoned work | Resume from last completed phase. Check plan status. |
| Scope drift | Review out-of-scope changes. Revert unrelated ones. |
| Crash/interruption | Preserve uncommitted changes. Clean orphaned worktrees. Resume from last commit. |

**Step 5: Format report** with sections: header (branch, commit count, plan
path), anomaly table, root cause hypothesis, remediation list, evidence
excerpts. All paths redacted, credentials scrubbed.

**GATE**: Report complete, scrubbed, formatted. Deliver to user.

### Forensics Error Handling

| Error | Action |
|-------|--------|
| No git history | Report "insufficient evidence." |
| No plan file | Note limitation. Detectors 2/3/4 degrade or skip. 1/5 still work. |
| Orphaned worktree | Report as crash/interruption evidence. Do not clean up. |
| Git log too large | Focus on most recent 50 commits. Note truncation. |
| Ambiguous target | Ask: "Which branch? Current is [X]." |

## Deep References

| When | Load | Content |
|---|---|---|
| Running Phase 2 detectors | `references/detectors.md` | 5 detector specs with confidence scoring tables and false-positive guidance |
| Matching symptoms to failure types | `references/failure-signatures.md` | Observable patterns, grep commands, causal chain analysis |
