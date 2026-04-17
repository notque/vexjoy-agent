# Explanation Traces — Error Handling

Error-fix mappings for every error state the skill encounters when reading and parsing
`session-trace.json`. Each entry includes: what the error looks like, root cause, and
exact response to give the user.

---

## Error: No Trace File Found

**Trigger**: None of the search paths (`./session-trace.json`, `.claude/session-trace.json`,
`**/session-trace.json`) return a readable file.

**Root causes**:
| Cause | How to identify |
|---|---|
| Tracing hook never installed | `ls hooks/ | grep trace` returns nothing |
| Hook installed but never fired | Hook file exists, but session-trace.json absent |
| File written to wrong path | `find . -name "session-trace*" 2>/dev/null` finds it elsewhere |
| File cleaned up between sessions | `git status` shows it was deleted or .gitignored |

**Detection** (run to diagnose which cause applies):
```bash
# Check if any hook references session-trace:
grep -rn "session-trace" hooks/ --include="*.py"
# Find any trace file anywhere in the project:
find . -name "session-trace*" 2>/dev/null
# Check gitignore:
grep "session-trace" .gitignore
```

**Response to user**:
```
No session-trace.json found.

To enable decision tracing, add a hook that writes routing decisions,
agent selections, skill phase transitions, and gate verdicts to
session-trace.json. See: skills/explanation-traces/references/trace-schema.md
for the expected JSON format.
```

Do NOT guess at decisions from conversation history. If no file exists, there is nothing
to read.

---

## Error: Trace File Is Malformed JSON

**Trigger**: `json.JSONDecodeError` (Python) or `SyntaxError` when parsing.

**Common error messages**:
```
json.JSONDecodeError: Expecting ',' delimiter: line 47 column 3 (char 1203)
json.JSONDecodeError: Unterminated string starting at: line 23 (char 890)
json.JSONDecodeError: Extra data: line 2 column 1 (char 247)
```

**Root causes**:
| Cause | Symptom |
|---|---|
| Partial write (process killed mid-write) | File truncated; last `}` or `]` missing |
| Race condition (two hooks writing simultaneously) | Duplicate or interleaved JSON objects |
| Manual edit error | Trailing comma, unquoted key, etc. |

**Detection**:
```bash
# Validate JSON syntax:
python3 -m json.tool session-trace.json > /dev/null
# Or:
python3 -c "import json; json.load(open('session-trace.json'))"
# Find the exact byte offset of the error:
python3 -c "
import json
try:
    json.load(open('session-trace.json'))
except json.JSONDecodeError as e:
    print(f'Error at line {e.lineno}, col {e.colno}, char {e.pos}: {e.msg}')
"
```

**Response to user**:
```
session-trace.json exists but cannot be parsed.

Parse error: [include exact error message and line/char offset]

Attempting to recover entries before the corruption point...
[show any valid decisions found before the error position]

The trace is incomplete. Decisions after char [N] are unavailable.
```

**Recovery attempt**: Try to extract the valid prefix by parsing the file byte-by-byte
up to the error position. Report what was recovered vs. what was lost.

---

## Error: Trace File Has No Decision Entries

**Trigger**: File parses successfully, but `data["decisions"]` is empty (`[]`) or the
`decisions` key is absent entirely.

**Distinguish the two cases**:
```python
data = json.load(open("session-trace.json"))
if "decisions" not in data:
    # Key absent — hook is writing wrong schema
    print("decisions key missing from trace file")
elif len(data["decisions"]) == 0:
    # Key present but empty — hook fired but recorded nothing
    print("decisions array is present but empty")
```

**Detection**:
```bash
python3 -c "
import json
data = json.load(open('session-trace.json'))
print('decisions key present:', 'decisions' in data)
print('decision count:', len(data.get('decisions', [])))
print('top-level keys:', list(data.keys()))
"
```

**Root causes**:
| Symptom | Likely cause |
|---|---|
| `decisions` key missing | Hook writes different schema (e.g., only metadata) |
| `decisions` is `[]` | Hook fires but the decision-recording code path never runs |
| File is `{}` | Hook creates the file but never populates it |

