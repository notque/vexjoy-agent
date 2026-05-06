# session-trace.json Schema

This document defines the JSON schema for `session-trace.json`, the structured decision log consumed by the `explanation-traces` skill. Hooks that record decisions must produce output conforming to this schema.

---

## Top-Level Structure

```json
{
  "session_id": "string",
  "started_at": "ISO-8601",
  "decisions": []
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | yes | Unique identifier for the session. Use UUID or timestamp-based ID. |
| `started_at` | string | yes | ISO-8601 timestamp of session start. |
| `decisions` | array | yes | Ordered list of decision entries, chronological. |

---

## Decision Entry Schema

Each entry in the `decisions` array represents a single decision point captured at the moment it was made.

```json
{
  "timestamp": "ISO-8601",
  "type": "routing|agent-selection|skill-phase|gate-verdict",
  "chosen": "string",
  "alternatives": ["string"],
  "evidence": "string",
  "context": "string"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `timestamp` | string | yes | ISO-8601 timestamp of when the decision was made. Must be captured AT decision time, not reconstructed. |
| `type` | string | yes | One of four decision categories (see below). |
| `chosen` | string | yes | What was selected -- the agent name, skill name, phase, or verdict. |
| `alternatives` | array of strings | yes | What else was considered. Empty array `[]` if no alternatives existed (e.g., forced route). |
| `evidence` | string | yes | The triggers matched, scores computed, or signals observed that drove this choice. This is the most important field -- it answers "why". |
| `context` | string | yes | The user request, phase name, or condition that prompted this decision point. |

---

## Decision Types

### `routing`
A request was classified and routed to a skill or execution tier.

**Example:**
```json
{
  "timestamp": "2026-04-01T14:23:01Z",
  "type": "routing",
  "chosen": "skill:roast",
  "alternatives": ["skill:parallel-code-review", "skill:systematic-code-review"],
  "evidence": "Trigger 'roast this' matched with force_route=true; no scoring needed",
  "context": "User said: 'Roast this repo'"
}
```

### `agent-selection`
A specific agent was selected to execute part of a task.

**Example:**
```json
{
  "timestamp": "2026-04-01T14:23:02Z",
  "type": "agent-selection",
  "chosen": "reviewer-code",
  "alternatives": ["reviewer-domain", "reviewer-perspectives"],
  "evidence": "Request contains code-specific keywords ('function', 'bug'); reviewer-code agent scores 0.92 vs domain 0.41 vs perspectives 0.38",
  "context": "Dispatching review agent for: 'review this function for bugs'"
}
```

### `skill-phase`
A skill transitioned from one phase to the next.

**Example:**
```json
{
  "timestamp": "2026-04-01T14:23:15Z",
  "type": "skill-phase",
  "chosen": "Phase 3: SPAWN ROASTER AGENTS",
  "alternatives": [],
  "evidence": "Phase 2 GATE passed: target identified (README.md), 12 context files gathered",
  "context": "roast skill advancing from GATHER CONTEXT to SPAWN ROASTER AGENTS"
}
```

### `gate-verdict`
A quality gate was evaluated and produced a pass or fail.

**Example:**
```json
{
  "timestamp": "2026-04-01T14:24:30Z",
  "type": "gate-verdict",
  "chosen": "PASS",
  "alternatives": ["FAIL"],
  "evidence": "All 5 agents returned tagged claims; claim count: Senior=7, Pedant=4, Newcomer=5, Contrarian=3, Builder=6",
  "context": "Phase 3 GATE: All 5 agents complete with tagged claims"
}
```

---

## Writing Traces from Hooks

Hooks that emit trace data should follow these rules:

1. **Capture at decision time.** Write the decision entry at the moment the decision is made, not after execution completes. Post-hoc entries are less trustworthy because they can be influenced by outcome knowledge.

2. **Append, do not overwrite.** Read the existing `session-trace.json`, append to the `decisions` array, and write back. If the file does not exist, create it with the top-level structure and the first entry.

3. **Evidence must be specific.** "Seemed like the right choice" is not evidence. Record the actual triggers, scores, or conditions: "Trigger 'review this function' matched reviewer-code; keyword score 0.92."

4. **Alternatives must be honest.** If a force_route was used and no alternatives were considered, set `alternatives` to `[]`. Do not fabricate alternatives that were never evaluated.

5. **File location.** Write to `session-trace.json` in the project root (same directory as `task_plan.md` and `STATE.md`). Hooks can also write to `.claude/session-trace.json` if project root is not writable.

---

## Validation Checklist

A well-formed trace file satisfies all of these:

- [ ] `session_id` is unique per session
- [ ] `started_at` is valid ISO-8601
- [ ] Every decision has all 6 required fields
- [ ] `type` is one of the 4 allowed values
- [ ] `timestamp` values are monotonically increasing
- [ ] `evidence` fields contain specific signals, not vague descriptions
- [ ] `alternatives` is `[]` when no alternatives existed, not omitted
