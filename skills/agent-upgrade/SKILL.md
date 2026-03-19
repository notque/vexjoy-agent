---
name: agent-upgrade
description: |
  5-phase pipeline for systematically improving an existing agent or skill:
  AUDIT → DIFF → PLAN → IMPLEMENT → RE-EVALUATE. Scores before and after,
  gaps against current templates, and gates on user approval before changes.
  Use when an agent needs quality improvement, template alignment, or
  retro knowledge graduation. Use for "upgrade agent", "improve agent",
  "agent upgrade", "fix agent quality", "align agent to template".
version: 1.0.0
user-invocable: true
agent: skill-creator-engineer
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
  - Agent
  - Edit
  - Write
---

# Agent Upgrade Pipeline

## Operator Context

This skill upgrades a single target agent or skill through a scored, gated pipeline.
It is a **bottom-up** quality mechanism — triggered when a specific component needs
improvement — complementing the **top-down** `system-upgrade` pipeline that handles
multi-component changes driven by external events.

### Hardcoded Behaviors (Always Apply)
- **Score before AND after**: Phase 1 (AUDIT) must produce a baseline score using `agent-evaluation`. Phase 5 (RE-EVALUATE) must produce an after score. Never claim improvement without a measured delta.
- **Plan approval gate**: Phase 3 output MUST be presented to the user and explicitly approved before Phase 4 begins. Do not implement any changes without approval.
- **Domain logic is off-limits**: Phase 4 MUST NOT alter an agent's routing triggers, domain coverage, or core methodology. Only structural improvements, template alignment, Operator Context additions, and retro graduations are in scope unless the user explicitly directs otherwise.
- **Use agent-evaluation for scoring**: Do not self-assess quality. Invoke the `agent-evaluation` skill for objective scores.

### Default Behaviors (ON unless disabled)
- **Check retro graduates**: Phase 1 always searches learning.db for entries targeting the agent under upgrade. Graduation candidates are surfaced in Phase 2.
- **Peer comparison**: Phase 2 compares the target against 2–3 agents in the same category for consistency gaps (e.g., comparing a Go agent against other Go agents).
- **Regression protection**: If Phase 5 delta is negative, report to user and do NOT auto-revert. User decides.

### Optional Behaviors (OFF unless enabled)
- **Auto-approve**: Skip the Phase 3 user approval gate (enable with "auto-apply" or "skip approval").
- **Skip peer comparison**: Omit peer consistency check in Phase 2 (enable with "skip peers").
- **Skip retro scan**: Omit retro graduate scan (enable with "skip retro").

## What This Skill CAN Do
- Establish an objective baseline score for any agent or skill in the repository
- Identify structural gaps against `AGENT_TEMPLATE_V2` (missing sections, outdated patterns)
- Surface learning.db entries ready for graduation into the target agent
- Produce a ranked improvement plan with Critical/Important/Minor tiers
- Apply approved improvements: missing sections, Operator Context behaviors, graduated retro patterns, peer consistency fixes
- Score the result and report the quality delta

## What This Skill CANNOT Do
- Change an agent's domain logic, routing triggers, or core methodology without explicit user direction
- Guarantee correctness of generated improvements — the RE-EVALUATE phase catches regressions
- Graduate retro entries automatically — graduation is proposed in the plan and requires approval

---

## Instructions

### Phase 1: AUDIT

**Goal**: Establish a baseline quality score for the target agent or skill.

**Step 1**: Identify the target file from the user's input.

```
# Common target patterns:
agents/golang-general-engineer.md
agents/python-general-engineer.md
skills/go-testing/SKILL.md
```

If the user names an agent without a path, resolve it:
```bash
ls agents/ | grep [name]
ls skills/ | grep [name]
```

**Step 2**: Run `agent-evaluation` skill on the target file to get the baseline score (0–100) and grade (A/B/C/F).

**Step 3**: Scan for retro entries targeting this agent:
```bash
python3 scripts/learning-db.py search "[agent-name]" 2>/dev/null || echo "No retro candidates found"
```

