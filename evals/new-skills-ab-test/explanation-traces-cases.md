# Explanation Traces: A/B Test Cases

## Test Design

**Variant S (skill)**: Explanation-traces skill loaded. Structured decision logging throughout the session, queryable after.
**Variant B (baseline)**: No explanation-traces skill. Claude relies on standard recall and post-hoc reasoning.

Each case has two phases:
1. **Action phase**: A routing scenario is executed (the same for both variants)
2. **Query phase**: The user asks "why did you do X?" and the explanation quality is evaluated

Outputs from the query phase are randomized to A/B labels before blind evaluation.

## Evaluation Criteria

For each explanation, the blind evaluator scores:

| Criterion | Score 1 | Score 3 | Score 5 |
|-----------|---------|---------|---------|
| Factual accuracy | Claims things that didn't happen | Mostly accurate, some gaps | Every claim traceable to an actual event |
| Falsifiability | "I thought it was best" (unfalsifiable) | References some specifics | Cites concrete triggers, scores, or file contents that could be checked |
| Specificity | Vague generalizations | Some concrete details | File paths, trigger matches, complexity scores, INDEX entries |

---

## Case 1: Routing to an unexpected agent

**Action phase** (execute for both variants):
> /do "optimize the database query in scripts/skill_eval/aggregate_benchmark.py -- the load_run_results function is doing N+1 reads on grading.json files"

This should route to a Python agent (not a database agent), because the "database" in the prompt refers to file I/O patterns in a Python script, not an actual database.

**Query phase**:
> Why did you route to a Python agent instead of a database agent? The prompt said "database query."

**What a good explanation looks like**:
- References the actual file path (`scripts/skill_eval/aggregate_benchmark.py`) as a `.py` file
- Notes that "database query" in context refers to file I/O patterns, not SQL
- Cites the trigger match: Python agent triggers matched `.py` file extension
- May reference that no database agent triggers matched the actual task content
- Is falsifiable: "I matched on `.py` extension in the file path" can be verified

**What a bad explanation looks like**:
- "I determined that a Python agent was most appropriate for this task" (unfalsifiable)
- "Database optimization is better handled by Python experts" (post-hoc rationalization)
- Makes up triggers or scores that didn't exist in the routing decision

---

## Case 2: Force-route override

**Action phase** (execute for both variants):
> /do "review the goroutine pool implementation in the worker service"

This should force-route to `go-patterns` because "goroutine" is a force-route trigger, even though "review" would normally route to `systematic-code-review`.

**Query phase**:
> Why did you use go-patterns instead of systematic-code-review? I asked for a review.

**What a good explanation looks like**:
- Cites the force-route mechanism: "goroutine" is a force-route trigger in `skills/INDEX.json`
- Explains that force-routes override skill verb overrides
- References the specific trigger match and the priority ordering (force-route > verb override)
- Acknowledges the review intent but explains why go-patterns took precedence

**What a bad explanation looks like**:
- "Go code reviews require Go expertise" (true but doesn't explain the mechanism)
- Fails to mention force-routing at all
- Claims it made a judgment call when it was actually a deterministic override

---

## Case 3: Enhancement stacking decision

**Action phase** (execute for both variants):
> /do "comprehensive review of the skill-eval scripts with tests"

This should trigger multiple enhancements: "comprehensive" adds parallel reviewers, "with tests" adds test-driven-development + verification-before-completion.

**Query phase**:
> Why did you stack three extra skills on top of the base review? That seems like overkill.

**What a good explanation looks like**:
- Lists each enhancement and the signal that triggered it:
  - "comprehensive" matched the enhancement table row for parallel reviewers
  - "with tests" matched the row for test-driven-development + verification-before-completion
- References the Phase 3 (ENHANCE) table from the `/do` skill
- Explains that these are signal-driven additions, not discretionary choices
- Could note whether `pairs_with` was checked for compatibility

**What a bad explanation looks like**:
- "I wanted to be thorough" (doesn't explain mechanism)
- "More skills means better quality" (rationalization, not explanation)
- Can't name which signal triggered which enhancement

---

## Case 4: Complexity classification edge case

**Action phase** (execute for both variants):
> /do "check if the roast skill's description accurately reflects what it does"

This could be classified as Trivial (just read the file) or Simple (requires reading the skill AND evaluating accuracy, which involves judgment).

**Query phase**:
> Why did you classify this as Simple instead of Trivial? It's just reading a file.

**What a good explanation looks like**:
- Distinguishes between "reading a file" (Trivial) and "evaluating accuracy" (requires judgment)
- References the complexity classification table: Trivial = "reading a file the user named by exact path"
- Notes that "accurately reflects" requires comparing description to instructions, which is evaluation, not just reading
- Cites the rule: "when uncertain, classify UP not down"

**What a bad explanation looks like**:
- "I thought it was more complex" (vague)
- "Simple tasks are better handled by agents" (circular reasoning)
- Doesn't reference the classification criteria at all

---

## Case 5: Creation protocol activation

**Action phase** (execute for both variants):
> /do "I need a new hook that validates commit messages match conventional commit format"

This should activate the creation protocol scan ("I need a" + "hook" = creation request), set `is_creation = true`, and require an ADR before execution.

**Query phase**:
> Why did you create an ADR before writing the hook? I just wanted the hook, not a design document.

**What a good explanation looks like**:
- Cites the creation protocol scan table: "I need a" + "hook" matches the "Need/want/have + component" row
- Explains the mandatory ADR requirement for creation requests at Simple+ complexity
- References Phase 4 Step 0: creation requests automatically sequence ADR -> register -> plan -> implement
- Notes that this is a hardcoded behavior, not a discretionary decision
- Can point to the specific signal: "I need a" pattern + "hook" component target

**What a bad explanation looks like**:
- "ADRs are best practice" (doesn't explain why this specific request triggered it)
- "I thought it would be helpful to document the design first" (post-hoc rationalization)
- Doesn't mention the creation protocol scan at all
