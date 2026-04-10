---
name: toolkit-evolution
description: "Closed-loop toolkit self-improvement: discover gaps, diagnose, propose, critique, build, test, evolve."
version: 1.0.0
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

Schedulable (nightly) or manually-invoked 7-phase pipeline that drives continuous improvement of the toolkit itself. Chains existing skills into a full closed-loop improvement cycle: discover capability gaps from multiple perspectives, diagnose problems from evidence, propose solutions, critique them from multiple perspectives, build the winners, A/B test against baselines, and promote winners via PR.

This is the nightly sibling of `auto-dream`. Auto-dream (2:07 AM) consolidates memories, graduates learnings, and prunes stale data. Toolkit-evolution (3:07 AM) diagnoses gaps, proposes features, builds and tests improvements. They feed each other: dream's graduated learnings inform evolution's diagnosis; evolution's results become dream's input for consolidation.

## When to invoke

- User says "evolve toolkit", "improve the system", "self-improve", "what should we improve"
- Cron job weekly (Sunday 3 AM) via wrapper script
- Manual trigger with optional focus area: `/evolve routing`, `/evolve hooks`
- Discovery mode: `/evolve --discover` (runs Phase 0 regardless of last-run date)

## Instructions

### Phase 0: DISCOVER -- Find what's missing

**Goal**: Identify skills, agents, or capability categories the toolkit should have but doesn't. While later phases improve existing components, this phase finds entirely new capabilities the toolkit is missing.

**Frequency**: Monthly, not every run. The DISCOVER phase only executes if:
- `--discover` flag is passed explicitly, OR
- It has been 30+ days since the last discovery run

Check the last discovery run date:

```bash
# Find the most recent discovery report
latest=$(ls -t evolution-reports/discovery-*.md 2>/dev/null | head -1)
if [ -z "$latest" ]; then
  echo "NO_PREVIOUS_DISCOVERY"
else
  # Extract date from filename: discovery-YYYY-MM-DD.md
  report_date=$(basename "$latest" | sed 's/discovery-//;s/\.md//')
  days_ago=$(( ($(date +%s) - $(date -d "$report_date" +%s)) / 86400 ))
  echo "Last discovery: $report_date ($days_ago days ago)"
  [ "$days_ago" -ge 30 ] && echo "DISCOVER_DUE" || echo "DISCOVER_SKIPPED"
fi
```

If neither condition is met, skip directly to Phase 1.

**Step 1: Gather briefing data**

Collect current toolkit state to brief all perspective agents with the same baseline:

```bash
# Skill count and category distribution
python3 -c "
import json
with open('skills/INDEX.json') as f:
    idx = json.load(f)
skills = idx.get('skills', {})
print(f'Total skills: {len(skills)}')
categories = {}
for s, meta in skills.items():
    cat = meta.get('category', 'uncategorized')
    categories[cat] = categories.get(cat, 0) + 1
for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
    print(f'  {cat}: {count}')
"

# Agent count
python3 -c "
import json
with open('agents/INDEX.json') as f:
    idx = json.load(f)
agents = idx.get('agents', {})
print(f'Total agents: {len(agents)}')
for a in sorted(agents):
    print(f'  {a}')
"
```

**Step 2: Dispatch 5 perspective agents in parallel**

Each agent receives the briefing data from Step 1 and evaluates from a different angle. Dispatch all 5 simultaneously:

| Agent | Perspective | What it looks for |
|-------|------------|-------------------|
| **The User** | Analyzes learning.db for unmatched routing requests (`python3 scripts/learning-db.py query --category routing-decision`), error patterns, and requests that had no agent match. "What did users ask for that we couldn't handle?" |
| **The Operator** | Examines the active projects (check git repos in `~/`) for repeated manual workflows that could be skills. "What am I doing by hand that should be automated?" |
| **The Strategist** | Uses the csuite skill's EVALUATION mode thinking: what decision-support, content, or process skills would make the owner more effective? Reads `skills/csuite/SKILL.md` for framework. "What high-leverage skills are we missing?" |
| **The Community** | Web-searches for what people are building and requesting in AI coding communities (Claude Code GitHub issues, Reddit, X/Twitter). "What does the market want?" |
| **The Architect** | Examines current skill categories (from `skills/INDEX.json`) for structural gaps. Cross-references with `agents/INDEX.json`. "Where are the architectural blind spots?" E.g., "we have 23 process skills but 0 decision skills." |