**Step 4**: Check for staleness markers in the target file:
- Missing frontmatter fields: `context`, `model`, `user-invocable` (for skills)
- Operator Context section absent or incomplete (no Hardcoded/Default/Optional subsections)
- Version references to deprecated patterns
- Hook event types that have been superseded

**Output**:
```
AUDIT COMPLETE
==============
Target: [file path]
Baseline: [score]/100 ([grade])

Known gaps detected:
  - [gap 1]
  - [gap 2]
  ...

Retro candidates: [N found | none]
```

**Gate**: Baseline score recorded. Proceed to Phase 2.

---

### Phase 2: DIFF

**Goal**: Gap analysis against current patterns, templates, and peers.

**Step 1**: Compare target against `AGENT_TEMPLATE_V2` structure. Read the template:
```bash
# Look for AGENT_TEMPLATE_V2 reference
ls agents/ | grep -i template
grep -rl "AGENT_TEMPLATE_V2" agents/ skills/ | head -5
```

Check for required sections. For agents:
- Frontmatter with `routing:` block (triggers, pairs_with, complexity, category)
- Operator Context with all three subsections (Hardcoded, Default, Optional)
- What This Agent CAN Do / CANNOT Do
- Error Handling section
- Anti-Patterns section

For skills:
- Frontmatter with `agent:`, `allowed-tools:`, `user-invocable:`
- Operator Context section
- Phase-by-phase instructions with gates
- Error Handling section
- Anti-Patterns section

**Step 2**: Assess Operator Context completeness:

| Subsection | Present? | Complete? |
|------------|----------|-----------|
| Hardcoded Behaviors | ? | ? |
| Default Behaviors | ? | ? |
| Optional Behaviors | ? | ? |

**Step 3**: Identify retro graduation candidates from Phase 1 scan. For each candidate:
- Note the learning (what pattern or behavior should be embedded)
- Identify where in the target it should be added (new hardcoded behavior, key pattern, error handling rule)

**Step 4**: Peer consistency check. Find 2–3 agents in the same category:
```bash
# For a Go agent, compare against other Go agents
grep -l "golang\|go\b" agents/*.md | grep -v [target] | head -3
```
Read peer Operator Context and structure. Note patterns present in peers but missing in target.

**Output**: Diff report — categorized list of gaps:

```
DIFF REPORT
===========
Target: [file path]

Missing Sections:
  - [section name]: [description of what's needed]

Outdated Patterns:
  - [pattern]: [current form] → [correct form]

Operator Context Gaps:
  - [missing behavior]: [description]

Retro Graduation Candidates:
  - [retro entry]: → [where it belongs in the agent]

Peer Inconsistencies:
  - [pattern in peers]: [missing from target]
```

**Gate**: Diff report produced. Proceed to Phase 3.

---

### Phase 3: PLAN

**Goal**: Prioritize improvements and get user approval before any changes.

**Step 1**: Rank all gaps from Phase 2 by tier:

| Tier | Criteria | Examples |
|------|----------|---------|
| **Critical** | Broken structure, missing required sections | No Operator Context, broken frontmatter |
| **Important** | Missing patterns that meaningfully affect quality | Missing Hardcoded behaviors, ungraduated retro with score ≥ 6 |
| **Minor** | Style alignment, peer consistency, optional fields | Missing optional frontmatter field, peer wording alignment |

**Step 2**: Present the ranked plan to the user:

```
AGENT UPGRADE PLAN
==================
Target: [file path]
Baseline: [score]/100 ([grade])

Proposed Improvements (Ranked):

CRITICAL (must fix):
  1. Add Operator Context section — Hardcoded/Default/Optional subsections absent [~20min]
  2. Add Error Handling section — 3 unhandled failure modes identified [~15min]

IMPORTANT (should fix):
  3. Graduate retro entry: "[learning summary]" → new Hardcoded behavior [~10min]
  4. Add missing frontmatter field: `model: sonnet` [~2min]
  5. Add Anti-Patterns section — missing entirely [~15min]

MINOR (nice to have):
  6. Align "What This Agent CANNOT Do" wording to peer style [~5min]

Total: 6 improvements
Estimated quality delta: +12 to +18 points

Proceed with implementation? (or specify which items to include/exclude)
```

