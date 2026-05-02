---
name: explanation-traces
description: "Query and display structured decision traces from routing, agent selection, and skill execution."
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

Reads `session-trace.json` and presents routing decisions, agent selections, skill phase transitions, and gate verdicts as a human-readable timeline. Every answer comes from recorded trace data -- never from post-hoc reconstruction.

**Constraints:**
- Read-only: never modifies trace files or any other file
- Answers from recorded trace data only, not memory or inference
- If no trace file exists, explain how to enable tracing -- do not guess
- When user asks about a specific decision, filter to that decision
- Timestamps and evidence fields are authoritative; do not paraphrase away precision

---

## Instructions

### Phase 1: LOCATE

**Goal**: Find the session trace file.

**Step 1: Search for trace data**

Check in order:
1. `./session-trace.json`
2. `.claude/session-trace.json`
3. Glob fallback: `**/session-trace.json`

Read the first match found.

**Step 2: Handle missing trace**

If no `session-trace.json` exists:

```
No session-trace.json found.

To enable decision tracing, add a hook that writes routing decisions,
agent selections, skill phase transitions, and gate verdicts to
session-trace.json. See: skills/explanation-traces/references/trace-schema.md
for the expected JSON format.
```

Do not fabricate trace data or reconstruct decisions from conversation history.

**GATE**: Trace file found and readable.

### Phase 2: PARSE

**Goal**: Extract decision points and filter to the user's query.

**Step 1: Read the trace file**

Parse JSON, extract `decisions` array. Each entry:

| Field | Purpose |
|-------|---------|
| `timestamp` | When decided (ISO-8601) |
| `type` | `routing`, `agent-selection`, `skill-phase`, `gate-verdict` |
| `chosen` | What was selected |
| `alternatives` | What else was considered |
| `evidence` | Triggers matched, scores, signals |
| `context` | User request or phase that prompted the decision |

**Step 2: Filter by user query**

| User signal | Filter strategy |
|-------------|-----------------|
| Names an agent | `type: agent-selection` entries mentioning that agent |
| Names a skill | `type: skill-phase` or `type: routing` involving that skill |
| Says "routing" | `type: routing` entries |
| Says "gate" or "failed" | `type: gate-verdict` entries |
| No specific target | All decisions chronologically |

**Step 3: Validate data integrity**

Flag entries missing `evidence` or `alternatives` -- lower-confidence records with incomplete trace.

**GATE**: Decisions parsed and filtered. At least one entry available.

### Phase 3: PRESENT

**Goal**: Format trace data as human-readable decision timeline.

**Step 1: Build the timeline**

Per decision entry:

```
[TIMESTAMP] TYPE
  Decision: CHOSEN
  Alternatives: ALTERNATIVES (or "none recorded")
  Evidence: EVIDENCE
  Context: CONTEXT
```

Chronological order. Group consecutive same-type entries under shared headings if >5 total entries.

**Step 2: Highlight the answer**

If user asked "why did you choose X?", lead with the matching decision, then surrounding context:

```
You asked: "Why did you choose the code reviewer?"

Decision found at [TIMESTAMP]:
  Chosen: reviewer-code agent
  Alternatives: reviewer-domain, reviewer-perspectives
  Evidence: Request matched "review this function" trigger; code-specific
            keywords scored highest for reviewer-code
  Context: User said "review this function for bugs"

--- Full session timeline (3 decisions) ---
[... remaining entries ...]
```

**Step 3: Flag gaps honestly**

If the trace has gaps (missing timestamps, empty evidence, decisions without alternatives):

```
Note: [N] decision(s) have incomplete evidence fields. These entries
show WHAT was decided but not WHY.
```

Do not fill gaps with speculation.

**GATE**: Timeline presented. User's question answered from trace data.

---

## Examples

### Example 1: General session review
User: "Show me the decision log"
1. Locate session-trace.json
2. Parse all entries
3. Present full chronological timeline

### Example 2: Specific agent question
User: "Why did you pick that agent?"
1. Locate session-trace.json
2. Filter to agent-selection entries
3. Present most recent agent selection with evidence, then full timeline

### Example 3: Gate failure investigation
User: "Why did the gate fail?"
1. Locate session-trace.json
2. Filter to gate-verdict entries, especially failures
3. Present gate verdicts with pass/fail evidence

---

## Patterns to Detect and Fix

### Pattern 1: Evidence-Backed Trace Reading
**Wrong**: Reconstructing "why" from memory when trace file is missing.
**Right**: If no trace file, say so and explain how to enable tracing.

### Pattern 2: Preserve the Evidence Field
**Wrong**: "The router probably picked that agent because it seemed relevant."
**Right**: Quote the exact `evidence` field: "Trigger 'review this function' matched reviewer-code with score 0.92."

### Pattern 3: Format, Don't Dump
**Wrong**: Printing entire session-trace.json raw.
**Right**: Parse, filter to user's question, format as readable timeline.

### Pattern 4: Report Missing Trace Data
**Wrong**: "The alternatives field is empty, but it likely considered agents X and Y."
**Right**: "No alternatives were recorded for this decision."

### Pattern 5: Answer the Specific Question First
**Wrong**: Always showing full timeline regardless of question.
**Right**: Lead with the specific answer, then offer full context.

---

## Error Handling

### Error: No Trace File Found
**Cause**: Tracing hook not enabled or session-trace.json cleaned up.
**Solution**: Point to `skills/explanation-traces/references/trace-schema.md` for the schema. Do not reconstruct from conversation history.

### Error: Trace File Is Malformed JSON
**Cause**: Partial write, race condition, or corruption.
**Solution**: Report parse error with line/character offset. Extract valid entries before corruption point. Flag trace as incomplete.

### Error: No Decision Entries
**Cause**: Hook writes file but not recording decisions.
**Solution**: Report that trace exists but contains zero entries. Check whether `decisions` array is empty vs. missing.

### Error: Decision Not in Trace
**Cause**: Requested decision type was not recorded.
**Solution**: Show what IS in the trace. Suggest which hook event type would capture that decision.

---

## References

### Reference Loading Table

| Task type | Signals | Reference file |
|---|---|---|
| Hook authoring / writing traces | "write hook", "add tracing", "record decisions", "emit trace" | `references/trace-schema.md` |
| Diagnosing wrong trace data | "alternatives null", "evidence empty", "overwrite", "post-hoc", "vague" | `references/preferred-patterns.md` |
| Handling parse or read errors | "malformed", "missing field", "no decisions", "invalid type", "not found" | `references/error-handling.md` |
| Presenting filtered timeline | "why did you", "show trace", "decision log", "explain routing" | `references/trace-schema.md` |

### Reference Files
- `references/trace-schema.md`: JSON schema for session-trace.json with field descriptions and examples
- `references/preferred-patterns.md`: Anti-pattern catalog for trace producers and consumers with detection commands
- `references/error-handling.md`: Error-fix mappings for all error states
