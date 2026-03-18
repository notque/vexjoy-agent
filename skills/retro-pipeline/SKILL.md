---
name: retro-pipeline
description: |
  5-phase retro orchestration pipeline: Walk, Merge, Gate, Apply, Report.
  Spawns context and meta walkers in parallel, merges outputs by hierarchy
  level, gates bottom-up (L3→L2→L1), applies approved changes, and reports
  with visual prefixes. Auto-invoked at phase checkpoints in feature lifecycle.
  Use for "run retro", "retro pipeline", "phase checkpoint retro", or when
  any feature-* skill reaches its CHECKPOINT phase.
version: 1.0.0
user-invocable: false
context: fork
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Agent
routing:
  triggers:
    - retro pipeline
    - run retro
    - phase checkpoint retro
    - retro checkpoint
  pairs_with:
    - feature-design
    - feature-plan
    - feature-implement
    - feature-validate
    - feature-release
  complexity: Medium
  category: process
---

# Retro Pipeline

## Purpose

Orchestrate the retro loop as a structured pipeline at phase checkpoints. This is the **write side** of the retro system — it extracts, classifies, promotes, and persists knowledge. The **read side** (auto-injection) is handled by the `retro-knowledge-injector` hook.

## Operator Context

### Hardcoded Behaviors (Always Apply)
- **Always Run**: Retro ALWAYS runs at checkpoints. Walkers handle empty phases gracefully.
- **Parallel Walkers**: Context and Meta walkers MUST run in parallel (not sequential)
- **Bottom-Up Gating**: Gate sequence is L3→L2→L1 (changes flow upward through hierarchy)
- **CLI for State**: All retro writes go through `python3 scripts/feature-state.py` — never write L2/L1 files directly
- **Artifacts at Every Phase**: Save walker outputs to files before merging
- **Visual Prefix Report**: Use structured prefixes (`>>`, `+`, `~`, `^`) for scannable output

### Default Behaviors (ON unless disabled)
- **Gate Modes**: Respect `CLAUDE_RETRO_GATE_*` env vars (default: all auto)
- **Observation Clustering**: Same-key records increment observation count, not duplicate
- **Frequency-Gated Auto-Promotion**: 3 obs → MEDIUM, 6 obs → HIGH (handled by CLI)
- **Audit on Report**: Run `retro-audit` as part of the report phase

### Optional Behaviors (OFF unless enabled)
- **Human Gates**: Set `CLAUDE_RETRO_GATE_L3_RECORDS=human` (or L2/L1) to require approval
- **Verbose Report**: Include full walker output in report (default: summary only)

## What This Skill CAN Do
- Spawn both walker agents in parallel and merge their outputs
- Gate retro changes bottom-up (L3 records → L2 context → L1 summaries)
- Apply approved changes via feature-state.py CLI
- Produce a visual report with prefixes showing what changed
- Run retro-audit to detect quality issues

## What This Skill CANNOT Do
- Modify source code (retro only updates knowledge files)
- Override gate modes set by env vars
- Promote LOW confidence findings directly to L1 (must go through frequency gate)
- Skip walkers — both always run (they handle empty phases gracefully)

---

## Instructions

### Input

This pipeline requires:
- `FEATURE`: Feature name (slugified)
- `PHASE`: Current phase (design, plan, implement, validate, release)
- `ARTIFACT_PATH`: Path to the phase's checkpoint artifact (`.feature/state/<phase>/YYYY-MM-DD-<feature>.md`)

These are provided by the calling feature-* skill at its CHECKPOINT step.

### Phase 1: WALK (Parallel)

**Goal**: Extract learnings from phase artifacts using both walkers simultaneously.

Launch 2 walker agents in parallel using Agent tool:

**Context Walker** (`retro-context-walker`):
```
Analyze phase artifacts for feature FEATURE, phase PHASE.

Artifact: ARTIFACT_PATH

Compare the artifact against:
- L1 context: .feature/context/PHASE.md
- L2 context: .feature/context/<phase>/*.md

Flag:
- Drift: implementation diverged from documented decisions
- Missing: patterns in artifact not in context docs
- Corrections: context docs contradict artifact

For each finding, output:
  KEY: descriptive-slug
  VALUE: specific, actionable finding (1-3 sentences)
  CONFIDENCE: low|medium|high
  TYPE: drift|missing|correction
```

