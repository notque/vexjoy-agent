# Explanation Traces — Anti-Patterns

Anti-patterns for both trace producers (hooks that write session-trace.json) and trace
consumers (this skill reading it). Organized by who makes the mistake.

---

## Producer Anti-Patterns (Hook Writers)

### AP-1: Post-Hoc Trace Writing

**Detection** (find hooks that append after execution rather than at decision time):
```bash
grep -rn "session-trace" hooks/ --include="*.py" | grep -v "import\|def "
rg 'session.trace' hooks/ -l
```

**What it looks like**:
```python
# Hook writes after the full agent run completes
def on_agent_stop(event):
    # WRONG: Writing what happened, not what was decided
    append_trace({
        "timestamp": datetime.utcnow().isoformat(),
        "type": "agent-selection",
        "chosen": event["agent"],
        "evidence": "agent completed successfully",  # outcome, not decision signal
        "alternatives": [],
    })
```

**Why wrong**: Post-hoc traces record outcomes, not decisions. The `evidence` becomes
"it worked" rather than the actual scoring signals. Callers using `explanation-traces`
get confident-sounding but meaningless answers.

**Fix**:
```python
# Write at classification time, before dispatch
def on_pre_tool_use(event):
    if event["tool"] == "Agent":
        chosen = event["input"]["subagent_type"]
        # Capture scoring from the router, not the outcome
        append_trace({
            "timestamp": datetime.utcnow().isoformat(),
            "type": "agent-selection",
            "chosen": chosen,
            "evidence": router_scores.get(chosen, "no score recorded"),
            "alternatives": list(router_scores.keys()),
        })
```

---

### AP-2: Null Alternatives

**Detection**:
```bash
grep -n '"alternatives": null' session-trace.json
rg '"alternatives":\s*null' session-trace.json
# Also catch missing alternatives field entirely:
python3 -c "
import json, sys
data = json.load(open('session-trace.json'))
bad = [i for i, d in enumerate(data['decisions']) if 'alternatives' not in d]
print(f'Missing alternatives field at indices: {bad}')
"
```

**What it looks like**:
```json
{
  "timestamp": "2026-04-01T10:00:00Z",
  "type": "routing",
  "chosen": "skill:roast",
  "alternatives": null,
  "evidence": "force_route triggered"
}
```

**Why wrong**: `null` is not the same as `[]`. The schema requires an array. When the
skill parses this, `alternatives` fails the `isinstance(v, list)` check. Consumers
cannot distinguish "no alternatives considered" from "alternatives field missing".

**Fix**: Use `[]` (empty array) when force_route was used and no alternatives were scored:
```json
{ "alternatives": [] }
```

---

### AP-3: Vague Evidence Strings

**Detection**:
```bash
grep -n '"evidence": ""' session-trace.json
rg '"evidence":\s*"(seemed right|best option|obvious choice|default)"' session-trace.json
# Check evidence length — short evidence is usually vague:
python3 -c "
import json
data = json.load(open('session-trace.json'))
short = [(i, d['evidence']) for i, d in enumerate(data['decisions'])
         if len(d.get('evidence', '')) < 20]
for i, ev in short: print(f'[{i}] Short evidence: {repr(ev)}')
"
```

**What it looks like**:
```json
{ "evidence": "seemed like the right choice" }
{ "evidence": "best match" }
{ "evidence": "" }
```

**Why wrong**: These evidence strings tell the user nothing. When they ask "why did you
pick that agent?", the skill must quote the evidence field verbatim. Vague evidence
produces vague explanations — the opposite of what the skill exists to provide.

**Fix**: Evidence must include at least one of: trigger string, score value, or matched signal:
```json
{ "evidence": "Trigger 'roast this' matched skill:roast force_route=true; no scoring run" }
{ "evidence": "reviewer-code scored 0.92 vs reviewer-domain 0.41; keywords: 'function', 'bug'" }
```

---

### AP-4: Overwriting Instead of Appending