Each agent produces 2-3 skill proposals in this format:

```
PROPOSAL: {skill-name}
Category: {category}
Triggers: {3-5 routing triggers}
Justification: {1-2 sentences on why this is needed}
Evidence: {what data supports this -- routing gaps, user patterns, market signals}
```

**Step 3: Deduplicate and filter**

Collect all proposals from the 5 agents and apply these filters:

1. **Remove duplicates of existing skills** -- check each proposal name and its triggers against `skills/INDEX.json`. If an existing skill already covers the proposed capability, drop it.
2. **Remove proposals with no evidence** -- pure speculation ("it might be useful someday") is not evidence. Require at least one concrete data point: a routing miss, a manual workflow observed, a community request, or a structural gap.
3. **Group similar proposals** -- if multiple agents proposed the same capability from different angles, merge them into a single proposal and note the convergent evidence (multi-agent convergence strengthens the case).

**Step 4: Feed into DIAGNOSE**

The surviving proposals become additional input for Phase 1 (DIAGNOSE). They are treated as "capability gaps" alongside the usual diagnosis signals (error patterns, routing mismatches, git churn). Append them to the Phase 1 opportunity list with source tagged as `[DISCOVER]`.

**Step 5: Save discovery report**

Write `evolution-reports/discovery-{YYYY-MM-DD}.md` with:
- Briefing data (skill count, agent count, category distribution)
- All proposals from each perspective agent (kept and filtered)
- Filtering rationale for each dropped proposal
- Which proposals were forwarded to DIAGNOSE
- Date stamp for frequency gating

```bash
# Ensure the reports directory exists
mkdir -p evolution-reports

# Write the discovery report
# Path: evolution-reports/discovery-{YYYY-MM-DD}.md
```

**Gate**: Discovery report saved. Proposals forwarded to Phase 1. Proceed to DIAGNOSE.

---

### Phase 1: DIAGNOSE -- Find improvement opportunities

**Goal**: Identify 5-10 evidence-backed improvement opportunities from multiple data sources.

**Step 1: Query the learning database for recent failures and routing mismatches**

```bash
python3 ~/.claude/scripts/learning-db.py search "routing decision mismatch reroute" --min-confidence 0.3 --limit 20
python3 ~/.claude/scripts/learning-db.py search "error pattern failure bug" --min-confidence 0.3 --limit 20
python3 ~/.claude/scripts/learning-db.py search "skill gap missing improvement" --min-confidence 0.3 --limit 20
```

Look for: recurring failures, routing mismatches where the user had to reroute, skills that consistently underperform, error patterns without automated fixes.

**Step 2: Scan recent git history for patterns**

```bash
# Frequent fixes to same areas suggest chronic issues
git log --oneline --since="2 weeks ago" | head -40

# Files changed most frequently (churn = potential problems)
git log --since="2 weeks ago" --pretty=format: --name-only | sort | uniq -c | sort -rn | head -20
```

**Step 3: Check auto-dream reports for accumulated insights**

```bash
ls -t ~/.claude/state/dream-* 2>/dev/null | head -5
# Read the most recent dream report for synthesized insights
```

If dream reports exist, read the latest one -- it contains cross-session patterns and graduation candidates that may point to improvement opportunities.

**Step 4: Check routing-table drift**

Skills present in `skills/INDEX.json` but absent from `skills/do/references/routing-tables.md` represent a documentation gap — the router can find them via index but they are invisible to any process that consults the reference docs. This gap has been missed in two consecutive cycles before being manually caught. Detect it programmatically:

