---
name: system-upgrade
description: |
  Systematic 6-phase pipeline for adapting agents, skills, hooks, and scripts to
  external changes: Claude Code releases, user goal shifts, or retro-driven upgrades.
  CHANGELOG → AUDIT → PLAN → IMPLEMENT → VALIDATE → DEPLOY. Always shows ranked
  plan to user before executing any changes. Use when Claude Code ships a new version,
  user's workflow preferences change, or retro accumulation warrants system-wide
  embedding. Use for "upgrade agents", "system upgrade", "claude update",
  "upgrade skills", "adapt workflow", "apply claude update", "system health".
version: 1.0.0
user-invocable: false
agent: system-upgrade-engineer
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
  - Agent
  - Edit
  - Write
routing:
  force_route: true
  triggers:
    - system upgrade
    - upgrade agents
    - claude update
    - upgrade skills
    - adapt workflow
    - system health
  pairs_with:
    - agent-upgrade
    - agent-evaluation
  complexity: Complex
  category: meta
---

# System Upgrade Pipeline

## Operator Context

This skill orchestrates systematic upgrades to the agent/skill/hook/script ecosystem
when external changes warrant adaptation. It is a **top-down** upgrade mechanism —
triggered by Claude Code releases, user goal changes, or accumulated retro learnings —
complementing the **bottom-up** retro-knowledge-injector.

### Hardcoded Behaviors (Always Apply)
- **Show Plan Before Implementing**: Phase 3 output (ranked upgrade list) MUST be presented to the user and approved before Phase 4 begins. Never silently execute upgrades.
- **Reuse Domain Agents**: Phase 4 (IMPLEMENT) dispatches to existing domain agents (skill-creator-engineer, agent-creator-engineer, hook-development-engineer, golang-general-engineer, etc.). The upgrade engineer orchestrates; specialists execute.
- **Parallel Fan-Out**: When 3+ components need the same type of upgrade, dispatch in parallel using multiple Agent tool calls in a single message.
- **Score Delta Required**: Phase 5 (VALIDATE) must produce before/after evaluation delta, not just "looks good." Use `agent-evaluation` skill.
- **Trigger Type Determines Input**: The three trigger types (claude-release, goal-change, retro-driven) require different input parsing in Phase 1.

### Default Behaviors (ON unless disabled)
- **Scope Limiting**: Default audit depth = 10 most-recently-modified agents + all hooks. Full audit only if user says "comprehensive" or "all".
- **Dry Run Presentation**: Show Phase 3 output as a formatted table with Tier (critical/important/minor) and effort estimate.
- **Branch Creation**: Create a branch before Phase 4 (e.g., `chore/system-upgrade-YYYY-MM-DD`).

### Optional Behaviors (OFF unless enabled)
- **Comprehensive Audit**: Audit all agents and skills (slow; enable with "comprehensive audit")
- **Full Upgrade Diff**: Force a full component scan instead of incremental diff (enable with `python3 ~/.claude/scripts/upgrade-diff.py --full` or "full upgrade")
- **Auto-Approve**: Skip user approval gate between Phase 3 and Phase 4 (enable with "auto-apply")
- **Skip Validate**: Skip agent-evaluation scoring (enable with "skip validation")

## What This Skill CAN Do
- Parse Claude Code release notes and map changes to affected component types
- Audit agents, skills, hooks, and scripts for patterns that need updating
- Produce a ranked upgrade plan with tier classification and estimated effort
- Dispatch parallel upgrade agents for independent changes
- Score components before/after with agent-evaluation
- Create branch, commit, sync to ~/.claude, and create PR

## What This Skill CANNOT Do
- Make architectural decisions without user approval (Phase 3 gate is mandatory)
- Modify core scripts (feature-state.py, plan-manager.py) — those require explicit user direction
- Guarantee correctness of generated upgrades — validation phase catches regressions

---

## Instructions

### Phase 1: CHANGELOG

**Goal**: Parse the external change and extract actionable upgrade signals.

**Determine trigger type** from user's input:

| Trigger Type | Signals | Input Format |
|-------------|---------|--------------|
| `claude-release` | "claude update", "new version", "release notes", "shipped X" | Version number or release notes text |
| `goal-change` | "I now want", "we're moving to", "new focus", "deprecate X" | User's description of the change |
| `retro-driven` | "retro graduate", "apply retro", "/retro" showed 5+ candidates | learning.db design/gotcha entries |

**For `claude-release`**: Extract from user's input or web search for Claude Code release notes:
- New hook event types (e.g., `Notification`, `ToolResult`)
- New tool capabilities or changed defaults
- New slash command patterns
- Deprecated features or behaviors
- New frontmatter fields for agents/skills

**For `goal-change`**: Parse the user's statement into:
- What domains/workflows are now in scope (NEW)
- What domains/workflows are no longer in scope (DEPRECATED)
- What patterns should be applied everywhere (ENFORCE)

**For `retro-driven`**: Query the learning database for graduation candidates:
```bash
python3 ~/.claude/scripts/learning-db.py query --category design --category gotcha
```
Evaluate entries for actionability and specificity. These are the upgrade signals.

**Output**: A structured "Change Manifest" — a list of change signals with type, description, and likely affected component types.

**Gate**: Change Manifest has at least 1 actionable signal. If zero signals found, report to user and stop.

---

### Phase 2: AUDIT

**Goal**: Scan the codebase and identify which components are affected by the Change Manifest.

**Step 0**: Check for incremental mode.

```bash
python3 ~/.claude/scripts/upgrade-diff.py
```

Evaluate the JSON output:
- If `mode` is `"incremental"` and `total_changed > 0`: scope the audit to only the files listed in `changed`. Skip Step 1 (audit depth) and proceed directly to Step 2 using only these components.
- If `mode` is `"incremental"` and `total_changed == 0`: report "No components changed since last upgrade" to the user and **stop**. No further phases are needed.
- If `mode` is `"full"` (first run or `--full` flag): proceed with existing full audit behavior starting at Step 1.

**Step 1**: Determine audit depth.
- Default: 10 most-recently-modified agents + all hooks + all relevant skills
- Comprehensive: all agents + all skills + all hooks

```bash
# Get most recently modified agents
ls -t agents/*.md | head -10

# Get all hooks
ls hooks/*.py

# Get relevant skills based on change signals
```

**Step 2**: For each change signal in the Change Manifest, search for affected components:

```bash
# Example: "new Notification hook event" signal
grep -l "PostToolUse\|PreToolUse\|SessionStart" hooks/*.py
grep -rn "event_type\|hook_event" hooks/

# Example: "user wants Go concurrency everywhere" signal
grep -l "goroutine\|concurrency" agents/*.md skills/*/SKILL.md
```

**Step 3**: For each affected component, classify the required change:

| Change Type | Description | Effort |
|------------|-------------|--------|
| `deprecate` | Component is now obsolete or superseded | Low |
| `upgrade` | Component needs modification to use new capability | Medium |
| `create-new` | Gap identified — new component needed | High |
| `inject-pattern` | Add a new hardcoded behavior or rule | Low-Medium |

**Step 4**: Produce the **Audit Report** — a list of affected components with their change type and rationale.

**Gate**: Audit Report produced. Proceed to Phase 3.

---

### Phase 3: PLAN

**Goal**: Produce a ranked upgrade plan and get user approval before any changes.

**Step 1**: Sort the Audit Report by priority:

| Tier | Criteria | Examples |
|------|----------|---------|
| **Critical** | Broken functionality or security | Hook that references deprecated event type |
| **Important** | Missing new capability that changes quality | Agent not using new hook capability |
| **Minor** | Style alignment or cosmetic | Agent missing new optional frontmatter field |

**Step 2**: Present the ranked plan to the user:

```
SYSTEM UPGRADE PLAN
===================

Trigger: [claude-release v4.7 | goal-change | retro-driven]
Change: [brief description]

Proposed Changes (Ranked):

CRITICAL (must fix):
  1. hooks/error-learner.py — Add Notification event handler [upgrade, ~30min]
  2. hooks/pretool-learning-injector.py — Update for new tool event format [upgrade, ~20min]

IMPORTANT (should fix):
  3. agents/hook-development-engineer.md — Document Notification event type [inject-pattern, ~15min]
  4. skills/go-testing/SKILL.md — Apply new pattern from retro L2 [inject-pattern, ~10min]

MINOR (nice to have):
  5. agents/skill-creator-engineer.md — Add new frontmatter field docs [upgrade, ~5min]

Total: 5 changes across 5 components
Parallel dispatch: 3 groups (hooks, agents, skills)

Proceed with implementation? (or modify the plan)
```