**Step 3**: Wait for user approval. Do NOT proceed to Phase 4 without it.
- "yes", "proceed", "go ahead", "do it" → proceed with all items
- User specifies subset (e.g., "skip 5 and 6") → update plan, proceed with approved subset
- "no" or "stop" → stop and summarize what was decided

**Gate**: User approval received. Proceed to Phase 4.

---

### Phase 4: IMPLEMENT

**Goal**: Apply the approved improvements to the target file.

**Step 1**: Read the current target file in full before making any edits. Never edit from memory.

**Step 2**: For each approved improvement, apply in order of tier (Critical first):

**For missing sections** (add from AGENT_TEMPLATE_V2 patterns):
- Operator Context: Add the three-subsection structure. Populate Hardcoded with behaviors that ARE enforced, Default with on-by-default behaviors, Optional with opt-in behaviors.
- Error Handling: Add 2–4 concrete error cases with Cause + Solution format.
- Anti-Patterns: Add 2–3 named anti-patterns with What it looks like / Why wrong / Do instead format.

**For retro graduations**:
- Add the learning as a new Hardcoded behavior (if it should always apply) or a new pattern/rule in the relevant section.
- Preserve the original voice and specificity of the retro entry — don't paraphrase it into generic advice.

**For outdated patterns**:
- Update to current convention. Reference the peer agents or template for the correct form.

**For peer inconsistencies**:
- Align to the majority pattern observed across peers. If peers themselves are inconsistent, align to the most recent or highest-scoring peer.

**Step 3**: Do NOT change any of the following without explicit user direction:
- Routing triggers (`triggers:` frontmatter field)
- Domain coverage statements
- Core methodology or phase structure (for skills)
- Agent pairing recommendations (`pairs_with:`)

**Gate**: All approved items implemented. No pending items from the approved plan.

---

### Phase 5: RE-EVALUATE

**Goal**: Score the updated agent and compute quality delta.

**Step 1**: Run `agent-evaluation` skill on the modified file. Record the after score and grade.

**Step 2**: Compute delta:
```
delta = after_score - baseline_score
```

**Step 3**: If delta is negative (regression):
- Show the exact diff of changes applied
- Report which change likely caused the regression
- Ask user whether to revert the specific change or proceed anyway
- Do NOT auto-revert

**Step 4**: Report upgrade completion:

```
UPGRADE COMPLETE
================
[agent-name or skill-name]
  Before: [baseline_score] ([baseline_grade])
  After:  [after_score] ([after_grade])
  Delta:  +[N] points

Improvements applied: [N/N approved items]

Items applied:
  ✓ [improvement 1]
  ✓ [improvement 2]
  ○ [improvement N — skipped by user]
```

If the delta is positive, the upgrade is complete. If the delta is zero or negative and the user has not already acknowledged it, surface the regression report before closing.

---

## Error Handling

### Error: "agent-evaluation skill unavailable or errors out"
Cause: The `agent-evaluation` skill has a dependency issue or the target file is malformed.
Solution: Read the target file manually and apply the scoring rubric from the CLAUDE.md quality gates section (Structure 20pts, Operator Context 15pts, Error Handling 15pts, Reference Files 10pts, Validation Scripts 10pts, Content Depth 30pts). Produce a manual score. Note it as manually derived in the report.

### Error: "No learning.db entries found for this agent"
Cause: No relevant learnings in the database for this agent's domain.
Solution: Skip retro graduation step and note it in the diff report. Learnings accumulate naturally during work.

### Error: "No AGENT_TEMPLATE_V2 found in repository"
Cause: Template file not yet created or named differently.
Solution: Use the highest-scoring agent (from recent agent-evaluation runs or MEMORY.md) as the de facto template for structural comparison. Note the substitution in the diff report.