```bash
python3 -c "
import json, re
with open('skills/INDEX.json') as f:
    idx = json.load(f)
index_skills = set(idx.get('skills', {}).keys())

with open('skills/do/references/routing-tables.md') as f:
    table_text = f.read()

missing = [s for s in sorted(index_skills) if s not in table_text]
if missing:
    print(f'{len(missing)} skill(s) in INDEX.json absent from routing-tables.md:')
    for s in missing:
        print(f'  {s}')
else:
    print('routing-tables.md is in sync with INDEX.json')
"
```

Any skill absent from routing-tables.md is a candidate improvement opportunity — especially new skills added in the past two weeks.

**Step 4b: Check for orphaned ADR session files**

A stale `.adr-session.json` referencing a non-existent ADR file will block all `skills/` edits via the synthesis gate mid-cycle. Detect this at Phase 1 start rather than discovering it as a blocker later:

```bash
if [ -f ".adr-session.json" ]; then
  adr_id=$(python3 -c "
import json, sys
try:
    d = json.load(open('.adr-session.json'))
    print(d.get('adr_id', d.get('id', 'unknown')))
except Exception as e:
    print('PARSE_ERROR')
")
  adr_file="adr/ADR-${adr_id}.md"
  if [ "$adr_id" = "PARSE_ERROR" ]; then
    echo "WARNING: .adr-session.json exists but is unparseable -- flag as cleanup opportunity"
  elif [ ! -f "$adr_file" ]; then
    echo "WARNING: .adr-session.json references ADR-${adr_id} but $adr_file does not exist"
    echo "  Orphaned session file. Add 'Remove orphaned .adr-session.json' to the opportunity list."
  else
    echo "ADR session OK: ADR-${adr_id} exists at $adr_file"
  fi
else
  echo "No active ADR session file (OK)"
fi
```

If an orphaned session is found, flag it as a cleanup opportunity in Step 6. Do not remove it automatically -- flag it so the user can confirm before deletion.

**Step 4c: Scan for registered stub hooks**

A stub hook is registered in settings.json but does nothing (body calls `empty_output()` or contains a `DISABLED` marker). Stubs waste a hook slot and fire on every matching event while returning empty output. They accumulate silently without this check.

```bash
python3 -c "
import json, os, re
from pathlib import Path

settings_path = Path('.claude/settings.json')
if not settings_path.exists():
    print('No .claude/settings.json found -- skip hook stub audit')
else:
    with open(settings_path) as f:
        settings = json.load(f)
    hooks = settings.get('hooks', {})
    stubs = []
    for event, groups in hooks.items():
        for group in (groups if isinstance(groups, list) else [groups]):
            entries = group.get('hooks', [group]) if isinstance(group, dict) else [group]
            for entry in entries:
                cmd = entry.get('command', '') if isinstance(entry, dict) else str(entry)
                m = re.search(r'python3 [\"\\x27]?([\\w/.\$~-]+\\.py)[\"\\x27]?', cmd)
                if not m:
                    continue
                script = m.group(1).replace('\$HOME', str(Path.home()))
                script = os.path.expandvars(script)
                if not os.path.exists(script):
                    continue
                with open(script) as sf:
                    body = sf.read()
                if 'DISABLED' in body or 'empty_output()' in body:
                    desc = entry.get('description', '(no description)') if isinstance(entry, dict) else ''
                    stubs.append((event, os.path.basename(script), desc))
    if stubs:
        print(f'{len(stubs)} stub hook(s) registered in settings.json:')
        for ev, name, desc in stubs:
            print(f'  [{ev}] {name} -- {desc}')
        print('  Add stub deregistration to the opportunity list.')
    else:
        print('No stub hooks found (OK)')
"
```

Flag any stub hook as a cleanup opportunity in Step 6. Do not deregister automatically -- document the stub so the BUILD phase handles it deliberately.

**Step 5: Narrow by focus area (if provided)**

If the user specified a focus area (e.g., "routing", "hooks", "agents"), filter all findings to that domain. If no focus area, analyze broadly.

**Step 6: Compile opportunity list**

