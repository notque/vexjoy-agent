---
name: retro
description: |
  Interact with the retro knowledge system: audit L2 files, list accumulated
  knowledge, fix hygiene issues, check injection health, and graduate mature
  knowledge into specific agents/skills. Thin wrapper around feature-state.py
  retro subcommands. Use when user says "retro", "retro audit", "retro list",
  "retro fix", "retro status", "retro graduate", "check knowledge",
  "what have we learned", "knowledge health", "graduate knowledge".
version: 1.0.0
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Agent
  - Grep
  - Glob
---

# Retro Knowledge Skill

## Operator Context

This skill wraps the retro subsystem of `scripts/feature-state.py` and the `retro/` knowledge store into a user-friendly interface. It provides read, audit, and fix operations for accumulated cross-feature knowledge.

### Hardcoded Behaviors (Always Apply)
- **Script-First**: All state queries go through `python3 scripts/feature-state.py`; never read/parse retro files manually when a command exists
- **JSON Output**: Parse script JSON output for structured reporting; use `--human` flag only for pass-through display
- **Fix Requires Confirmation**: Before modifying L2 files (in `fix` subcommand), show what will change and confirm with user

### Default Behaviors (ON unless disabled)
- **Formatted Output**: Present results in readable tables/sections, not raw JSON
- **Actionable Suggestions**: When audit finds issues, suggest the fix command

### Optional Behaviors (OFF unless enabled)
- **Auto-Fix**: Apply fixes without confirmation (only if user passes `--auto`)

