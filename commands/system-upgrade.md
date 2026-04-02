---
name: system-upgrade
description: |
  Systematic upgrade pipeline for adapting agents, skills, and hooks when
  Claude Code ships updates, user goals change, or retro learnings accumulate.
version: 1.0.0
route_to:
  agent: system-upgrade-engineer
  skill: system-upgrade
  enhancements:
    - agent-evaluation
    - routing-table-updater
trigger:
  keywords:
    - upgrade agents
    - system upgrade
    - claude update
    - upgrade skills
    - adapt workflow
    - apply claude update
    - apply retro
parameters:
  required:
    - name: trigger
      description: |
        What triggered the upgrade: Claude Code version/release notes,
        description of goal change, or "retro" to use learning.db graduation candidates
  optional:
    - name: scope
      description: "comprehensive | default (default: recent 10 agents + all hooks + all routing tables)"
      default: "default"
    - name: auto
      description: "Skip Phase 3 approval gate and apply all changes automatically"
      default: "false"
---

# /system-upgrade

Entry point for the System Upgrade Pipeline.

## Usage

```
/do upgrade the system — claude just shipped [feature]
/do system upgrade — I'm now working with [new domain]
/do apply retro learnings to upgrade the system
```

## What It Does

**6-Phase Pipeline:**

1. **CHANGELOG** — Parse the trigger, extract actionable change signals
2. **AUDIT** — Scan agents/skills/hooks for affected components
3. **PLAN** — Rank changes (Critical/Important/Minor), present to user for approval
4. **IMPLEMENT** — Dispatch domain specialists in parallel for approved changes
5. **VALIDATE** — Score modified components before/after with agent-evaluation
6. **DEPLOY** — Commit, sync to `~/.claude`, create PR

## Three Trigger Types

| Type | When | Input |
|------|------|-------|
| **claude-release** | Claude Code ships new version | "Claude added Notification hook event" |
| **goal-change** | Your workflow/focus shifts | "I'm now working with Rust" |
| **retro-driven** | Retro learnings ready to embed | "Apply retro" or "/retro graduate" output |

## Key Behavior

**Phase 3 always gates on your approval.** The pipeline shows you a ranked table
of proposed changes with effort estimates before touching any files. You can
approve all, pick specific items, or stop.

## Examples

```
/do upgrade the system — Claude Code shipped structured output support for tools
/do system upgrade — I want to add Rust support to the agent system
/do apply retro learnings to upgrade the system
/do claude update — new hook event Notification was added
```