Output a numbered list of 5-10 improvement opportunities. Each entry must include:
- **What**: One-sentence description of the problem or gap
- **Evidence**: Which data source surfaced it (learning DB entry, git churn, dream report)
- **Impact**: Estimated user impact (High/Medium/Low)

**Gate**: At least 3 evidence-backed opportunities identified. If fewer than 3, expand the time window or broaden the data sources. Do not proceed with speculative opportunities that lack evidence.

---

### Phase 2: PROPOSE -- Generate concrete solutions

**Goal**: Transform opportunities into actionable proposals with clear scope.

**Step 1: Generate proposals**

For each opportunity from Phase 1, propose 1-2 concrete solutions. Each proposal must be actionable:
- "Add anti-pattern X to agent Y's prompt" (not "improve agent Y")
- "Create a reference file for Z in skill W" (not "enhance skill W")
- "Modify Phase 3 of skill V to include check for Q" (not "make skill V better")

**Step 2: Estimate effort**

| Effort | Definition |
|--------|-----------|
| Small | Single file edit, <30 lines changed |
| Medium | 2-5 files, new reference or script, <200 lines |
| Large | New skill or agent, multiple components, >200 lines |

**Step 3: Check for duplicates**

```bash
# Verify proposals don't duplicate existing capabilities
cat skills/INDEX.json | python3 -c "import sys,json; idx=json.load(sys.stdin); [print(k,'-',v.get('description','')) for k,v in idx.get('skills',{}).items()]" 2>/dev/null || echo "INDEX.json parse failed -- check manually"
```

Drop any proposal that duplicates an existing skill or capability. If an existing skill could be extended instead, frame the proposal as an extension.

**Step 4: Rank proposals**

Rank by: (Impact score) x (1 / Effort score), where High=3, Medium=2, Low=1 and Small=1, Medium=2, Large=3. Higher rank = better return on investment.

Output: ranked list of 5-10 proposals, each with:
- **Proposal**: 2-4 sentence description
- **Scope**: What files/skills are affected
- **Effort**: Small/Medium/Large
- **Expected outcome**: What measurably improves

**Gate**: All proposals are concrete (specific files/skills named), non-duplicative (verified against INDEX.json), and ranked. Proceed with the top 5.

---

### Phase 3: CRITIQUE -- Multi-persona evaluation

**Goal**: Evaluate proposals from multiple perspectives to surface blind spots.

**Step 1: Check for multi-persona-critique skill**

```bash
test -f skills/multi-persona-critique/SKILL.md && echo "AVAILABLE" || echo "NOT AVAILABLE"
```

**Step 2a: If multi-persona-critique is available**

Invoke it with the ranked proposals:

```
Skill(skill="multi-persona-critique", args="Evaluate these toolkit improvement proposals: {proposals}")
```

Collect consensus ratings and proceed to Step 3.

**Step 2b: If multi-persona-critique is NOT available -- use inline fallback**

Dispatch 3 parallel agents, each with a distinct evaluator perspective:

**Pragmatist**: "You are a pragmatist engineer. Evaluate each proposal on: implementation feasibility, time-to-value, and risk of unintended side effects. Rate each STRONG/MODERATE/WEAK with one sentence of justification."

**Purist**: "You are an architecture purist. Evaluate each proposal on: design coherence with existing toolkit patterns, long-term maintainability, and whether it solves a root cause vs a symptom. Rate each STRONG/MODERATE/WEAK with one sentence of justification."

**User Advocate**: "You are a user advocate. Evaluate each proposal on: how often real users hit this problem, whether the solution reduces friction, and whether it introduces new complexity users must learn. Rate each STRONG/MODERATE/WEAK with one sentence of justification."

**Step 3: Synthesize consensus**

For each proposal, compute a consensus score:
- STRONG = 3, MODERATE = 2, WEAK = 1
- Average across personas
- Score >= 2.5 = STRONG consensus
- Score 1.5-2.4 = MODERATE consensus
- Score < 1.5 = WEAK consensus (shelve)

Output: ranked proposals with consensus scores, key concerns from each persona, and notable disagreements.

