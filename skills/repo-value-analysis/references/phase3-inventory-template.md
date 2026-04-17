# Phase 3: INVENTORY Agent Template

Dispatch 1 Agent (in background, concurrent with Phase 2 zone agents) to inventory our system. Running this in parallel is safe because inventory is a read-only catalog of our codebase:

```
You are cataloging the claude-code-toolkit repository for comparison purposes.

Inventory these component types:
1. Agents (agents/*.md) - count and list with brief descriptions
2. Skills (skills/*/SKILL.md) - count and list with brief descriptions
3. Hooks (hooks/*.py) - count and list with brief descriptions
4. Scripts (scripts/*.py) - count and list with brief descriptions

For each category, note:
- Total count
- Key capability areas covered
- Notable patterns in how components are structured

Save your inventory to /tmp/self-inventory.md
```

Running this in parallel (not waiting for Phase 2 to finish) reduces total pipeline time from `Phase1 + Phase2 + Phase3` to roughly `Phase1 + max(Phase2, Phase3)`.