**Response to user**:
```
session-trace.json exists [and the decisions array is present] but contains zero
decision entries.

This means the hook is running but no decisions were recorded. Check:
1. Does the hook emit entries on PreToolUse (agent dispatch) or only on PostToolUse?
2. Is the decision-writing code path gated behind a condition that never fires?

See: skills/explanation-traces/references/trace-schema.md for the expected
schema and hook writing rules.
```

---

## Error: Decision Entry Missing Required Fields

**Trigger**: An entry in `decisions` is missing one or more of the six required fields:
`timestamp`, `type`, `chosen`, `alternatives`, `evidence`, `context`.

**Detection**:
```bash
python3 -c "
import json
REQUIRED = {'timestamp', 'type', 'chosen', 'alternatives', 'evidence', 'context'}
data = json.load(open('session-trace.json'))
for i, d in enumerate(data['decisions']):
    missing = REQUIRED - set(d.keys())
    if missing:
        print(f'Entry [{i}]: missing fields: {missing}')
"
```

**Response to user**:
```
[N] decision entries have incomplete records:

Entry [2]: missing fields: evidence, alternatives
Entry [7]: missing fields: context

These entries show WHAT was decided but not WHY. The recording hook did not
capture full context at decision time. Presenting available fields only.
```

Flag each incomplete entry in the timeline output. Do not invent values for missing fields.

---

## Error: Invalid `type` Field Value

**Trigger**: An entry's `type` field contains a value other than `routing`, `agent-selection`,
`skill-phase`, or `gate-verdict`.

**Detection**:
```bash
python3 -c "
import json
VALID = {'routing', 'agent-selection', 'skill-phase', 'gate-verdict'}
data = json.load(open('session-trace.json'))
for i, d in enumerate(data['decisions']):
    t = d.get('type', '')
    if t not in VALID:
        print(f'Entry [{i}]: invalid type {repr(t)} (valid: {VALID})')
"
```

**Common invalid values**: `"agent_selection"` (underscore instead of hyphen),
`"Agent"` (capitalized), `"decision"` (wrong category name).

**Response to user**: Include the entry in the timeline but label it `[UNKNOWN TYPE]`.
Do not silently drop entries with invalid types.

---

## Error: User Asks About a Decision Not in the Trace

**Trigger**: User asks "why did you choose X?" but no entry in `decisions` matches X
in the `chosen` or `alternatives` fields.

**Detection logic**:
```python
query = "golang-general-engineer"
matches = [d for d in decisions
           if query in d.get("chosen", "") or query in d.get("alternatives", [])]
if not matches:
    # Decision was not recorded
```

**Response to user**:
```
No trace entry found for [X].

The session trace has [N] decisions recorded:
  - [list types and chosen values from the trace]

The decision you're asking about was not captured. To record [X] decisions,
the hook needs to emit a [routing|agent-selection|skill-phase|gate-verdict]
entry when [X] is selected.
```

Show what IS in the trace. Do not speculate about why X was chosen when it has no
trace entry.

---

## Error-Fix Summary Table

| Error | Root cause | User message keyword | Fix |
|---|---|---|---|
| No file found | Hook not installed or wrong path | "No session-trace.json found" | Install tracing hook; see trace-schema.md |
| Malformed JSON | Partial write or race condition | "cannot be parsed" | Show error offset; attempt recovery of pre-error entries |
| `decisions` key missing | Wrong schema from hook | "decisions key missing" | Fix hook to use correct top-level structure |
| `decisions` is empty | Hook fires but records nothing | "zero decision entries" | Check hook's decision-recording code path |
| Missing required fields | Incomplete hook implementation | "incomplete records" | Flag affected entries; never invent missing values |
| Invalid `type` value | Typo or schema drift in hook | `[UNKNOWN TYPE]` label | Label in output; do not drop |
| Decision not in trace | Hook doesn't record that decision type | "not captured" | Show what is in trace; explain what hook change would fix it |