**Gate**: All personas have reported. Synthesis complete. At least 1 proposal rated STRONG. If no STRONG proposals, revisit Phase 2 with the critique feedback, or report to user that no high-confidence improvements were found this cycle.

**On early exit (no STRONG proposals): always record to the learning DB before stopping.** Do not skip this step — the learning DB accumulates diagnostic value across cycles only if every cycle records, including null-result ones.

```bash
python3 ~/.claude/scripts/learning-db.py learn \
  --topic "evolution-cycle" \
  "early-exit: no STRONG proposals found. {N} proposals evaluated ({list of titles}). Top scores: {top_score}. Consider: {what prevented STRONG consensus}."
```

This ensures future diagnosis phases can query `evolution-cycle` to detect recurring proposal types that consistently fail consensus, rather than re-proposing the same ideas each cycle.

---

### Phase 4: BUILD -- Implement winners

**Goal**: Implement the top 1-3 STRONG-rated proposals on isolated feature branches.

**Constraint**: Maximum 3 implementations per cycle. Focus over breadth -- doing 3 well beats doing 7 poorly.

**Step 1: Select winners**

Take the top 1-3 proposals rated STRONG by consensus. If fewer than 3 are STRONG, take only the STRONG ones -- do not pad with MODERATE proposals.

**Step 2: Dispatch implementation agents**

For each winner, dispatch an appropriate agent in an isolated context:

| Proposal type | Implementation approach |
|--------------|----------------------|
| New skill | Use skill-creator methodology: draft SKILL.md, create references, structure directory |
| Skill modification | Read the target skill, apply the specific change, validate structure |
| New hook | Create hook script, register in settings.json (deploy hook files BEFORE registering) |
| Routing change | Update routing tables, verify with routing-table-updater |
| New reference file | Write the reference, add pointer in the parent skill's SKILL.md |
| Agent modification | Edit agent prompt, preserve frontmatter and routing metadata |

Each implementation must:
- Create a feature branch: `feat/evolve-{proposal-slug}`
- Make the minimal set of changes described in the proposal
- Commit with a descriptive message explaining what and why

**Step 3: Validate implementations**

For each implementation:
```bash
# Verify the skill structure if a skill was created/modified
python3 -m scripts.skill_eval.quick_validate skills/{skill-name} 2>/dev/null || echo "Validation script not available -- manual review"

# Verify no syntax errors in Python scripts
python3 -m py_compile {script} 2>/dev/null

# Verify shell scripts
bash -n {script} 2>/dev/null
```

**Gate**: All implementations committed on feature branches. Basic validation passed. Proceed to testing.

---

### Phase 5: VALIDATE -- A/B test implementations

**Goal**: Empirically verify that each implementation improves outcomes vs baseline.

**Step 1: Create test cases**

For each implementation, create 3-5 realistic test prompts that exercise the changed behavior. These should be the kind of input that would trigger the relevant skill or agent in production.

**Step 2: Run comparisons**

Use the skill-eval or agent-comparison methodology:
- **Baseline**: Run test prompts against the current (unmodified) toolkit
- **Candidate**: Run test prompts against the branch with the implementation

If skill-eval's evaluation modes are available:
```bash
python3 -m scripts.skill_eval.run_eval \
  --eval-set test-cases.json \
  --skill-path skills/{skill-name} \
  --runs-per-query 3 \
  --verbose
```

If automated comparison is not available, fall back to:
- Run each test prompt manually with and without the change
- Use a grader agent to score both outputs on relevant dimensions (correctness, completeness, actionability)

**Step 3: Evaluate results**

Win condition for each implementation:
- 60%+ of test cases show improvement on at least one dimension
- No dimension regressed by more than 1 point (on a 5-point scale)
- No new failures introduced

Mark each implementation as WIN or LOSS.

**Gate**: All implementations tested. Win/loss determined for each. Evidence recorded.

---

### Phase 6: EVOLVE -- Promote winners and record learnings

**Goal**: Ship winners via PR, record all outcomes in the learning database.

**Step 1: Handle winners (WIN status)**

