---
name: explanation-traces
description: "Query and display structured decision traces from routing, agent selection, and skill execution."
version: 1.0.0
user-invocable: true
argument-hint: "<optional: specific decision to explain>"
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
routing:
  triggers:
    - "why did you"
    - "explain routing"
    - "show trace"
    - "decision log"
    - "why that agent"
    - "explain decision"
    - "show decisions"
    - "trace log"
  force_route: true
  pairs_with: []
  complexity: Simple
  category: analysis
---

# Explanation Traces: Structured Decision Query

## Overview

This skill reads the current session's `session-trace.json` and presents routing decisions, agent selections, skill phase transitions, and gate verdicts as a human-readable timeline. Every answer comes from what the trace actually recorded at decision time -- never from post-hoc reconstruction or rationalization.

**Key constraints baked into the workflow:**
- Read-only: this skill never modifies trace files or any other file
- Answers must come from recorded trace data, not from memory or inference about what "probably happened"
- If no trace file exists, explain how to enable tracing rather than guessing at decisions
- When the user asks about a specific decision, filter to that decision -- do not dump the full log
- Timestamps and evidence fields are authoritative; do not paraphrase away precision

---

## Instructions

### Phase 1: LOCATE

**Goal**: Find the session trace file.

**Step 1: Search for trace data**

Check for `session-trace.json` in these locations, in order:

1. Current working directory: `./session-trace.json`
2. `.claude/` directory: `.claude/session-trace.json`
3. Glob fallback: `**/session-trace.json` (in case a custom path was used)

Use the Read tool on the first match found.

**Step 2: Handle missing trace**

If no `session-trace.json` exists anywhere, stop and inform the user:

```
No session-trace.json found.

To enable decision tracing, add a hook that writes routing decisions,
agent selections, skill phase transitions, and gate verdicts to
session-trace.json. See: skills/explanation-traces/references/trace-schema.md
for the expected JSON format.
```

Do not fabricate trace data. Do not attempt to reconstruct decisions from memory or conversation history. The entire value of this skill is that it reads what was actually recorded -- without a trace file, there is nothing to read.

**GATE**: Trace file found and readable. Proceed only when gate passes.

### Phase 2: PARSE

**Goal**: Extract decision points from the trace and filter to the user's query.

**Step 1: Read the trace file**

Parse the JSON from `session-trace.json`. Extract the `decisions` array. Each entry contains:

| Field | Purpose |
|-------|---------|
| `timestamp` | When the decision was made (ISO-8601) |
| `type` | Category: `routing`, `agent-selection`, `skill-phase`, `gate-verdict` |
| `chosen` | What was selected |
| `alternatives` | What else was considered |
| `evidence` | Triggers matched, scores, signals that drove the choice |
| `context` | The user request or phase that prompted the decision |

**Step 2: Filter if user asked about a specific decision**

If the user's query targets a specific decision (e.g., "why did you pick the code reviewer?", "why that agent?"), filter the decisions array:

| User signal | Filter strategy |
|-------------|-----------------|
| Names an agent | Filter to `type: agent-selection` entries mentioning that agent in `chosen` or `alternatives` |
| Names a skill | Filter to `type: skill-phase` or `type: routing` entries involving that skill |
| Says "routing" | Filter to `type: routing` entries |
| Says "gate" or "failed" | Filter to `type: gate-verdict` entries |
| No specific target | Return all decisions in chronological order |

**Step 3: Validate data integrity**

Check that each decision entry has all required fields. Flag any entries missing `evidence` or `alternatives` -- these are lower-confidence records where the trace was incomplete.

**GATE**: Decisions parsed and filtered. At least one decision entry available. Proceed only when gate passes.

### Phase 3: PRESENT

**Goal**: Format trace data as a human-readable decision timeline.

**Step 1: Build the timeline**

For each decision entry, format as:

```
[TIMESTAMP] TYPE
  Decision: CHOSEN
  Alternatives: ALTERNATIVES (or "none recorded")
  Evidence: EVIDENCE
  Context: CONTEXT
```

Order chronologically. Group consecutive entries of the same type under a shared heading if there are more than 5 entries total, to prevent wall-of-text for long sessions.

**Step 2: Highlight the answer to the user's question**

If the user asked "why did you choose X?", lead with the specific decision entry that answers their question, then show surrounding context:

