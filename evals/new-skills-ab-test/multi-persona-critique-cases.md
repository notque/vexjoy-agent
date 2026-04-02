# Multi-Persona Critique: A/B Test Cases

## Test Design

Three-way comparison:
- **Variant A**: multi-persona-critique skill (5 philosophical personas)
- **Variant B**: existing `roast` skill (5 HackerNews personas with claim validation)
- **Variant C**: plain evaluation (no critique skill loaded)

Each case presents a set of proposals. All three variants evaluate the same proposals. Outputs are randomized to labels X/Y/Z before blind evaluation.

## Evaluation Criteria

| Criterion | Score 1 | Score 3 | Score 5 |
|-----------|---------|---------|---------|
| Insight density | Only surface observations | Mix of obvious and non-obvious | Multiple non-obvious insights per proposal |
| Disagreement quality | Personas echo each other | Some genuine disagreement | Disagreements illuminate real tradeoffs |
| Synthesis usefulness | Summary just restates individual critiques | Organized but not actionable | Actionable priorities with clear reasoning |
| Trap detection | Misses hidden flaws entirely | Notices something is off but can't articulate it | Identifies the specific flaw and explains its impact |

---

## Case 1: Clear winner -- Skill description optimization (Convergence test)

**Proposals to evaluate**:

**Proposal A**: Improve the `roast` skill's description by adding more trigger keywords:
> Change from: "Constructive critique via 5 HackerNews personas with claim validation."
> Change to: "Constructive critique via 5 HackerNews personas with claim validation. Use for devil's advocate analysis, stress testing ideas, poking holes in proposals, challenging assumptions, and getting honest feedback on code, designs, or plans."

**Proposal B**: Improve the `roast` skill by reducing its description to the minimum:
> Change from: "Constructive critique via 5 HackerNews personas with claim validation."
> Change to: "Critique tool."

**Expected outcome**: Proposal A should clearly win. Proposal B strips too much context for trigger matching.

**What good critique looks like**:
- All personas converge on Proposal A being better
- Identifies that Proposal B would break trigger matching (skill-eval framework relies on description for routing)
- Notes that Proposal A adds useful trigger surface without bloating
- Maybe raises a concern about description length limits (1024 chars from quick_validate)

**What bad critique looks like**:
- Personas can't distinguish between the proposals
- Debates style preferences without mentioning functional impact on routing
- Misses the trigger-matching implication entirely

---

## Case 2: Clear winner -- Hook timeout configuration (Convergence test)

**Proposals to evaluate**:

**Proposal A**: Set all hook timeouts to 30 seconds to ensure nothing times out:
> Update all `timeout` values in settings.json hooks to 30000ms.

**Proposal B**: Set timeouts proportional to each hook's actual measured execution time, with a 2x safety margin:
> Profile each hook, set timeout to `max(measured_p99 * 2, 3000)`.

**Expected outcome**: Proposal B should clearly win. Proposal A masks performance regressions.

**What good critique looks like**:
- Identifies that Proposal A's uniform high timeout hides performance regressions
- Notes Proposal B's data-driven approach surfaces problems early
- Recognizes that 30s timeouts would make the pre-tool hooks block the user for unacceptable durations
- May note that Proposal B requires profiling infrastructure that may not exist yet

**What bad critique looks like**:
- Treats both as reasonable alternatives without identifying the performance masking issue
- Focuses on implementation difficulty rather than design quality

---

## Case 3: Genuinely ambiguous -- Learning DB storage format (Disagreement test)

**Proposals to evaluate**:

**Proposal A**: Keep the current SQLite + FTS5 approach for the learning database:
> SQLite is embedded, zero-config, fast enough for the volume of learnings we store. FTS5 gives us full-text search. The scripts already work. Ship stability.

**Proposal B**: Migrate the learning database to a structured JSON directory:
> One JSON file per learning entry in `~/.claude/learnings/`. Easier to inspect, git-trackable, no binary format lock-in. Simpler mental model. Trade query speed for transparency.