For each winning implementation, create a PR, run pr-review, and merge:

```bash
git push -u origin feat/evolve-{proposal-slug}
gh pr create \
  --title "feat: {short description of improvement}" \
  --body "## Summary
- Evolution cycle proposal: {proposal description}
- Consensus score: {score} (Pragmatist: {rating}, Purist: {rating}, User Advocate: {rating})
- A/B result: {win rate}% improvement across {N} test cases

## Changes
{list of specific changes}

## Test Results
| Test Case | Baseline | Candidate | Delta |
|-----------|----------|-----------|-------|
| ... | ... | ... | ... |

## Evolution Cycle
This PR was generated and validated by the toolkit-evolution skill."
```

After creating the PR, run pr-review to validate, then merge:

```bash
# Review the PR (catches issues the A/B test may have missed)
# Use the pr-workflow skill's review capability
gh pr merge {pr-number} --squash --delete-branch
```

The multi-persona critique + A/B testing gate is the review. If a proposal passed both with STRONG consensus and WIN status, it has been validated more rigorously than most human reviews. Auto-merge is safe because the validation happened before this step, not after.

**Step 1b: Clean up the feature branch after merge**

`gh pr merge ... --squash --delete-branch` handles branch deletion when gh auth is available. As a paranoid safeguard, verify the remote branch is gone:

```bash
# Verify remote branch was removed (or remove it manually if still present)
BRANCH_NAME="feat/evolve-{proposal-slug}"
if git ls-remote --heads origin "$BRANCH_NAME" | grep -q "$BRANCH_NAME"; then
  git push origin --delete "$BRANCH_NAME" && echo "Remote branch deleted: $BRANCH_NAME" \
    || echo "WARNING: could not delete remote branch $BRANCH_NAME -- delete manually"
else
  echo "Remote branch already cleaned up: $BRANCH_NAME"
fi
```

Also clean up any stranded remote evolution branches from cycles where gh auth was unavailable and PRs were never created:

```bash
# Find remote evolution branches older than 14 days that were never merged
git fetch --prune origin 2>/dev/null
git branch -r --merged origin/main | grep "origin/feat/evolve-" | while read branch; do
  remote="${branch#origin/}"
  git push origin --delete "$remote" 2>/dev/null && echo "Cleaned up merged branch: $remote" || true
done
```

**Step 2: Handle losers (LOSS status)**

Record what was tried and why it failed:

```bash
python3 ~/.claude/scripts/learning-db.py learn \
  --topic "evolution-result" \
  "Failed proposal: {description}. Hypothesis: {what we expected}. Result: {what happened}. Lesson: {what we learned}."
```

Failed experiments are valuable data -- they prevent the same idea from being re-proposed in future cycles.

**Step 3: Record the full cycle**

```bash
python3 ~/.claude/scripts/learning-db.py learn \
  --topic "evolution-cycle" \
  "toolkit-evolution cycle: {N} proposals evaluated, {M} built, {W} winners, {L} losses. Top win: {description}. Focus: {area or 'general'}."
```

**Step 4: Write evolution report**

Write a dated report using the template in `references/evolution-report-template.md`:

```bash
# Write to project-local evolution-reports directory (gitignored)
# Path: evolution-reports/evolution-report-{YYYY-MM-DD}.md
```

Read the template, fill in all sections with data from this cycle, and write the report.

**Gate**: Winners merged. Learnings recorded for all proposals (wins and losses). Evolution report written. Cycle complete.

---

## Scheduling

### Manual invocation

```
/evolve
/evolve routing
/do evolve toolkit
/do evolve hooks
```

### Cron setup (nightly)

Runs nightly at 3:07 AM, after auto-dream (2:07 AM) finishes consolidating learnings:

```bash
python3 ~/.claude/scripts/crontab-manager.py add \
  --tag "toolkit-evolution" \
  --schedule "7 3 * * *" \
  --command "/home/feedgen/claude-code-toolkit/scripts/toolkit-evolution-cron.sh --execute >> /home/feedgen/claude-code-toolkit/cron-logs/toolkit-evolution/cron.log 2>&1"
```

