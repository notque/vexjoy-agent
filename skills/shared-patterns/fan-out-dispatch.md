# Fan-Out / Fan-In Dispatch Pattern

Canonical pattern for dispatching multiple agents in parallel, collecting results, and integrating findings. Referenced by skills that need concurrent agent execution.

## Critical Constraint

All Agent/Task tool invocations for a wave MUST appear in a **single message** for true parallelism. Dispatching agents one at a time serializes the work and defeats the purpose.

```
CORRECT:  One message with 5 Task tool calls → 5 agents run concurrently
WRONG:    5 sequential messages with 1 Task call each → agents run one at a time
```

## Dispatch Rules

1. **One message per wave** — all agents in a wave dispatched together
2. **Cap at 10 concurrent agents** — coordination overhead increases beyond this
3. **Scoped prompts** — each agent receives explicit scope, goal, constraints, and expected output format
4. **No cross-contamination** — agents receive only their assigned perspective/scope, not each other's
5. **Branch convergence** — if agents write code, create one target branch BEFORE dispatch; agents must NOT create their own branches

## Wave Ordering

When agents have overlapping scopes:

```
Wave 1 (parallel): [task-1, task-2] -- no overlap
Wave 2 (after wave 1): [task-3] -- overlaps with task-1
```

Tasks within a wave run concurrently. Waves run sequentially. Wait for wave N to complete before dispatching wave N+1.

## Graceful Degradation

Not all agents are guaranteed to complete (timeout, errors, etc.). Degrade gracefully:

| Agents Completed | Action |
|------------------|--------|
| 80-100% | Full pipeline, excellent coverage |
| 50-79% | Proceed, note gaps in report |
| 30-49% | Proceed with caution, synthesis will be thinner |
| 10-29% | Abort parallel approach, fall back to inline analysis |
| 0% | Critical failure, investigate cause |

## Timeout Handling

```
Agent running > 5 minutes?
    +-- YES --> Check progress (non-blocking)
    |           +-- Making progress? --> Wait 2 more minutes
    |           +-- Stuck? --> Mark as timed out, proceed with completed agents
    +-- NO --> Continue waiting
```

## Result Integration

After all agents return:

1. **Verify completeness** — check how many agents returned results
2. **Check for conflicts** — did agents produce contradictory findings or modify overlapping files?
3. **Synthesize** — merge findings into unified output, noting which agents contributed each finding
4. **Report gaps** — explicitly state what was NOT covered due to agent failures/timeouts

## Agent Prompt Template

```markdown
[Task description for this specific agent]

Context: [What this subsystem/area does]

Your task:
1. [Specific step 1]
2. [Specific step 2]
3. [Specific step 3]

Constraints:
- Only [read/modify] files in [SCOPE]
- Do NOT [out of scope actions]

Return:
- [Expected output format]
- [Key findings]
- [Confidence level if applicable]
```

## Anti-Patterns

| Anti-Pattern | Why It Fails | Correct Approach |
|-------------|--------------|-----------------|
| Sequential dispatch | Serializes work, wastes time | All agents in one message |
| Vague prompts | Agents wander, modify wrong files | Explicit scope + constraints |
| No scope overlap check | Merge conflicts, data corruption | Run scope overlap check first |
| Each agent creates branches | Scattered branches, cherry-pick chaos | One branch before dispatch |
| Summarizing without reading | Miss contradictions between agents | Read all results before synthesizing |
