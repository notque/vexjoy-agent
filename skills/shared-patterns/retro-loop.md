# Retro Loop Pattern

Extract and promote knowledge at phase checkpoints. Any skill can reference this pattern to add self-improving context management.

## Orchestration

The retro loop is orchestrated by the **retro-pipeline** skill (`skills/retro-pipeline/SKILL.md`), a 5-phase pipeline:

```
WALK (parallel) → MERGE → GATE → APPLY → REPORT
```

All 5 feature lifecycle skills invoke the retro pipeline at their Phase 3: CHECKPOINT step. The pipeline spawns both walkers in parallel, merges outputs by hierarchy level, gates bottom-up (L3→L2→L1), applies approved changes, and reports with visual prefixes.

## How It Works

At the end of a phase, two parallel analysis passes run:

### Context Walker (what we built vs what we documented)

1. Read the phase's output artifacts from `.feature/state/<phase>/`
2. Compare against published context in `.feature/context/<PHASE>.md` (L1) and `.feature/context/<phase>/` (L2)
3. Flag drift: implementation diverged from documented decisions
4. Propose L2 updates with specific diffs

### Meta Walker (what we learned about how we work)

1. Review the phase execution: what tools were used, what patterns emerged, what conventions were discovered
2. Record findings with confidence tags:
   - **LOW**: First observation. May be one-off.
   - **MEDIUM**: Seen 2-3 times. Likely a real pattern.
   - **HIGH**: Well-established. Should be a procedure.
3. Write L3 records via: `python3 scripts/feature-state.py retro-record FEATURE KEY VALUE --confidence LEVEL`

## Promotion Pipeline

```
L3 (meta/<phase>/record.md)  →  L2 (context/<phase>/topic.md)  →  L1 (context/PHASE.md)
     LOW/MEDIUM findings          MEDIUM/HIGH promoted              HIGH auto-summarized
```

**Promotion criteria**:
- LOW → stays at L3 until confidence rises
- MEDIUM → promoted to L2 via `retro-promote` command
- HIGH → promoted to L2 and L1 summary updated

**Frequency-gated auto-promotion**: When the same key is recorded multiple times, observation count increments automatically. At 3 observations, LOW auto-promotes to MEDIUM. At 6, MEDIUM auto-promotes to HIGH. The highest confidence seen is always preserved.

**Command**: `python3 scripts/feature-state.py retro-promote FEATURE KEY`

## L3 Record Format

Walkers produce structured observations in a lean format:

```markdown
## {key} [{CONFIDENCE}]

{What was learned - specific, actionable finding}

*Phase*: {design|plan|implement|validate|release}
*Source*: {artifact path}
*Recorded*: {ISO timestamp}
```

This is intentionally simpler than a full Observation/Context/Rationale/Source/Confidence format. We keep it lean because our records go through `retro-record` which handles metadata.

## Observation Clustering

Observations are tracked at two levels:

1. **Within a feature** (`retro-record`): Recording the same key multiple times increments the observation count. This count carries through to archival and triggers frequency-gated auto-promotion.

2. **Across features** (`complete` archival): When archiving to `retro/L2/`, the `complete` command checks existing L2 files for matching `### headings`. If a heading from a new feature matches an existing entry, the `[Nx]` counter is incremented instead of duplicating:

```markdown
### D4: Sync Mutex Over Atomics For State Machines [3x]
```

This lightweight confidence signal replaces a full L3 hierarchy. High-observation entries signal well-established patterns.

## Language-Aware Gating

L2 files should include a `**Languages**:` field alongside tags:

```markdown
**Tags**: go, middleware, concurrency
**Languages**: go
```

The injector hook penalizes L2 files whose language tags don't match the current project's language (detected from file extensions). This prevents Go advice from loading in Python projects.

## Integration with Existing System

The retro loop uses our existing learning infrastructure:

| Component | Role |
|-----------|------|
| `scripts/feature-state.py` | Deterministic state and retro operations |
| `hooks/lib/learning_db_v2.py` | Confidence scoring for gate auto-flip |
| `shared-patterns/gate-enforcement.md` | Phase transition gates |
| `agents/retro-context-walker.md` | Reconciles phase artifacts against context docs |
| `agents/retro-meta-walker.md` | Extracts process learnings from phase execution |

## Configurable Retro Gates

Gate modes control whether retro operations require human approval or run automatically. All retro gates default to `auto` (no token limits on Claude Max):

| Gate | Default | Env Override |
|------|---------|-------------|
| `retro.l3-records` | auto | `CLAUDE_RETRO_GATE_L3_RECORDS` |
| `retro.l2-context` | auto | `CLAUDE_RETRO_GATE_L2_CONTEXT` |
| `retro.l1-summaries` | auto | `CLAUDE_RETRO_GATE_L1_SUMMARIES` |
| `retro.phase-checkpoint` | auto | `CLAUDE_RETRO_GATE_PHASE_CHECKPOINT` |

Set env var to `human` to require approval for specific gates.

## Retro Audit

Detect stale, orphaned, or incomplete L2 files:

```bash
python3 scripts/feature-state.py retro-audit
```

Checks for: missing `**Tags**:` line, missing `**Languages**:` line, no `###` learnings, and cross-file duplicate headings that could be consolidated.

## Auto-Injection (Default ON)

Retro knowledge is automatically injected into agent context via the `retro-knowledge-injector` hook.

**How it works**:
1. Hook fires on every `UserPromptSubmit`
2. Fast-path skip for trivial prompts (< 4 words, questions, reads)
3. Checks work intent (implement, build, design, plan, etc.)
4. Loads L1 (~20 lines, always) + relevance-gated L2 files (no cap)
5. L2 relevance: keyword matching between prompt and L2 `**Tags**:` line

**Persistent store**: `retro/L1.md` and `retro/L2/*.md` in the agents repo.

**Archiving**: When `feature-state.py complete` runs, promoted L2 knowledge is automatically copied to `retro/L2/<feature>.md` with observation counts preserved.

**Benchmark validation** (7 trials, blind grading):
- Win rate: 67% when knowledge is relevant
- Avg margin: +5.3 points on 8-dimension rubric
- Knowledge Transfer dimension: 5-0 win record
- Token efficiency: retro agents use 32% FEWER tokens (23.5K vs 34.5K)

**Critical finding**: Full SKILL.md loading HURTS (-11 points). Compact L1/L2 summaries HELP (+5.3 avg). The value is in accumulated knowledge, not in process methodology.

## When to Use

- After any phase checkpoint in feature-lifecycle skills
- After completing a `workflow-orchestrator` plan
- After any multi-phase pipeline completion
- Whenever a session produces reusable knowledge

## Anti-Patterns

| Anti-Pattern | Why Wrong | Do Instead |
|--------------|-----------|------------|
| Skip retro because "nothing learned" | Every phase teaches something | Run walkers; they handle empty phases gracefully |
| Write directly to L2/L1 | Bypasses confidence gating | Always write to L3 first, promote via script |
| Record generic findings | "Follow best practices" teaches nothing | Record specific: "use snake_case for DB columns in this project" |
| Promote everything to HIGH | Dilutes signal | Let frequency-gated auto-promotion handle it (3 obs → MEDIUM, 6 → HIGH) |
| Ignore retro-audit output | Stale L2 files degrade injection quality | Run `retro-audit` periodically and fix issues |