Schedule uses 3:07 AM (off-minute per cron best practice, 1 hour after auto-dream). Budget set to $5.00 per run.

---

## Anti-Patterns

- **Improving without measuring** -- every change must have a baseline and A/B result. "It looks better" is not evidence.
- **Merging without validation** -- every winner must pass multi-persona critique (STRONG consensus) AND A/B testing (WIN status) before merge. The validation gates are the review.
- **Ignoring negative results** -- failed experiments are valuable data. Record them in the learning DB so the same idea is not re-proposed.
- **Improving everything at once** -- max 3 implementations per cycle. Focus compounds; scatter dissipates.
- **Running without diagnosis** -- do not propose solutions without evidence of problems first. Solutions looking for problems create phantom work.
- **Proposing duplicates** -- always check INDEX.json before proposing a new skill or capability. Extend existing skills when possible.
- **Discovery without evidence** -- the DISCOVER phase requires concrete data points (routing misses, manual workflows, community requests), not speculation. "It might be useful" is not a valid justification.
- **Discovering too often** -- discovery runs monthly, not nightly. Running it every cycle wastes budget on perspective agents that will produce the same gaps repeatedly.

---

## Error Handling

### Error: "learning-db.py not found"
Cause: Learning database scripts not installed.
Solution: The learning DB is at `~/.claude/scripts/learning-db.py`. If missing, skip learning DB queries and rely on git log + dream reports for diagnosis. Record this gap as an improvement opportunity.

### Error: "No dream reports found"
Cause: Auto-dream has not run yet or state directory is empty.
Solution: Proceed without dream insights. Use git log and learning DB as primary data sources. Note that enabling auto-dream would improve future evolution cycles.

### Error: "No STRONG proposals after critique"
Cause: All proposals received MODERATE or WEAK consensus.
Solution: Report to the user that no high-confidence improvements were found this cycle. Record the proposals and critique feedback in the evolution report for future reference.

### Error: "A/B test inconclusive"
Cause: Test cases don't discriminate between baseline and candidate.
Solution: Review test case quality. Non-discriminating tests ("file exists") provide false signal. Write tests that exercise the specific behavior the proposal changes. If still inconclusive after better tests, shelve the proposal.

### Error: "Feature branch conflicts"
Cause: Multiple evolution implementations touch the same files.
Solution: Reduce to 1 implementation per cycle when conflicts arise. Alternatively, sequence implementations so later ones branch from earlier ones.

---

## Cost Estimate

A full evolution cycle runs all 7 phases and may dispatch multiple subagents. Estimated cost:
- Discovery (Phase 0, monthly): ~$0.50-0.75 (5 parallel perspective agents + dedup)
- Diagnosis + Proposal: ~$0.15 (reading files, querying DBs)
- Critique: ~$0.30 (3 persona agents evaluating proposals)
- Build: ~$0.50-1.50 (1-3 implementation agents)
- Validate: ~$0.50-1.50 (A/B test runs)
- Evolve: ~$0.10 (PR creation, learning DB writes)

Total without discovery: ~$1.50-3.50 per cycle. With discovery: ~$2.00-4.25.
Budget capped at $5.00 via wrapper script.
Nightly cost at full utilization: ~$45-105/month. Discovery adds ~$0.50-0.75/month (runs monthly, not nightly). Cycles with no STRONG proposals exit early (diagnosis + proposal only: ~$0.45).

---

## References

- `references/evolution-report-template.md` -- Template for the evolution report
- `skills/auto-dream/SKILL.md` -- Nightly sibling: memory consolidation and learning graduation
- `skills/skill-eval/SKILL.md` -- Skill testing and benchmarking
- `skills/multi-persona-critique/SKILL.md` -- Multi-persona evaluation (may not exist yet; inline fallback provided)
- `skills/skill-creator/SKILL.md` -- Skill creation methodology
- `skills/agent-comparison/SKILL.md` -- A/B testing methodology
- `skills/headless-cron-creator/SKILL.md` -- Cron job creation patterns
