# Complexity Tier Examples

Real skills from the Claude Code ecosystem categorized by complexity tier with rationale.

## Simple Tier (300-600 lines)

### pr-cleanup
**Lines**: ~350
**Purpose**: Local branch cleanup after PR merge
**Phases**: 4 (Identify, Switch, Delete, Prune)
**Why Simple**:
- Single linear workflow
- No subagent coordination
- Minimal error cases (3)
- No reference files needed

**Structure**:
```
.claude/skills/pr-cleanup/
└── SKILL.md (350 lines)
    - Frontmatter (40 lines)
    - Instructions - 4 phases (180 lines)
    - Error Handling - 3 errors (60 lines)
    - Anti-Patterns - 2 patterns (40 lines)
    - Anti-Rationalization (30 lines)
```

---

### branch-naming
**Lines**: ~400
**Purpose**: Generate Git branch names from descriptions
**Phases**: 3 (Parse, Transform, Validate)
**Why Simple**:
- Single deterministic operation
- Python script does heavy lifting
- Few error cases (4)
- No multi-agent coordination

**Structure**:
```
.claude/skills/branch-naming/
├── SKILL.md (280 lines)
└── scripts/
    └── generate.py (120 lines)
```

---

## Medium Tier (800-1500 lines)

### systematic-debugging
**Lines**: ~1200
**Purpose**: Evidence-based root cause analysis
**Phases**: 4 (Reproduce, Isolate, Identify, Verify)
**Why Medium**:
- Multi-phase workflow with gates
- Moderate error handling (7 cases)
- Some anti-patterns (4)
- No references/ needed yet

**Structure**:
```
.claude/skills/systematic-debugging/
└── SKILL.md (1200 lines)
    - Frontmatter (60 lines)
    - Instructions - 4 phases (500 lines)
    - Error Handling - 7 errors (250 lines)
    - Anti-Patterns - 4 patterns (200 lines)
    - Anti-Rationalization (100 lines)
    - Blocker Criteria (90 lines)
```

---

### git-commit-flow
**Lines**: ~1100
**Purpose**: Phase-gated git commit workflow
**Phases**: 5 (Status, Diff, Log, Stage, Commit)
**Why Medium**:
- Sequential Git operations
- Validation at each phase
- Moderate scripting (2 scripts)
- 6 error cases

**Structure**:
```
.claude/skills/git-commit-flow/
├── SKILL.md (900 lines)
└── scripts/
    ├── validate.py (120 lines)
    └── commit-msg.py (80 lines)
```

---

## Complex Tier (1500-2500 lines)

### parallel-code-review
**Lines**: ~2200
**Purpose**: Parallel 3-reviewer orchestration
**Phases**: 4 (Prepare, Execute, Aggregate, Report)
**Why Complex**:
- Multi-agent coordination (3 reviewers)
- Parallel execution with timeouts
- Verdict synthesis logic
- Death loop prevention required
- 10+ error cases

**Structure**:
```
.claude/skills/parallel-code-review/
├── SKILL.md (1600 lines)
│   - Frontmatter (80 lines)
│   - Instructions - 4 phases (700 lines)
│   - Death Loop Prevention (200 lines)
│   - Error Handling - top 5 (150 lines)
│   - Anti-Patterns - top 5 (200 lines)
│   - Anti-Rationalization (150 lines)
│   - References (120 lines)
└── references/
    ├── error-catalog.md (400 lines)
    └── verdict-aggregation.md (200 lines)
```

---

### workflow-orchestrator
**Lines**: ~2100
**Purpose**: Three-phase task orchestration
**Phases**: 4 (BRAINSTORM, WRITE-PLAN, EXECUTE-PLAN, VERIFY)
**Why Complex**:
- Multi-file coordination
- Task tool integration
- State management
- Multiple workflow patterns
- Extensive error handling

**Structure**:
```
.claude/pipelines/workflow-orchestrator/
├── SKILL.md (1500 lines)
│   - Frontmatter (70 lines)
│   - Instructions - 4 phases (800 lines)
│   - State Management (200 lines)
│   - Error Handling - top 5 (150 lines)
│   - Anti-Patterns - top 5 (180 lines)
│   - References (100 lines)
└── references/
    ├── error-catalog.md (350 lines)
    └── workflow-patterns.md (250 lines)
```

---

## Comprehensive Tier (2500-4000 lines)