**Expected outcome**: Genuinely ambiguous. Both have real strengths. The critique should surface the tradeoffs, not declare a winner.

**What good critique looks like**:
- Personas genuinely disagree (some favor stability, some favor transparency)
- Surfaces specific tradeoffs: query performance vs inspectability, binary format vs git-trackability
- Raises questions neither proposal addresses (e.g., what about concurrent access? what about migration path?)
- The synthesis acknowledges the ambiguity instead of forcing a recommendation

**What bad critique looks like**:
- Forces a winner when the tradeoffs are genuinely balanced
- Personas all agree without real tension
- Misses the concurrent access concern (Claude Code sessions can overlap)

---

## Case 4: Genuinely ambiguous -- Agent isolation strategy (Disagreement test)

**Proposals to evaluate**:

**Proposal A**: Use git worktrees for agent isolation (current approach):
> Each agent gets its own worktree via `git worktree add`. Clean filesystem isolation. Agents can commit independently. Worktrees are cleaned up after.

**Proposal B**: Use Docker containers for agent isolation:
> Each agent runs in a lightweight container with the repo mounted read-only. Writes go to an overlay filesystem. Stronger isolation guarantees. Container cleanup is atomic.

**Expected outcome**: Genuinely ambiguous. Worktrees are simpler and already implemented. Containers are more isolated but add infrastructure complexity.

**What good critique looks like**:
- Surfaces the simplicity-vs-isolation tradeoff explicitly
- Notes worktrees have a known failure mode (branch confusion, leaked changes -- referenced in worktree-agent skill)
- Notes containers add Docker dependency that many Claude Code users don't have
- Raises the question of whether the failure modes of worktrees are frequent enough to justify the migration cost
- Personas disagree based on different value weightings (simplicity vs safety)

**What bad critique looks like**:
- Defaults to "containers are more secure therefore better" without weighing migration cost
- Ignores that the worktree approach is already implemented and working
- Doesn't acknowledge the Docker dependency issue

---

## Case 5: Hidden trap -- Caching skill descriptions for faster routing (Trap detection)

**Proposals to evaluate**:

**Proposal A**: Cache parsed SKILL.md frontmatter in a `skill-cache.json` file at startup:
> Parse all SKILL.md files once when Claude Code starts, store the parsed frontmatter (name, description, triggers) in `.claude/skill-cache.json`. The router reads the cache instead of parsing markdown on every request. Faster routing, especially with 100+ skills.

**Proposal B**: Keep parsing SKILL.md files on every routing request (current approach):
> Parsing YAML frontmatter from ~100 markdown files takes < 50ms. The bottleneck in routing is LLM inference (seconds), not file parsing (milliseconds). Keep it simple.

**Expected outcome**: Proposal A sounds good (performance optimization!) but has a fatal flaw: the cache becomes stale when skills are modified during a session. This toolkit frequently modifies skills (skill-creator, skill-eval optimize loop, manual edits). A stale cache would cause routing to use outdated descriptions, potentially routing to the wrong agent or missing new triggers. Proposal B is correct: the optimization addresses a non-bottleneck.

**The hidden trap in Proposal A**:
1. Cache staleness: Skills are modified during sessions (skill-creator loop, manual edits)
2. Premature optimization: File parsing is ~50ms vs LLM routing at ~3-5 seconds
3. Cache invalidation complexity: Would need file watchers or manual invalidation
4. Phantom problem: "Future-proofing for 100+ skills" when the toolkit has ~80 and parsing is fast

**What good critique looks like**:
- At least one persona identifies the cache staleness problem
- Recognizes the premature optimization (50ms vs 3-5s LLM time)
- Connects to the toolkit's own anti-patterns: YAGNI, phantom problem detection
- Notes that cache invalidation is a known hard problem
- Proposal B wins despite being "do nothing" because the optimization is unnecessary

**What bad critique looks like**:
- Endorses Proposal A because "caching is always good for performance"
- Misses the staleness issue entirely
- Doesn't check whether the performance bottleneck is real
- Falls for the "100+ skills" future-proofing framing
