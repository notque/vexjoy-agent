---
name: toolkit-evolution
description: "Closed-loop toolkit self-improvement: discover gaps, diagnose, propose, critique, build, test, evolve."
user-invocable: true
argument-hint: "<optional: focus area like 'routing' or 'hooks'>"
command: evolve
context: fork
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Agent
  - Skill
routing:
  triggers:
    - "evolve toolkit"
    - "improve the system"
    - "self-improve"
    - "toolkit evolution"
    - "what should we improve"
    - "find improvement opportunities"
    - "discover skill gaps"
    - "what skills are missing"
    - "systematic improvement"
  pairs_with:
    - multi-persona-critique
    - skill-eval
  complexity: Complex
  category: meta-tooling
---

# Toolkit Evolution

Schedulable (nightly) or manual 7-phase pipeline for continuous toolkit self-improvement. Discovers gaps, diagnoses from evidence, proposes solutions, critiques via multi-persona review, builds on isolated branches, A/B tests, and promotes via PR.

Nightly sibling of `auto-dream` (2:07 AM consolidates memories; 3:07 AM this skill diagnoses and builds). They feed each other: dream's graduated learnings inform diagnosis; evolution's results become dream's next input.

Invoke: `/evolve`, `/evolve routing`, `/evolve hooks`, `/evolve --discover`. Cron setup in `references/evolve-preferred-patterns.md`.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| tasks related to this reference | `diagnose-scripts.md` | Loads detailed guidance from `diagnose-scripts.md`. |
| tasks related to this reference | `evolution-report-template.md` | Loads detailed guidance from `evolution-report-template.md`. |
| implementation patterns | `evolve-preferred-patterns.md` | Loads detailed guidance from `evolve-preferred-patterns.md`. |
| tasks related to this reference | `evolve-scripts.md` | Loads detailed guidance from `evolve-scripts.md`. |

## Instructions

### Phase 0: DISCOVER -- Find what's missing

**Goal**: Identify skills, agents, or capabilities the toolkit should have but doesn't.

**Frequency**: Monthly, not every run. Executes only if:
- `--discover` flag passed explicitly, OR
- 30+ days since last discovery run

Check last run date using `references/diagnose-scripts.md` frequency check. If neither condition met, skip to Phase 1.

**Step 1: Gather briefing data** -- Collect toolkit state using commands from `references/diagnose-scripts.md` DISCOVER Step 1. Brief all 5 perspective agents with same baseline.

**Step 2: Dispatch 5 perspective agents in parallel** -- See `references/evolve-preferred-patterns.md` Phase 0 for agent table and proposal format.

**Step 3: Deduplicate and filter** -- Remove duplicates of existing skills (check `skills/INDEX.json`), remove proposals without evidence, group similar proposals noting convergent evidence.

**Step 4: Feed into DIAGNOSE** -- Append surviving proposals to Phase 1 opportunity list tagged `[DISCOVER]`.

**Step 5: Save discovery report** to `evolution-reports/discovery-{YYYY-MM-DD}.md` (run `mkdir -p evolution-reports` first). Include briefing data, all proposals, filtering rationale, forwarded proposals, date stamp.

**Gate**: Discovery report saved. Proposals forwarded to Phase 1. Proceed to DIAGNOSE.

---

### Phase 1: DIAGNOSE -- Find improvement opportunities

**Goal**: Identify 5-10 evidence-backed improvement opportunities.

**Step 1: Query learning database** -- Run 4 search queries from `references/diagnose-scripts.md` DIAGNOSE Step 1. Look for: routing patterns, recurring failures, underperforming skills, error patterns without automated fixes.

**Step 2: Scan recent git history** -- Run commands from `references/diagnose-scripts.md` DIAGNOSE Step 2.

**Step 3: Check auto-dream reports** -- Run check from `references/diagnose-scripts.md` DIAGNOSE Step 3, read most recent dream-analysis file.

**Step 3b: Cross-validate dream insights** -- Verify insights still reflect current repo using `references/diagnose-scripts.md` DIAGNOSE Step 3b. Mark insight STALE if: (a) names a file that no longer exists, OR (b) claims recent activity but `git log` shows nothing in past 7 days.

**Step 4: Check routing-table drift** -- Skills in `skills/INDEX.json` but absent from routing tables are a documentation gap. Run check from `references/diagnose-scripts.md` DIAGNOSE Step 4.

**Step 4b: Check for orphaned ADR session files** -- Run check from `references/diagnose-scripts.md` DIAGNOSE Step 4b. Flag any found.

**Step 4c: Scan for registered stub hooks** -- Run audit from `references/diagnose-scripts.md` DIAGNOSE Step 4c. Flag stubs as cleanup opportunities.

**Step 5: Narrow by focus area** -- If user specified a focus (e.g., "routing", "hooks"), filter all findings to that domain.

**Step 6: Compile opportunity list** -- 5-10 numbered opportunities. Each includes: **What** (one sentence), **Evidence** (data source), **Impact** (High/Medium/Low).

**Gate**: At least 3 evidence-backed opportunities. If fewer, expand time window or broaden sources. Do not proceed with speculative opportunities.

---

### Phase 2: PROPOSE -- Generate concrete solutions

**Goal**: Transform opportunities into actionable proposals.

**Step 1: Generate proposals** -- 1-2 per opportunity. Must be actionable: "Add anti-pattern X to agent Y" (not "improve agent Y"). "Create reference file for Z in skill W" (not "enhance skill W").

**Step 2: Estimate effort**

