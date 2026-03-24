---
name: workflow-help
description: |
  Interactive guide to repository workflow system: agents, skills, routing,
  and execution patterns. Use when user asks how the system works, what
  commands are available, or how to use brainstorm/plan/execute phases.
  Use for "how does this work", "what can you do", "explain workflow",
  "help me understand", or "show me the process". Do NOT use for actually
  executing workflows (use workflow-orchestrator) or debugging (use
  systematic-debugging).
version: 2.0.0
user-invocable: true
argument-hint: "[<topic>]"
allowed-tools:
  - Read
  - Grep
  - Glob
---

# Workflow Help Skill

## Operator Context

This skill operates as an operator for workflow education and guidance, configuring Claude's behavior for clear, accurate explanation of the repository's agent/skill/routing architecture. It implements the **Knowledge Transfer** pattern -- understand the user's question, locate the relevant component, explain with concrete examples.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before answering
- **Over-Engineering Prevention**: Answer only what was asked. Do not dump the entire system architecture when the user asks about one skill
- **Accuracy Over Speed**: Read actual SKILL.md and agent files before explaining them; never describe from memory
- **Show Real Examples**: Reference actual skill names, commands, and file paths from this repository
- **No Fabrication**: If a skill or agent does not exist, say so rather than inventing capabilities
- **Route When Appropriate**: If user actually wants to execute a workflow, route to the correct skill instead of explaining it

### Default Behaviors (ON unless disabled)
- **Scope to Question**: Answer the specific topic asked about, then offer to explain related concepts
- **Use Tables for Lists**: Present available skills, agents, and commands in table format
- **Include Invocation Syntax**: Show how to invoke each skill or command mentioned
- **Progressive Disclosure**: Start with overview, offer deeper detail on request
- **Cross-Reference**: Link related skills and agents when explaining one component
- **Verify Before Citing**: Read the actual SKILL.md file before quoting its description or capabilities

### Optional Behaviors (OFF unless enabled)
- **Full Architecture Dump**: Explain the entire Router -> Agent -> Skill -> Script pipeline
- **Comparison Mode**: Compare two skills or agents side-by-side
- **Troubleshooting Guide**: Help diagnose why a skill or route isn't working as expected

## What This Skill CAN Do
- Explain how the /do router classifies and routes requests
- Describe what any specific skill or agent does (by reading its file)
- Show the brainstorm -> plan -> execute workflow phases
- List available skills, agents, hooks, and their purposes
- Explain execution modes (direct vs subagent-driven)
- Clarify when to use which skill for a given task

## What This Skill CANNOT Do
- Execute workflows (use workflow-orchestrator)
- Debug code (use systematic-debugging)
- Create or modify skills (use skill-creator-engineer)
- Run tests or validate code (use verification-before-completion)
- Make decisions about which approach to take for the user's actual task

---

## Instructions

### Phase 1: UNDERSTAND THE QUESTION

**Goal**: Determine exactly what the user wants to know about.

$ARGUMENTS - Parse the user's topic. Common categories:
- `brainstorm` / `plan` / `execute` - Workflow phases
- `skills` / `agents` / `hooks` - Component types
- `routing` / `do` - How routing works
- `subagent` - Subagent-driven execution
- No argument - Provide system overview

**Gate**: Topic identified. Proceed only when you know what to explain.

### Phase 2: GATHER ACCURATE INFORMATION

**Goal**: Read actual files before explaining anything.

**Step 1: Read relevant files**

If explaining a specific skill:
```
Read skills/{skill-name}/SKILL.md
```

If explaining a specific agent:
```
Read agents/{agent-name}.md
```

If explaining routing:
```
Read the /do router configuration
```

If providing overview:
```
Glob for skills/*/SKILL.md and agents/*.md to get current counts
```

**Step 2: Extract key information**
- Name, description, version
- What it CAN and CANNOT do
- How to invoke it
- Related skills or agents

**Gate**: Information gathered from actual files, not memory. Proceed only when gate passes.

### Phase 3: EXPLAIN CLEARLY

**Goal**: Present information in the format most useful for the user's question.

**For system overview**, present the execution architecture:

```
Router (/do) -> Agent (domain expert) -> Skill (methodology) -> Script (execution)
```

Then show key workflow:
1. BRAINSTORM - Clarify requirements, explore approaches
2. WRITE-PLAN - Break into atomic, verifiable tasks
3. EXECUTE - Direct or subagent-driven execution
4. VERIFY - Run tests, validate changes

**For specific components**, use this format:

```markdown
## [Component Name]
**Type**: Skill / Agent / Hook
**Invoke**: /command or skill: name
**Purpose**: One-sentence description
**Key Phases/Capabilities**: Bulleted list
**Related**: Links to related components
```

**For "when to use what"**, use a decision table:

| You Want To... | Use This |
|----------------|----------|
| Start a new feature | `/do implement [feature]` |
| Debug a bug | `/do debug [issue]` |
| Review code | `/do review [code]` |
| Execute an existing plan | `skill: subagent-driven-development` |
| Create a PR | `/pr-sync` |

**Step: Offer next steps**

After explaining, ask if the user wants to:
- Learn about a related component
- Actually execute a workflow (route to appropriate skill)
- See more detail on a specific aspect

**Gate**: User's question answered with information from actual files.

---

## Error Handling

### Error: "Skill or Agent Not Found"
Cause: User asked about a component that does not exist or was renamed
Solution:
1. Search with Glob for similar names
2. Check if it was recently deleted or merged
3. Suggest the closest matching component

### Error: "User Wants Execution, Not Explanation"
Cause: User asked "how do I debug X" meaning "debug X for me"
Solution:
1. Recognize the intent is execution, not education
2. Route to the appropriate skill (e.g., systematic-debugging)
3. Do not explain the debugging process; invoke it

### Error: "Stale Information"
Cause: Skill files may have changed since last read
Solution:
1. Always read files fresh; never rely on cached descriptions
2. Check file modification dates if information seems inconsistent
3. Report any discrepancies found

---

## Anti-Patterns

### Anti-Pattern 1: Explaining From Memory
**What it looks like**: Describing a skill's capabilities without reading its SKILL.md
**Why wrong**: Skills change. Memory drifts. Fabricated capabilities erode trust.
**Do instead**: Read the actual file before every explanation.

### Anti-Pattern 2: Information Dump
**What it looks like**: Listing all 120 skills when user asked about one
**Why wrong**: Overwhelms the user. Buries the relevant answer.
**Do instead**: Answer the specific question. Offer to expand if requested.

### Anti-Pattern 3: Explaining Instead of Routing
**What it looks like**: Spending 500 words explaining how debugging works when user wants their bug fixed
**Why wrong**: User wants action, not education. Wastes time.
**Do instead**: Detect execution intent and route to the correct skill.

### Anti-Pattern 4: Inventing Capabilities
**What it looks like**: "This skill can also do X" when X is not in the SKILL.md
**Why wrong**: Creates false expectations. User tries X and it fails.
**Do instead**: Only cite capabilities listed in the actual file.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "I remember what that skill does" | Memory drifts; files change | Read the actual SKILL.md file |
| "User just needs a quick overview" | Quick overview with wrong info is worse than slow accuracy | Verify against source files |
| "Listing everything is more helpful" | Information overload reduces comprehension | Scope to the question asked |
| "They probably mean execution" | Assuming intent leads to wrong action | Ask if unclear, check $ARGUMENTS |
