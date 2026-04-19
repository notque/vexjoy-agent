---
name: do
description: "Route requests to agents with skills."
user-invocable: true
argument-hint: "<request>"
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
  - Skill
  - Task
routing:
  triggers:
    - "route task"
    - "classify request"
    - "which agent"
    - "delegate to skill"
    - "smart router"
  category: meta-tooling
---

# /do - Dispatch Router

`/do` dispatches user requests to the right worker agent. The parent's job is
exactly three steps:

1. Spawn one Haiku subagent to decide routing.
2. Receive a JSON decision back.
3. Dispatch the worker agent that Haiku returned.

The parent MUST NOT read the agent manifest, skill listings, routing tables,
or any agent or skill files. Haiku pays that context cost in its own window.

---

## Phase 1: GATE

If the user named an exact file path and only wants it read, read it and
return. Everything else proceeds to Phase 2.

Do not dispatch any worker agent before Phase 2 completes. Phase 2 chooses
the worker.

---

## Phase 2: ROUTE (one Haiku call)

Read the self-contained routing prompt, substitute the user's request, and
dispatch a single Haiku subagent.

1. Read the file `~/.claude/skills/do/haiku-router-prompt.md`.
2. Replace every occurrence of the literal token `{{USER_REQUEST}}` with the
   user's raw, unmodified request.
3. Call the `Agent` tool with:
   - `subagent_type`: `"general-purpose"`
   - `model`: `"haiku"`
   - `description`: `"Route /do request"`
   - `prompt`: the substituted prompt from step 2

Do not pre-load, summarize, or inspect any manifest, index, or skill file.
Do not add routing logic of your own to the prompt. The file is the prompt.

Haiku returns one JSON object. Parse it and treat its fields opaquely:

```json
{
  "agent": "<name-or-null>",
  "skill": "<name-or-null>",
  "complexity": "Simple|Medium|Complex",
  "subagent_type": "<value to pass to Agent>",
  "worker_prompt": "<prompt to send to the worker>",
  "routing_summary": "<one-line banner text>",
  "confidence": "high|medium|low",
  "reasoning": "<one sentence>"
}
```

If `agent` and `skill` are both null, tell the user the router found no clean
match, quote Haiku's `reasoning`, and ask them to narrow the request. Do not
invent a fallback.

---

## Phase 3: DISPATCH

1. Print the routing banner exactly as Haiku provided it:

   ```
   ===================================================================
    ROUTING: <routing_summary>
   ===================================================================
   ```

2. Dispatch the worker with the `Agent` tool:
   - `subagent_type`: value from Haiku's `subagent_type`
   - `description`: a 3 to 5 word summary of the user request
   - `prompt`: Haiku's `worker_prompt`, verbatim

   Do not append extra routing instructions. The `worker_prompt` is already
   self-contained. Haiku composed it to include every file the worker must
   read, every injection, and the closing completion directives.

If the request has multiple independent parts and Haiku returns an array of
decisions instead of a single object, dispatch items with sequential
dependencies in order and dispatch independent items in parallel (max 10).

---

## Phase 4: LEARN

Record the routing outcome. This is advisory. Skip silently if the script is
absent.

```bash
python3 ~/.claude/scripts/learning-db.py record \
    routing "<agent>:<skill>" \
    "routing-decision: agent=<agent> skill=<skill> complexity=<complexity>" \
    --category effectiveness
```

Use the values from Haiku's JSON verbatim. Do not add commentary.

---

## Files

- `~/.claude/skills/do/haiku-router-prompt.md`: self-contained routing prompt
  Haiku executes. All routing knowledge (agent names, skill names, triggers,
  routing tables) lives behind this file and is never loaded into the parent.
- `~/.claude/scripts/learning-db.py`: routing outcome recorder (optional).