```
You asked: "Why did you choose the code reviewer?"

Decision found at [TIMESTAMP]:
  Chosen: reviewer-code agent
  Alternatives: reviewer-domain, reviewer-perspectives
  Evidence: Request matched "review this function" trigger; code-specific
            keywords ("function", "bug") scored highest for reviewer-code
  Context: User said "review this function for bugs"

--- Full session timeline (3 decisions) ---
[... remaining entries ...]
```

**Step 3: Flag gaps honestly**

If the trace has gaps (missing timestamps, empty evidence fields, decisions without alternatives), say so explicitly:

```
Note: [N] decision(s) have incomplete evidence fields. These entries
show WHAT was decided but not WHY -- the recording hook may not have
captured full context for these decisions.
```

Do not fill gaps with speculation. Incomplete data presented honestly is more useful than complete-looking data that includes fabrication.

**GATE**: Timeline presented. User's question answered from trace data. Done.

---

## Examples

### Example 1: General session review
User says: "Show me the decision log"
```
skill: explanation-traces
```
Actions:
1. Locate session-trace.json (Phase 1)
2. Parse all decision entries (Phase 2)
3. Present full chronological timeline (Phase 3)
Result: Complete session decision history with evidence for each choice

### Example 2: Specific agent question
User says: "Why did you pick that agent?"
```
skill: explanation-traces "why that agent?"
```
Actions:
1. Locate session-trace.json (Phase 1)
2. Filter to agent-selection entries (Phase 2)
3. Present the most recent agent selection with evidence, then full timeline for context (Phase 3)
Result: Evidence-backed explanation of agent choice, not a post-hoc rationalization

### Example 3: Gate failure investigation
User says: "Why did the gate fail?"
```
skill: explanation-traces "gate failure"
```
Actions:
1. Locate session-trace.json (Phase 1)
2. Filter to gate-verdict entries, especially failures (Phase 2)
3. Present gate verdicts with the evidence that caused pass/fail (Phase 3)
Result: Specific gate failure reason from the trace, with what was expected vs. what was found

---

## Anti-Patterns

### Anti-Pattern 1: Post-Hoc Rationalization
**Wrong**: Reconstructing "why" from memory when the trace file is missing.
**Right**: If no trace file exists, say so and explain how to enable tracing. Never fabricate an explanation.

### Anti-Pattern 2: Paraphrasing Away Evidence
**Wrong**: "The router probably picked that agent because it seemed relevant."
**Right**: Quote the exact `evidence` field: "Trigger 'review this function' matched reviewer-code with score 0.92."

### Anti-Pattern 3: Dumping Raw JSON
**Wrong**: Printing the entire session-trace.json as-is.
**Right**: Parse, filter to the user's question, and format as a readable timeline with clear labels.

### Anti-Pattern 4: Filling Gaps with Inference
**Wrong**: "The alternatives field is empty, but it likely considered agents X and Y."
**Right**: "No alternatives were recorded for this decision -- the trace is incomplete at this point."

### Anti-Pattern 5: Ignoring the User's Specific Question
**Wrong**: Always showing the full timeline regardless of what the user asked.
**Right**: Lead with the specific answer, then offer full context as supplementary detail.

---

## Error Handling

### Error: No Trace File Found
**Cause**: Tracing hook not enabled or session-trace.json was cleaned up.
**Solution**: Inform user that no trace exists. Point to `skills/explanation-traces/references/trace-schema.md` for the schema a tracing hook should produce. Do not reconstruct decisions from conversation history.

### Error: Trace File Is Malformed JSON
**Cause**: Partial write, race condition, or manual corruption.
**Solution**: Report the parse error with the specific line/character offset. Attempt to extract any valid decision entries before the corruption point. Flag that the trace is incomplete.

### Error: Trace File Has No Decision Entries
**Cause**: Hook is writing the file but not recording decisions (e.g., only session metadata).
**Solution**: Report that the trace exists but contains zero decision entries. Check whether the `decisions` array is present but empty vs. missing entirely, and report which case applies.

### Error: User Asks About a Decision Not in the Trace
**Cause**: The specific decision the user is asking about was not recorded.
**Solution**: Show what IS in the trace and explain that the requested decision type was not captured. Suggest which hook event type would need to emit that decision.

---

## References

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/trace-schema.md`: JSON schema for session-trace.json with field descriptions and example entries