### go-testing
**Lines**: ~3800
**Purpose**: Go testing patterns and methodology
**Phases**: Multiple workflows (table-driven, subtests, helpers, mocks, benchmarks)
**Why Comprehensive**:
- Multiple complex workflows
- Extensive code examples (30+)
- Deep Go testing expertise
- Comprehensive error catalog
- Reference-quality documentation

**Structure**:
```
.claude/skills/go-testing/
├── SKILL.md (2000 lines)
│   - Frontmatter (90 lines)
│   - Core Workflows (800 lines)
│   - Top 5 errors (200 lines)
│   - Top 5 anti-patterns (250 lines)
│   - Quick reference (300 lines)
│   - References section (160 lines)
└── references/
    ├── error-catalog.md (600 lines)
    ├── code-examples.md (800 lines)
    ├── anti-patterns.md (500 lines)
    └── table-driven-testing.md (400 lines)
```

---

### go-concurrency
**Lines**: ~3500
**Purpose**: Go concurrency patterns and primitives
**Phases**: Multiple workflows (goroutines, channels, sync primitives, worker pools)
**Why Comprehensive**:
- Multiple complex concurrency patterns
- 40+ code examples
- Extensive race condition catalog
- Deep Go concurrency expertise
- Production debugging patterns

**Structure**:
```
.claude/skills/go-concurrency/
├── SKILL.md (1800 lines)
│   - Frontmatter (100 lines)
│   - Core Patterns (700 lines)
│   - Top 5 errors (180 lines)
│   - Top 5 anti-patterns (220 lines)
│   - Quick reference (350 lines)
│   - References section (150 lines)
└── references/
    ├── error-catalog.md (700 lines)
    ├── code-examples.md (900 lines)
    ├── anti-patterns.md (600 lines)
    └── worker-pools.md (400 lines)
```

---

## Tier Selection Decision Tree

### Start: What kind of workflow?

**Single, focused operation?**
→ Simple tier
- Examples: pr-cleanup, branch-naming, service-health-check
- Characteristics: Linear workflow, minimal scripting, <5 errors

**Multi-step with moderate coordination?**
→ Medium tier
- Examples: systematic-debugging, git-commit-flow, pr-fix
- Characteristics: 2-4 phases, moderate scripting, 5-10 errors

**Multi-agent coordination OR parallel execution?**
→ Complex tier
- Examples: parallel-code-review, workflow-orchestrator, research-coordinator
- Characteristics: Subagent spawning, parallel tasks, death loop prevention, 10+ errors

**Reference-quality with multiple complex workflows?**
→ Comprehensive tier
- Examples: go-testing, go-concurrency, go-error-handling
- Characteristics: Multiple workflows, 30+ code examples, extensive catalogs

---

## Migration Patterns

### Simple → Medium (when to upgrade)
**Signals**:
- Added 2nd or 3rd phase with complex gates
- Error cases approaching 10
- Users requesting more detailed workflows

**Example**: pr-cleanup → pr-pipeline (added commit, push, create-pr phases)

---

### Medium → Complex (when to upgrade)
**Signals**:
- Added subagent coordination
- Parallel execution needed
- Reference files created
- Main file approaching 1500 lines

**Example**: code-review → parallel-code-review (added 3 parallel reviewers)

---

### Complex → Comprehensive (when to upgrade)
**Signals**:
- Multiple distinct workflows in one skill
- Code examples exceeding 20
- Reference files exceeding 1500 total lines
- Becoming reference documentation

**Example**: testing-patterns → go-testing (added table-driven, mocks, benchmarks workflows)

---

## Anti-Patterns in Tier Selection

### ❌ Over-Tiering
**What it looks like**: Simple workflow (pr-cleanup) implemented as Complex tier with references/, death loop prevention, 10+ error cases

**Why wrong**: Creates maintenance burden, confuses users, violates Over-Engineering Prevention

**Fix**: Reduce to appropriate tier - Simple workflows stay Simple

---

### ❌ Under-Tiering
**What it looks like**: Multi-agent orchestration skill (parallel-code-review) implemented as Medium tier with no death loop prevention

**Why wrong**: Missing critical patterns, will fail in production, no scaling considerations

**Fix**: Upgrade to Complex tier, add death loop prevention, create references/

---

### ❌ Tier Drift
**What it looks like**: Skill starts as Simple (400 lines), grows to 2000 lines over time without restructuring

**Why wrong**: Violates progressive disclosure, bloats context, makes skill hard to maintain

**Fix**: Promote to appropriate tier, extract references/, apply progressive disclosure