**Step 3**: Wait for user approval. Do NOT proceed to Phase 4 without explicit approval.
- If user says "yes", "proceed", "go ahead", "do it" → proceed to Phase 4
- If user modifies the plan → update and re-present
- If user says "no" or "stop" → stop and summarize what was decided

**Gate**: User approved the plan. Branch created.

```bash
git checkout -b chore/system-upgrade-$(date +%Y-%m-%d)
```

---

### Phase 4: IMPLEMENT

**Goal**: Execute the approved plan by dispatching domain agents for each change.

**Step 1**: Group changes by domain agent that should handle them:

| Change Domain | Domain Agent |
|--------------|-------------|
| Hook modifications | hook-development-engineer |
| Agent upgrades | agent-creator-engineer (or skill-creator-engineer for agents) |
| Skill upgrades | skill-creator-engineer |
| Routing changes | routing-table-updater |
| Pattern injection | skill-creator-engineer or direct Edit |

**Step 2**: Dispatch parallel agents for independent groups. Use a single message with multiple Agent tool calls for changes that don't depend on each other.

For each dispatched agent, provide:
- The specific component to modify (file path)
- The exact change to make (from Phase 3 plan)
- The rationale (from the Change Manifest)
- The relevant context (surrounding code, other files that reference this component)

**Step 3**: For low-effort changes (inject-pattern, Minor tier), make direct edits rather than dispatching agents. Batch these into one pass.

**Step 4**: Track completion. Mark each planned item as done as agents complete.

**Gate**: All approved changes implemented. No pending items.

---

### Phase 5: VALIDATE

**Goal**: Score changed components before/after to quantify upgrade quality.

**Step 1**: For each modified agent or skill, run evaluation:

Use the `agent-evaluation` skill on the modified files. Compare against a baseline if available, or simply produce absolute scores.

```
VALIDATION REPORT
=================

[component]
  Before: [score if available, or "N/A (new)"]
  After:  [score]
  Delta:  [+N or new]
  Grade:  [A/B/C/F]
```

**Step 2**: Flag any regressions (after < before). For regressions:
- Report to user
- Suggest fix or revert
- Do NOT auto-revert — user decides

**Step 3**: For hook modifications, run syntax check:
```bash
python3 -m py_compile hooks/[modified-hook].py
```

**Gate**: All components pass syntax check. No regressions (or user acknowledges regressions). Proceed to Phase 6.

---

### Phase 6: DEPLOY

**Goal**: Commit changes, sync to ~/.claude, create PR.

**Step 1**: Sync modified files to `~/.claude/` (agents, skills, hooks, commands that were modified).

```bash
python3 hooks/sync-to-user-claude.py  # or call the sync script directly
```

**Step 2**: Stage and commit:
```bash
git add agents/ skills/ hooks/ commands/
git commit -m "chore: system upgrade — [brief description of trigger]

[List top 3 changes from Phase 3 plan]"
```

**Step 3**: Push and create PR using `pr-pipeline` skill.

**Step 4**: Record upgrade SHA so the next run diffs incrementally:
```bash
python3 ~/.claude/scripts/upgrade-diff.py --record
```

**Step 5**: Produce completion summary:

```
SYSTEM UPGRADE COMPLETE
=======================

Trigger: [type and description]
Branch:  chore/system-upgrade-YYYY-MM-DD
PR:      [URL]

Changes Applied:
  ✓ [N] Critical
  ✓ [N] Important
  ○ [N] Minor (skipped/deferred)

Validation: [N/N components scored, mean grade [X]]

Next Upgrade: Run /system-upgrade after next Claude Code release
              or when /retro shows 5+ graduation candidates
```

**Gate**: Changes committed, synced to ~/.claude, PR created, and upgrade SHA recorded. Pipeline complete.

---

## Error Handling