**Meta Walker** (`retro-meta-walker`):
```
Review phase execution for feature FEATURE, phase PHASE.

Artifact: ARTIFACT_PATH

Extract:
- Process patterns: what workflow approaches worked/failed
- Tool observations: which agents performed well, what conventions emerged
- Friction points: where did execution deviate from plan

For each finding, output:
  KEY: process-descriptive-slug
  VALUE: specific, actionable finding (1-3 sentences)
  CONFIDENCE: low|medium|high
  TYPE: process|implementation
```

**Timeout**: 5 minutes per walker. If one times out, proceed with available results.

**Gate**: At least 1 walker completed. Collect findings from both.

### Phase 2: MERGE

**Goal**: Group walker findings by hierarchy level and deduplicate.

**Step 1: Collect all findings**

Combine context walker and meta walker outputs into a single list:
```
findings = context_walker_findings + meta_walker_findings
```

**Step 2: Classify by hierarchy level**

| Confidence | Hierarchy Level | Action |
|---|---|---|
| LOW | L3 only | Record, wait for frequency promotion |
| MEDIUM | L3 + L2 | Record and promote to L2 |
| HIGH | L3 + L2 + L1 | Record, promote, and update L1 summary |

**Step 3: Deduplicate**

For each finding, check:
1. Does the key already exist in current feature's retro records? → Increment observation
2. Does a similar heading exist in `retro/L2/*.md`? → Flag for clustering on archive

**Gate**: Findings classified by level. Duplicates resolved. Proceed.

### Phase 3: GATE (Bottom-Up)

**Goal**: Apply approval gates from L3 upward to L1.

Execute gates in sequence (bottom-up):

**Gate 1: L3 Records** (`retro.l3-records`)
```bash
python3 scripts/feature-state.py gate FEATURE retro.l3-records
```

If `auto`: approve all L3 records.
If `human`: present records for approval:
```
#### L3 Records (N proposed)

+ process-wave-ordering [LOW]
  "Wave 1 types-only, Wave 2 logic prevented file conflicts"

>> concurrent-state-mgmt [MEDIUM] (observation 3, auto-promoted from LOW)
  "sync.Mutex is correct default for state machines"
```

**Gate 2: L2 Context** (`retro.l2-context`)
```bash
python3 scripts/feature-state.py gate FEATURE retro.l2-context
```

If `auto`: approve all MEDIUM+ promotions to L2.
If `human`: present L2 changes:
```
#### L2 Context Changes (N promotions)

~ .feature/context/implement/concurrency.md
  + Section: "State Machine Patterns"
  + "sync.Mutex is correct default for concurrent state machines"

+ .feature/context/design/api-patterns.md — new file
  + "REST endpoint naming follows resource/{id}/action pattern"
```

**Gate 3: L1 Summaries** (`retro.l1-summaries`)
```bash
python3 scripts/feature-state.py gate FEATURE retro.l1-summaries
```

If `auto`: approve HIGH confidence L1 updates.
If `human`: present L1 changes:
```
#### L1 Summary Updates (N updates)

~ .feature/context/IMPLEMENT.md
  ^ "ALWAYS use sync.Mutex for concurrent state machines" — promoted from L3 (6x observations)

~ .feature/context/DESIGN.md
  ~ Rewritten section: "API Patterns" (reflects 3 new L2 entries)
```

**Gate**: All approved changes collected. Proceed to Apply.

### Phase 4: APPLY

**Goal**: Write approved changes via feature-state.py CLI.

**Step 1: Apply L3 records** (all approved findings)

For each approved finding:
```bash
python3 scripts/feature-state.py retro-record FEATURE "KEY" "VALUE" --confidence LEVEL
```

