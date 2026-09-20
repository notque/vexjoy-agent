---
name: debugging
description: "Guide a user through Socratic diagnosis, or perform a read-only forensic post-mortem of a failed agent workflow."
user-invocable: false
allowed-tools: [Read, Grep, Glob, Bash]
routing:
  not_for: "code review (use review), implementing a fix or feature (use workflow)"
  triggers: [guide debugging, ask me questions, coaching mode, forensics, what went wrong, stuck loop, diagnose workflow, post-mortem, session crashed, incident review]
  category: process
  pairs_with: [workflow, review]
---

# Debugging

Choose Socratic mode when the user wants coaching; choose Forensics for failed, stuck, or interrupted agent sessions.

## Socratic mode

Inspect relevant code first, then ask one question at a time without embedding the answer. Progress as evidence warrants through: expected vs actual behavior, reproducibility, attempts already made, minimal failing case, error output, runtime state, code path, unverified assumptions, and a testable hypothesis. Mirror the user’s terms and acknowledge discoveries briefly.

Do not reveal the diagnosis while coaching. If the user asks for the answer, is frustrated, or 12 questions produce no progress, offer a switch to direct debugging. On acceptance, hand off the accumulated symptoms, attempts, hypothesis, and relevant paths/lines to `workflow`’s systematic-debugging path. When the user identifies the cause, ask what fix they would apply.

## Forensics mode

This mode is read-only. Even if remediation is requested, finish the evidence report and recommend actions; do not mutate the repository. It diagnoses workflow-level behavior, not ordinary tool output.

1. Identify the explicit branch, otherwise the current branch. Read repository instructions and locate `task_plan.md`, `.feature/state/plan/`, or `plan/active/` if present.
2. Gather branch history, working-tree state, orphaned/prunable worktrees, and plan state. Use the most recent 50 commits when history is large.
3. Run all five detectors in [references/detectors.md](references/detectors.md). Missing plans degrade artifact, abandonment, and scope analysis; they do not prevent loop or interruption analysis.
4. Correlate findings into a specific, testable causal chain. Every finding needs evidence and `High`, `Medium`, or `Low` confidence.
5. Scrub credentials (`sk-`, `ghp_`, bearer values, tokens, passwords, secrets, keys, encoded credentials) and replace absolute home paths with `~/`.

Report target branch, commit count, plan path/absence, findings ordered by confidence, root-cause hypothesis, advisory remediation, and short evidence excerpts. An unavailable git history means “insufficient evidence,” not a fabricated diagnosis. Never clean an orphaned worktree during forensics.