| Effort | Definition |
|--------|-----------|
| Small | Single file edit, <30 lines |
| Medium | 2-5 files, new reference or script, <200 lines |
| Large | New skill or agent, multiple components, >200 lines |

**Step 3: Check for duplicates**

```bash
cat skills/INDEX.json | python3 -c "import sys,json; idx=json.load(sys.stdin); [print(k,'-',v.get('description','')) for k,v in idx.get('skills',{}).items()]" 2>/dev/null || echo "INDEX.json parse failed -- check manually"
```

Drop duplicates of existing capabilities.

**Step 4: Rank proposals** -- Rank by: (Impact) x (1/Effort), where High=3, Medium=2, Low=1 and Small=1, Medium=2, Large=3.

Output: ranked list of 5-10 proposals with description, scope, effort, expected outcome.

**Gate**: All proposals concrete (specific files named), non-duplicative (verified against INDEX.json), ranked. Proceed with top 5.

---

### Phase 3: CRITIQUE -- Multi-persona evaluation

**Goal**: Evaluate proposals from multiple perspectives to surface blind spots.

**Step 1: Check for multi-persona-critique skill**

```bash
test -f skills/multi-persona-critique/SKILL.md && echo "AVAILABLE" || echo "NOT AVAILABLE"
```

**Step 2a: If available** -- `Skill(skill="multi-persona-critique", args="Evaluate these toolkit improvement proposals: {proposals}")`

**Step 2b: If NOT available** -- Use inline fallback from `references/evolve-preferred-patterns.md` Phase 3.

**Step 3: Synthesize consensus** -- Average persona scores (STRONG=3, MODERATE=2, WEAK=1):
- >= 2.5 = STRONG consensus
- 1.5-2.4 = MODERATE consensus
- < 1.5 = WEAK (shelve)

**Gate**: All personas reported. At least 1 STRONG proposal. If none, revisit Phase 2 with feedback or report to user.

**On early exit (no STRONG proposals)**: Always record to learning DB. See `references/evolve-scripts.md` Early Exit Record.

---

### Phase 4: BUILD -- Implement winners

**Goal**: Implement top 1-3 STRONG-rated proposals on isolated feature branches.

**Constraint**: Maximum 3 per cycle.

**Step 1: Select winners** -- Top 1-3 STRONG proposals only. Do not pad with MODERATE.

**Step 2: Dispatch implementation agents** -- See `references/evolve-scripts.md` Build Dispatch for proposal-type to implementation-approach table. Each creates branch `feat/evolve-{proposal-slug}` with descriptive commit.

**Step 3: Validate** -- `python3 -m scripts.skill_eval.quick_validate skills/{skill-name}`, `python3 -m py_compile {script}`, `bash -n {script}`.

**Gate**: All implementations committed on feature branches. Basic validation passed.

---

### Phase 5: VALIDATE -- A/B test implementations

**Goal**: Empirically verify implementations improve outcomes vs baseline.

**Step 1: Create test cases** -- 3-5 realistic prompts per implementation exercising the changed behavior.

**Step 2: Run comparisons** -- See `references/evolve-scripts.md` Validate Run for skill-eval command and manual fallback.

**Step 3: Evaluate results** -- Win condition: 60%+ test cases show improvement on at least one dimension, no dimension regressed >1 point (5-point scale), no new failures.

**Gate**: All implementations tested. Win/loss determined. Evidence recorded.

---

### Phase 6: EVOLVE -- Promote winners and record learnings

**Goal**: Ship winners via PR, record all outcomes.

**Step 1: Handle winners** -- Create PR using template from `references/evolve-scripts.md` Step 1. Run pr-review, then merge. Multi-persona critique + A/B testing is the review gate.

**Step 1b: Clean up feature branch** -- Use `references/evolve-scripts.md` Step 1b.

**Step 2: Handle losers** -- Record what was tried and why it failed using `references/evolve-scripts.md` Step 2.

**Step 3: Record full cycle** -- Use `references/evolve-scripts.md` Step 3.

**Step 4: Write evolution report** -- Save to `evolution-reports/evolution-report-{YYYY-MM-DD}.md` using `references/evolution-report-template.md`. Setup in `references/evolve-scripts.md` Step 4.

**Gate**: Winners merged. Learnings recorded for all proposals. Report written. Cycle complete.

---

## Reference Loading

| Signal | Load |
|--------|------|
| Phase 0 DISCOVER or Phase 1 DIAGNOSE commands | `references/diagnose-scripts.md` |
| Phase 0 agent table, Phase 3 critique fallback, anti-patterns, scheduling | `references/evolve-preferred-patterns.md` |
| Phase 6 EVOLVE (PR, merge, cleanup, learning DB) | `references/evolve-scripts.md` |
| Writing/reading evolution report | `references/evolution-report-template.md` |

---

## References

- `references/evolution-report-template.md` -- Evolution report template
- `references/diagnose-scripts.md` -- Phase 0 and Phase 1 commands
- `references/evolve-scripts.md` -- Phase 6 PR, merge, cleanup, learning DB commands
- `references/evolve-preferred-patterns.md` -- Anti-patterns, error handling, cost, critique fallback, scheduling
- `skills/auto-dream/SKILL.md` -- Nightly sibling: memory consolidation
- `skills/skill-eval/SKILL.md` -- Skill testing and benchmarking
- `skills/multi-persona-critique/SKILL.md` -- Multi-persona evaluation (inline fallback in references)
- `skills/skill-creator/SKILL.md` -- Skill creation methodology
- `skills/agent-comparison/SKILL.md` -- A/B testing methodology
- `skills/headless-cron-creator/SKILL.md` -- Cron job creation patterns