### Error: "Regression detected in Phase 5 (delta is negative)"
Cause: One or more applied improvements reduced the evaluation score.
Solution: Show the diff, identify the likely culprit change, and ask the user whether to revert it. Do NOT auto-revert. Proceed only after user makes a decision.

### Error: "User approves plan but target file changes between Phase 3 and Phase 4"
Cause: Another process or agent modified the file during the gap.
Solution: Re-read the file before editing. If the baseline state has changed materially, re-run Phase 1–2 and re-present the plan.

---

## Anti-Patterns

### Anti-Pattern 1: Skipping the Baseline Score
**What it looks like**: Jumping straight to DIFF or PLAN without running agent-evaluation in Phase 1.
**Why wrong**: Without a baseline, there is no way to verify improvement. "Looks better" is not a quality claim.
**Do instead**: Always score first. Even a rough manual score is better than no baseline.

### Anti-Pattern 2: Implementing Without Plan Approval
**What it looks like**: Editing the target file immediately after Phase 2 without presenting the plan.
**Why wrong**: The user may have strong opinions about which improvements are appropriate. Silent mass edits violate the approval contract.
**Do instead**: Always present the ranked plan and wait for explicit approval. The gate exists for a reason.

### Anti-Pattern 3: Changing Domain Logic
**What it looks like**: "Improving" an agent by changing its routing triggers, expanding its domain scope, or altering its core methodology as part of the upgrade.
**Why wrong**: Domain logic changes require deliberate user decision, not opportunistic bundling. They can break routing, cause misrouting, or alter behavior the user depends on.
**Do instead**: Limit Phase 4 to structural improvements, Operator Context additions, retro graduations, and template alignment. Flag domain logic questions to the user separately.

### Anti-Pattern 4: Self-Assessing Quality Instead of Using agent-evaluation
**What it looks like**: Saying "the agent looks much better now" without running RE-EVALUATE.
**Why wrong**: Self-assessment is the exact failure mode that the scoring pipeline exists to prevent. An agent can look better and score worse.
**Do instead**: Always run agent-evaluation in Phase 5. The delta is the claim. Everything else is opinion.

### Anti-Pattern 5: Over-Graduating Retro Entries
**What it looks like**: Adding every learning.db entry as a new Hardcoded behavior, bloating the agent with marginally relevant rules.
**Why wrong**: Bloat degrades usability and reduces the signal-to-noise ratio of the Operator Context.
**Do instead**: Graduate only retro entries with score ≥ 6 that are directly relevant to the target agent's domain. Surfacing them in the plan lets the user decide their importance.

---

## Examples

### Example 1: Template alignment upgrade
User: "Upgrade the python-general-engineer agent — it's missing Operator Context."
Actions: Phase 1 scores it (baseline: 58/C). Phase 2 finds missing Operator Context, no Anti-Patterns section, one retro graduation candidate. Phase 3 presents 3-item plan (Critical: add Operator Context; Important: graduate retro entry; Minor: add Anti-Patterns). User approves all. Phase 4 adds sections. Phase 5 re-evaluates (after: 74/B, delta: +16). Upgrade complete.

### Example 2: Retro graduation only
User: "Graduate the retro learnings about debugging into the systematic-debugging skill."
Actions: Phase 1 scores systematic-debugging (baseline: 81/A). Phase 2 finds 2 retro entries in debugging.md with tags matching the skill. Phase 3 presents 2-item plan (both Important: inject as Hardcoded behaviors). User approves item 1, skips item 2. Phase 4 applies one graduation. Phase 5 re-evaluates (after: 84/A, delta: +3). Upgrade complete.

### Example 3: Regression caught
User: "Improve the hook-development-engineer agent — align it to current patterns."
Actions: Phase 1 scores (baseline: 72/B). Phase 2 finds 4 gaps. Phase 3 plan approved. Phase 4 applies all 4. Phase 5 re-evaluates (after: 69/C, delta: -3). Regression detected. Show diff. Ask user: revert item 3 (the likely culprit) or accept? User says revert. Item 3 reverted. Phase 5 re-run (after: 75/B, delta: +3). Upgrade complete.
