# Pause-Work Extract Learnings

Verbatim Phase 3 (EXTRACT LEARNINGS) detail. Query session learnings from learning.db, filter for architectural decisions that warrant ADRs, and draft ADR skeletons for each candidate. This phase runs before WRITE so that ADR data is available for inclusion in both handoff files — passing extracted data downstream is cheaper than appending to files after the fact.

## Step 1: Query session learnings

```bash
python3 ~/.claude/scripts/learning-db.py query --format json --limit 20
```

`learning-db.py` has no `--since` flag, so query recent entries and filter by recency. Use the `created_at` field in the JSON output to identify entries recorded during this session — the most recent entries are the ones this session produced.

## Step 2: Filter for ADR candidates

Apply this heuristic to determine which learnings describe architectural decisions vs. incidental tips:

| Learning pattern | ADR candidate? |
|-----------------|----------------|
| "After X, always do Y" | Yes — process decision |
| "X depends on Y" | Yes — contract/coupling |
| "Use A instead of B because C" | Yes — architectural choice |
| "X is faster than Y" | Maybe — only if it changes approach |
| "Use --flag for better output" | No — tip, not decision |

Keep only entries that describe process changes, tooling contracts, or architectural choices. Tips and incidental observations don't warrant ADRs because they don't reflect decisions that constrain future work — capturing them as ADRs would dilute the ADR corpus and create noise in architecture documentation.

## Step 3: Draft ADR skeletons (only if candidates found)

Get the next safe ADR number once, then increment for subsequent candidates:
```bash
python3 ~/.claude/scripts/adr-query.py next-number 2>/dev/null || echo "manual"
```

Call `next-number` once for the first candidate. For additional candidates, increment the number manually (e.g., if first returns 132, use 133 for the second) because the script checks existing files on disk and the first skeleton has not been committed yet.

If `adr-query.py` returns "manual", use placeholder numbers and note that the user should assign them before merging.

Draft to `adr/{number}-{slug}.md`:

```markdown
# ADR-{number}: {Title from learning}

**Status**: Proposed
**Date**: {today}
**Source**: Auto-extracted from session learning (confidence: {confidence})

## Context
{Context derived from the learning entry}

## Decision
{Decision derived from the learning pattern}

## Validation Criteria
- [ ] {Criterion derived from the decision}
```

Write the file to disk so it is visible in the next session even if Phase 4 fails.

## Step 4: Pass ADR data to Phase 4

Construct a `drafted_adrs` list in memory for use during the WRITE phase:
- If candidates were found: list of `{"number": N, "path": "adr/N-slug.md", "title": "..."}` entries
- If no candidates found: empty list — skip silently, no empty sections in output files