**Detection**:
```bash
# Find hooks that open with 'w' mode (overwrite) instead of read-then-write:
grep -rn "open.*session-trace.*['\"]w['\"]" hooks/
rg 'open\([^)]*session.trace[^)]*["\']w["\']' hooks/ --type py
```

**What it looks like**:
```python
# WRONG: Overwrites entire file each time
with open("session-trace.json", "w") as f:
    json.dump({"decisions": [new_entry]}, f)
```

**Why wrong**: Every hook invocation destroys all prior decisions. A session that makes
10 routing decisions ends up with only the last one in the trace. The timeline is
unrecoverable.

**Fix**:
```python
import json, os

def append_trace(entry):
    path = "session-trace.json"
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
    else:
        data = {"session_id": generate_id(), "started_at": now_iso(), "decisions": []}
    data["decisions"].append(entry)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
```

---

### AP-5: Non-Monotonic Timestamps

**Detection**:
```bash
python3 -c "
import json
data = json.load(open('session-trace.json'))
ts = [d['timestamp'] for d in data['decisions']]
for i in range(1, len(ts)):
    if ts[i] < ts[i-1]:
        print(f'Non-monotonic: [{i-1}] {ts[i-1]} > [{i}] {ts[i]}')
"
```

**Why wrong**: If timestamps go backwards, the skill cannot sort decisions reliably.
Chronological presentation breaks. This often happens when a hook generates timestamps
at initialization rather than at emission time.

**Fix**: Always call `datetime.utcnow().isoformat() + "Z"` at the moment the entry is
created, not at hook startup.

---

## Consumer Anti-Patterns (Skill Behavior)

### AP-6: Reconstructing Decisions from Conversation History

**What it looks like** (incorrect skill behavior):
> "The trace file doesn't exist, but based on the conversation I can tell the router
> probably chose the golang agent because the user mentioned Go..."

**Why wrong**: This is exactly the rationalization the skill exists to prevent. If no
trace file exists, the correct answer is "no trace file found" — not an inference from
memory or conversation history.

**Correct behavior**: Report the missing file. Explain how to enable tracing. Do not fill
the gap with inference. See SKILL.md Phase 1 Step 2 for the exact message to produce.

---

### AP-7: Dumping Raw JSON Without Filtering

**What it looks like**: Printing the entire `session-trace.json` content when the user
asks a specific question like "why did you pick the code reviewer?".

**Why wrong**: Unfiltered JSON forces the user to manually scan for the relevant entry.
A 20-decision trace printed as raw JSON is noise, not an explanation.

**Correct behavior**: Filter to the specific decision type, lead with the answer to the
user's question, then offer the full timeline as supplementary context. See SKILL.md
Phase 2 Step 2 for the filter strategy table.

---

### AP-8: Treating Incomplete Traces as Complete

**What it looks like**: Presenting a timeline without flagging that several decisions have
empty `evidence` fields.

**Why wrong**: The user assumes the explanation is authoritative. Missing evidence means
the "why" for those decisions is unknown — presenting them without a caveat creates false
confidence in the explanation.

**Correct behavior**: Flag incomplete entries explicitly (SKILL.md Phase 3 Step 3).
Report count of entries with missing/empty evidence. Never fill gaps silently.

---

## Quick Detection Cheatsheet

| Anti-pattern | Detection command |
|---|---|
| Empty evidence | `rg '"evidence":\s*""' session-trace.json` |
| Null alternatives | `rg '"alternatives":\s*null' session-trace.json` |
| Overwrite hooks | `grep -rn 'open.*session-trace.*"w"' hooks/` |
| Non-monotonic timestamps | see AP-5 detection block |
| Missing required fields | `python3 -c "import json; fields={'timestamp','type','chosen','alternatives','evidence','context'}; [print(i, fields-set(d)) for i,d in enumerate(json.load(open('session-trace.json'))['decisions']) if fields-set(d)]"` |