### Error: "No actionable signals in Change Manifest"
Cause: The changelog/goal statement didn't produce clear change signals.
Solution: Ask user to be more specific. "Claude Code shipped X" → "what specific feature in X applies to our hooks/agents?"

### Error: "Domain agent returned incomplete work"
Cause: Dispatched agent didn't finish all changes in its group.
Solution: Re-dispatch with more specific instructions. Check agent output for errors. Do NOT skip to Phase 5 with incomplete work.

### Error: "Regression detected in Phase 5"
Cause: A component scored lower after modification.
Solution: Show diff of changes to user. Offer to revert the specific component. Do NOT auto-revert without user approval.

### Error: "Sync script not found"
Cause: `hooks/sync-to-user-claude.py` missing or broken.
Solution: Manually copy modified files to `~/.claude/` equivalent directories. Report the broken sync script for future fixing.

---

## Anti-Patterns

### Anti-Pattern 1: Skipping the Plan Approval Gate
**What it looks like**: Moving from AUDIT directly to IMPLEMENT without showing the user what will change
**Why wrong**: Mass edits without visibility can break the system in hard-to-trace ways
**Do instead**: Always present the ranked plan and wait for explicit approval

### Anti-Pattern 2: Handling All Changes Directly Instead of Dispatching
**What it looks like**: Making all edits inline rather than routing to domain agents
**Why wrong**: Domain agents (skill-creator-engineer, hook-development-engineer) know the templates and anti-patterns for their domain
**Do instead**: Dispatch to domain agents for anything beyond simple pattern injection

### Anti-Pattern 3: Auditing Everything Every Time
**What it looks like**: Full audit of all 120+ skills on every trigger
**Why wrong**: Most changes affect a subset of components; full audits waste time and dilute focus
**Do instead**: Target the audit to the change signals. Comprehensive mode is opt-in.

### Anti-Pattern 4: Skipping VALIDATE for "Simple" Changes
**What it looks like**: Deploying without agent-evaluation scores because "it's just a comment injection"
**Why wrong**: Even small changes can break an agent's Operator Context or scoring criteria
**Do instead**: Always score — even a 1-minute validation catches regressions before they reach production

---

## Examples

### Example 1: Claude Code release with new hook event
User: "Claude Code just shipped with a Notification event type for hooks. Upgrade the system."
Actions: Phase 1 parses "Notification event type". Phase 2 scans all hooks for event handling. Phase 3 shows plan (3 hooks need updating, 2 agents need docs update). User approves. Phase 4 dispatches hook-development-engineer. Phase 5 validates. Phase 6 deploys.

### Example 2: Goal change — new domain focus
User: "I'm now working heavily with Rust. Update the system to handle Rust projects."
Actions: Phase 1 extracts "Rust as new domain". Phase 2 audits hooks (no Rust file patterns), `/do` routing (no Rust triggers), error-learner (no Rust tags). Phase 3 proposes: 1 new agent (rust-general-engineer), 2 hook updates (learning injector + retro injector), 1 routing update. User approves. Phase 4 dispatches agent-creator-engineer + hook-development-engineer in parallel. Phases 5–6 validate and deploy.

### Example 3: Retro-driven upgrade
User: "/retro graduate" shows 7 ready candidates.
Actions: Phase 1 queries learning.db for design/gotcha candidates as the Change Manifest. Phase 2 maps candidates to target agents. Phase 3 proposes injecting 7 patterns into 5 agents. User approves with "skip 3 and 6". Phase 4 injects 5 patterns directly (Low effort, no domain agent needed). Phase 5 scores the 5 modified agents. Phase 6 deploys.

---

## References

- [agent-upgrade](../agent-upgrade/SKILL.md) - Bottom-up single-agent upgrade pipeline (complements this top-down system pipeline)
- [agent-evaluation](../../skills/agent-evaluation/SKILL.md) - Objective scoring skill used in Phase 5 validation
- [pr-pipeline](../pr-pipeline/SKILL.md) - PR creation pipeline used in Phase 6 deploy
- [upgrade-diff.py](../../scripts/upgrade-diff.py) - Incremental diff script for scoping audits
- [learning-db.py](../../scripts/learning-db.py) - Script for querying retro graduation candidates