The CLI handles:
- Observation counting (auto-increments if key exists)
- Frequency-gated auto-promotion (3 → MEDIUM, 6 → HIGH)
- Highest confidence preservation

**Step 2: Apply L2 promotions** (MEDIUM+ findings)

For each MEDIUM+ finding:
```bash
python3 scripts/feature-state.py retro-promote FEATURE "KEY"
```

**Step 3: Run audit**

```bash
python3 scripts/feature-state.py retro-audit
```

Check for issues introduced by this retro pass (missing tags, duplicates).

**Gate**: All changes applied. Audit clean (or issues noted in report).

### Phase 5: REPORT

**Goal**: Produce a summary of what was learned, promoted, and flagged.

Generate the retro report using visual prefixes:

```markdown
## Retro Report: FEATURE / PHASE

### Walkers
- Context Walker: N findings (X drift, Y missing, Z corrections)
- Meta Walker: N findings (X process, Y implementation)

### Records (L3)
+ process-wave-ordering [LOW]
  "Wave 1 types-only prevented file conflicts"

>> concurrent-state-mgmt [MEDIUM] (3x, auto-promoted)
  "sync.Mutex is correct default for state machines"

### Promotions (L2)
~ .feature/context/implement/concurrency.md
  + "State Machine Patterns" section added

### Summary Updates (L1)
^ "ALWAYS use sync.Mutex for concurrent state machines"
  Promoted from L3 after 6 observations across 2 features

### Audit
- Issues: N (or "Clean")
- Details: [any findings from retro-audit]
```

**Prefix legend**:
| Prefix | Meaning |
|--------|---------|
| `+` | New record or file created |
| `>>` | Observation appended to existing record |
| `~` | Existing file edited |
| `^` | Promoted from lower level to higher level |

**Gate**: Report displayed. Pipeline complete.

---

## Integration: How Feature Skills Invoke This Pipeline

Each feature-* skill's Phase 3: CHECKPOINT should invoke the retro pipeline:

```markdown
### Phase 3: CHECKPOINT

1. Save artifact:
   python3 scripts/feature-state.py checkpoint FEATURE PHASE

2. **Invoke retro pipeline**:
   Run the retro-pipeline skill with:
   - FEATURE: current feature name
   - PHASE: current phase
   - ARTIFACT_PATH: path to the checkpoint artifact just saved

3. Advance:
   python3 scripts/feature-state.py advance FEATURE
```

The pipeline runs between checkpoint save and phase advance. This ensures:
- Artifact exists before walkers analyze it
- Knowledge is captured before phase transition
- Retro findings from this phase inform the next phase

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| Both walkers timeout | Phase artifact too large or malformed | Record timeout in report, proceed with empty retro |
| Gate returns exit 2 | Human approval required | Present findings, wait for user response |
| retro-record fails | Invalid key or state file corrupted | Log error, continue with remaining findings |
| retro-audit finds issues | Missing tags or duplicates | Include in report, do not block pipeline |

## Anti-Patterns

| Anti-Pattern | Why Wrong | Do Instead |
|--------------|-----------|------------|
| Skip pipeline because "nothing to learn" | Every phase teaches something; walkers handle empty gracefully | Always run the pipeline |
| Write to L2/L1 directly | Bypasses observation clustering and confidence gating | Use retro-record and retro-promote CLI |
| Run walkers sequentially | Wastes time; they're independent | Launch both in parallel via Agent tool |
| Block on audit issues | Audit is informational, not a gate | Report issues, don't block pipeline |
| Inflate confidence to force promotion | Undermines frequency-gated trust system | Record honestly; let observations accumulate |

## References

- [Retro Loop](../shared-patterns/retro-loop.md) - Core retro pattern
- [Gate Enforcement](../shared-patterns/gate-enforcement.md) - Phase gates
- [Pipeline Architecture](../shared-patterns/pipeline-architecture.md) - Pipeline patterns
- [Context Walker](../../agents/retro-context-walker.md) - Domain learning extraction
- [Meta Walker](../../agents/retro-meta-walker.md) - Process learning extraction
