# Explanation Traces — Patterns to Fix

Failure modes when reading `route-events.jsonl`, organized by kind: consumer
mistakes (this skill's behavior) and producer-side diagnostics (recognizing why
the recorded data is thin). The producers are fixed toolkit code
(`hooks/routing-decision-recorder.py`, `hooks/routing-outcome-finalizer.py`,
both writing through `hooks/lib/route_events.py`) — thin data usually means an
older log line or an uninstrumented marker, and the fix is correct
interpretation, never editing the log.

Path used throughout:

```bash
LOG="${CLAUDE_LEARNING_DIR:-$HOME/.claude/learning}/route-events.jsonl"
```

---

## Consumer Patterns to Fix (Skill Behavior)

### AP-1: Reconstructing Decisions from Conversation History

**What it looks like** (incorrect skill behavior):
> "The log doesn't exist, but based on the conversation I can tell the router
> probably chose the golang agent because the user mentioned Go..."

**Why wrong**: This is exactly the rationalization the skill exists to prevent.
The recorded event is the only evidence of what the router saw at decision time.

**Correct behavior**: Report the missing log, name the real path and producing
hook, and stop. See SKILL.md Phase 1 Step 2 for the exact message.

---

### AP-2: Joining Outcomes by File Adjacency

**What it looks like**: Pairing an OUTCOME event with the DECISION on the line
above it.

**Why wrong**: Appends from parallel sessions interleave at line granularity.
The outcome above may belong to a different session's dispatch. An outcome also
lands minutes-to-hours after its decision — anything can sit between them.

**Correct behavior**: Match on same `session` AND
`key == f"{agent}:{skill}"`. Verify join quality:

```bash
python3 - "$LOG" <<'EOF'
import json, sys
dec, out = {}, set()
for line in open(sys.argv[1]):
    if not line.strip():
        continue
    e = json.loads(line)
    if e["type"] == "decision":
        dec[(e["session"], f"{e['agent']}:{e['skill']}")] = dec.get((e["session"], f"{e['agent']}:{e['skill']}"), 0) + 1
    else:
        out.add((e["session"], e["key"]))
matched = sum(1 for k in dec if k in out)
print(f"decision keys: {len(dec)}, with matched outcome: {matched}")
EOF
```

---

### AP-3: Conflating the Three Health States

**What it looks like**: Rendering every `null` `health_at_decision` as
"no health data".

**Why wrong**: `null` carries two different facts, split by
`gate_inputs_present`:
- `true` → instrumented, but the pick had no weight row (a new pair — valid, expected)
- `false`/absent → legacy marker, health never read

Collapsing them hides whether the health gate ran.

**Correct behavior**: Render the three states distinctly (SKILL.md Phase 3
Step 1 table). Count each state:

```bash
python3 - "$LOG" <<'EOF'
import json, sys, collections
c = collections.Counter()
for line in open(sys.argv[1]):
    if not line.strip():
        continue
    e = json.loads(line)
    if e["type"] != "decision":
        continue
    if e.get("health_at_decision") is not None:
        c["(a) numeric"] += 1
    elif e.get("gate_inputs_present"):
        c["(b) no weight row"] += 1
    else:
        c["(c) legacy/uninstrumented"] += 1
print(dict(c))
EOF
```

---

### AP-4: Treating Absent Additive Fields as Corruption

**What it looks like**: Flagging lines without `gate_inputs_present` or
`reason` as malformed.

**Why wrong**: The schema grew append-compatibly; old lines lack new fields by
design. `n`/`failure`/`action`/`alternates` are also `null` on any dispatch
where no numeric `health=` was read.

**Correct behavior**: Absent = "not recorded then". Flag the count in the
timeline note; keep the entries.

---

### AP-5: Sorting by File Order Instead of `ts`

**What it looks like**: Presenting events in the order they appear in the file.

**Why wrong**: Concurrent appends interleave; a slow hook can land its line
after a faster one with an earlier `ts`. File order approximates time but does
not guarantee it.

**Correct behavior**: Sort numerically on `ts` (a float, epoch seconds), then
group by session for display.

---

### AP-6: Dumping Raw JSONL Without Filtering

**What it looks like**: Printing raw log lines when the user asks a specific
question like "why did I get the governance agent?".

**Why wrong**: A 500-event log printed raw is noise, not an explanation.

**Correct behavior**: Filter to the matching decision, lead with the answer,
offer the session timeline as supplementary context. See SKILL.md Phase 2
Step 2 for the filter table.

---

### AP-7: Leaking `request_snippet` Outside the Session

**What it looks like**: Pasting `request_snippet` values into a PR body, issue,
or exported report while demonstrating the skill.

**Why wrong**: The snippet is the first 200 chars of a real user request —
private session data. Showing it to the session's own user is the skill's job;
sending it elsewhere is a leak.

**Correct behavior**: Inside the session, quote snippets freely. In anything
that leaves the session, report counts and field-presence statistics only.

---

## Producer-Side Diagnostics (Why the Data Is Thin)

### AP-8: Missing Decisions — the Dispatch Was Never Recorded

**Detection**:
```bash
ls ~/.claude/hooks/ | grep -E "routing-(decision-recorder|outcome-finalizer)"
```

**Interpretation**: The recorder appends a DECISION only for /do-routed
dispatches carrying a `[do-route]` marker; manual Agent calls and nested
fan-out are deliberately excluded (they would inflate route-health's
denominator). Recorder absent from `~/.claude/hooks/` means merged hook changes
were never synced — run `hooks/sync-to-user-claude.py`.

---

### AP-9: High Legacy Rate — Markers Without `health=`

**Detection**: Run the AP-3 state counter. A large "(c) legacy/uninstrumented"
share among *recent* decisions means current markers lack the `health=` token.

**Interpretation**: `gate_inputs_present` is the signal the decommission clock
reads. State (c) on old lines is history; state (c) on new lines means the
router's Step-1.5 wiring regressed — worth a report against
`skills/meta/do/SKILL.md` Phase 4, never a log edit.

---

## Quick Detection Cheatsheet

| Question | Command |
|---|---|
| Event counts by type | `python3 -c "import json,collections,os;p=os.path.expandvars('$LOG');print(collections.Counter(json.loads(l)['type'] for l in open(p) if l.strip()))"` |
| Malformed lines | see error-handling.md, "Malformed JSONL Line" |
| Health-state split | AP-3 counter above |
| Decisions with matched outcomes | AP-2 join checker above |
| Recorder synced | `ls ~/.claude/hooks/ \| grep routing-decision-recorder` |