## What This Skill CAN Do
- List all accumulated L1 and L2 knowledge
- Audit L2 files for hygiene issues (missing tags, languages, empty files)
- Fix common L2 hygiene issues (add missing metadata fields)
- Show injection health (what gets loaded, what's gated out)
- Graduate mature L2 observations into specific agents/skills (AI-evaluated)

## What This Skill CANNOT Do
- Record new retro observations (use `retro-record` during feature work or `/do` learning phase)
- Promote observations (use `retro-promote` during feature work)
- Modify L1 summary (generated automatically by `complete` command)
- Graduate without user confirmation (proposals always require approval)

---

## Instructions

Parse the user's argument to determine the subcommand. Default to `status` if no argument given.

| Argument | Subcommand |
|----------|------------|
| (none), status | **status** |
| audit | **audit** |
| list | **list** |
| fix | **fix** |
| graduate | **graduate** |

### Subcommand: status

Show a summary of the retro knowledge system health.

**Step 1**: Count L2 files and read L1 summary.

```bash
ls retro/L2/ 2>/dev/null | wc -l
wc -l < retro/L1.md 2>/dev/null
```

**Step 2**: Run audit to get issue count.

```bash
python3 scripts/feature-state.py retro-audit
```

**Step 3**: Check hook is registered.

```bash
grep -l "retro-knowledge-injector" hooks/*.py 2>/dev/null
```

**Step 4**: Present status report.

```
RETRO KNOWLEDGE STATUS
======================

Knowledge Store:
  L1 summary: [N] lines
  L2 files:   [N] topic files

Injection:
  Hook: [installed/missing]
  Gating: language-aware (matches project file extensions)

Health:
  [N] L2 files with issues (run /retro audit for details)
  [N] cross-file duplicates
```

### Subcommand: audit

Run the retro audit and present findings.

**Step 1**: Run audit.

```bash
python3 scripts/feature-state.py retro-audit
```

**Step 2**: Parse JSON output. For each file with issues, report:

```
RETRO AUDIT
===========

[filename.md]
  [severity] [issue type] - [hint]

Summary: [N] files checked, [N] with issues, [N] cross-file duplicates

Fix: run /retro fix to resolve issues
```

### Subcommand: list

Display all accumulated knowledge.

**Step 1**: Read and display L1 summary.

```bash
cat retro/L1.md
```

**Step 2**: List L2 files with their tags and observation counts.

For each file in `retro/L2/`:
- Read the file
- Extract `**Tags**:` and `**Languages**:` lines
- Count `###` headings (individual learnings)
- Count `[Nx]` markers (repeated observations)

**Step 3**: Present:

```
RETRO KNOWLEDGE
===============

## L1 Summary (always injected)
[L1 content]

## L2 Topic Files (injected when tags match)

[filename.md] - [N] learnings
  Tags: [tags]
  Languages: [languages]
  High-observation: [any entries with 3x+]
```

### Subcommand: fix

Fix common L2 hygiene issues found by audit.

**Step 1**: Run audit to identify issues.

```bash
python3 scripts/feature-state.py retro-audit
```

**Step 2**: For each fixable issue, show the proposed change and confirm with user before applying:

| Issue Type | Fix |
|------------|-----|
| `missing_tags` | Read file content, infer tags from `###` headings, add `**Tags**:` line after first heading |
| `missing_languages` | Infer language from tags (go, python, typescript, etc.), add `**Languages**:` line after Tags |
| `no_learnings` | Report as unfixable — file is empty and should be manually populated or deleted |

**Step 3**: Apply fixes using the Edit tool. Report what was changed.

```
RETRO FIX
=========

[filename.md]
  + Added **Tags**: [inferred tags]
  + Added **Languages**: [inferred language]

[N] fixes applied across [N] files
```

### Subcommand: graduate

Evaluate mature L2 observations and embed them into the specific agents/skills where they belong. Uses value-based scoring (actionability + specificity + target-clarity + confidence, scored 0-10, threshold 6) to identify candidates. This is the knowledge graduation pipeline — observations become prescriptive rules in the exact tool that uses them.

**This is AI work, not mechanical.** Graduation requires judgment about:
- Whether an observation is truly prescriptive (rule) vs. still situational (observation)
- Which section of the target agent/skill to embed it in
- How to phrase it as an instruction rather than an observation

**Step 1**: Run the deterministic pre-filter to identify candidates.

```bash
python3 scripts/retro-graduate.py scan
```

Parse the JSON output. If `candidates` is empty, report:
```
RETRO GRADUATE
==============
No candidates ready for graduation.

Criteria: Score >= 6 (actionability + specificity + target-clarity + confidence)
Current L2 files: [N]

Knowledge graduates based on value, not frequency. Single high-value
observations can graduate immediately if they score high enough on
actionability and specificity.
```

If candidates exist, proceed to Step 2.

**Step 2**: For each candidate, evaluate graduation readiness.

Read the candidate's full L2 entry AND the target agent/skill files. The `matching_agents` field from `scan` output tells you which agents declared this topic in their `retro-topics` frontmatter. Display the candidate's `score` and `score_breakdown` (actionability, specificity, target-clarity, confidence) when presenting each candidate.

For each candidate, evaluate:

| Question | Pass | Fail |
|----------|------|------|
| Is this specific and actionable? | "sync.Mutex for multi-field state machines" | "Use proper concurrency" |
| Is this universally applicable to the domain? | Applies to all Go state machines | Only applied in one specific feature |
| Would it be wrong as a prescriptive rule? | Safe as a default recommendation | Has important exceptions not captured |
| Does the target agent/skill already contain this? | Not present | Already has equivalent guidance |

If any question fails, skip the candidate with explanation.

**Step 3**: For passing candidates, draft the modification.

Read the target agent's markdown file. Identify the best insertion point:
- If the agent has a `## Key Patterns` or similar section, add there
- If the agent has a `## Hardcoded Behaviors` section, add as a new behavior
- Otherwise, add a new `## Graduated Knowledge` section before the closing content

Draft the modification as:
```
### [Observation Key]
[Rewritten as prescriptive instruction, not observation]
*Graduated from retro/L2/[topic].md — [N] observations, HIGH confidence*
```

**Step 4**: Present all proposals to the user for approval.

```
RETRO GRADUATION PROPOSALS
==========================

[N] candidates evaluated, [M] ready for graduation:

1. [key] → agents/[agent-name].md
   FROM: "[original L2 observation]"
   TO:   "[rewritten as agent instruction]"
   Section: [where in the agent file]

2. ...

[K] candidates not ready:
- [key]: [reason - e.g., "too situational", "already present", "has exceptions"]

Approve? (y/n/pick numbers)
```

**Step 5**: For approved proposals, apply the modifications.

Use the Edit tool to insert the graduated content into each target agent/skill file.

After embedding, mark the L2 entry as graduated using the script:

```bash
python3 scripts/retro-graduate.py mark TOPIC "KEY" "target1, target2"
```

This appends `[GRADUATED → target]` to the heading, prevents the entry from being re-graduated, and signals the retro-knowledge-injector hook to skip it (already embedded in the agent).

**Step 6**: Regenerate L1 to reflect graduated entries.

```bash
python3 scripts/feature-state.py retro-audit
```

Report:
```
GRADUATED:
  [key] → agents/[agent].md (section: [section])

L2 entries marked. These will no longer be injected via the hook
since they are now part of the agent's permanent knowledge.
```

---

## Examples

### Example 1: Quick health check
User says: "/retro"
Actions: Run status subcommand, show knowledge store size, injection health, issue count.

### Example 2: Audit hygiene
User says: "/retro audit"
Actions: Run `retro-audit`, format issues by file with severity and hints.

### Example 3: See what we know
User says: "/retro list"
Actions: Display L1 summary and L2 inventory with tags and observation counts.

### Example 4: Fix issues
User says: "/retro fix"
Actions: Run audit, show proposed fixes, confirm with user, apply edits.

### Example 5: Graduate mature knowledge
User says: "/retro graduate"
Actions: Run `retro-candidates`, evaluate each against graduation criteria, draft modifications to target agents/skills, present proposals, apply approved changes, mark L2 entries as graduated.

---

## Error Handling

### Error: "No retro/ directory"
Cause: Knowledge store not initialized yet
Solution: Report that no knowledge has been accumulated yet. Suggest running a feature lifecycle to generate retro data.

### Error: "feature-state.py not found"
Cause: Script missing or wrong working directory
Solution: Check that we're in the agents repo root. Report the missing script path.

### Error: "Empty L1.md"
Cause: No features have been completed yet
Solution: Report that L1 is empty — knowledge accumulates when features complete via `feature-state.py complete`.

---

## Anti-Patterns

### Anti-Pattern 1: Manually Parsing Retro Files Instead of Using Script
**What it looks like**: Reading and parsing `.feature/meta/` files directly
**Why wrong**: The script handles observation counting, promotion logic, and archival
**Do instead**: Use `feature-state.py` subcommands for all retro operations

### Anti-Pattern 2: Auto-Fixing Without Showing Changes
**What it looks like**: Silently editing L2 files in fix subcommand
**Why wrong**: User should see what's being changed in their knowledge store
**Do instead**: Show proposed changes, confirm, then apply

### Anti-Pattern 3: Graduating Too Early
**What it looks like**: Embedding an observation that scores below 6 on the value-based model
**Why wrong**: Observations are probabilistic; agent rules are prescriptive. Premature graduation creates wrong rules.
**Do instead**: Wait for score >= 6 on the value-based scoring model. Single high-value observations can graduate immediately if they score high enough on actionability and specificity. Let the `retro-graduate.py scan` filter enforce this.

### Anti-Pattern 4: Graduating Generic Advice
**What it looks like**: Graduating "use proper error handling" into the Go agent
**Why wrong**: Generic advice adds noise, not value. Agents already know general patterns.
**Do instead**: Only graduate specific, actionable findings that encode something non-obvious.
