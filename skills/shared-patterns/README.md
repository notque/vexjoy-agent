# Shared Patterns

Reusable workflow patterns referenced by multiple skills and agents.
These are NOT skills themselves - they are building blocks.

## Usage

In your SKILL.md, reference patterns with relative links:

```markdown
See [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md)
for mandatory verification before completion.
```

In agent files (from agents/):

```markdown
See [Anti-Rationalization](../skills/shared-patterns/anti-rationalization-core.md)
```

## Available Patterns

| Pattern | Purpose | Used By |
|---------|---------|---------|
| `anti-rationalization-core.md` | Prevent shortcut rationalizations | All implementation skills |
| `anti-rationalization-review.md` | Review-specific rationalizations | Review skills/agents |
| `anti-rationalization-testing.md` | Testing-specific rationalizations | TDD, testing skills |
| `anti-rationalization-security.md` | Security-specific rationalizations | Security review agents |
| `pressure-resistance.md` | Handle user pressure to skip steps | All skills |
| `gate-enforcement.md` | Phase transition rules | Workflow skills |
| `verification-checklist.md` | Pre-completion checks | All skills |
| `execution-report-format.md` | Structured output format | Review/analysis skills |
| `severity-classification.md` | Issue severity definitions | Review skills |
| `output-schemas.md` | Standardized agent output patterns | All agents |
| `forbidden-patterns-template.md` | Template for domain-specific hard gates | Domain agents (Go, Python, etc.) |
| `blocker-criteria.md` | When to STOP and ask vs proceed | All agents |
| `analysis-paralysis-guard.md` | Prevent unbounded read-only exploration | Debugging, research, exploration skills |
| `autonomous-repair.md` | Bounded self-repair with RETRY/DECOMPOSE/PRUNE/ESCALATE | Workflow orchestrator, pipeline skills |

## Pattern vs Skill Distinction

| Type | Has SKILL.md | User Invocable | Purpose |
|------|--------------|----------------|---------|
| Skill | Yes | Yes (via /skill-name) | Complete workflow |
| Pattern | No | No | Building block for skills |

## Creating New Patterns

Before creating a new pattern:

1. **Search first** - Does this already exist?
2. **Check usage** - Will 3+ skills use this?
3. **Keep focused** - One concept per pattern file

Pattern file structure:

```markdown
# Pattern Name

Brief description of what this pattern addresses.

## When to Use

- Condition 1
- Condition 2

## The Pattern

[Main content - tables, checklists, rules]

## Examples

[Concrete usage examples]

## Related Patterns

- [Other Pattern](./other-pattern.md) - relationship
```

## Extension Syntax

Skills should ADD domain-specific rows, not duplicate core content:

```markdown
## Anti-Rationalization

See [core patterns](../shared-patterns/anti-rationalization-core.md).

Additional for this domain:

| Rationalization | Why Wrong | Action |
|-----------------|-----------|--------|
| [domain-specific] | [reason] | [action] |
```
