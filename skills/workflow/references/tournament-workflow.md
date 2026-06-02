<!-- pairs_with: workflow, decision-helper -->

# Tournament Workflow (TEMPLATE)

A **template**, not a runnable script. Use it to compose a pairwise-comparison workflow when comparative judgment beats absolute scoring. Referenced from `workflow-patterns.md` (Pattern 5).

**Terminology:** "workflow" is canonical; "pipeline" is the legacy alias for the same concept. Not registered as a routing pipeline — no `pipeline-index.json` key, no `meta.name` export. Additive only.

## When to Use

The blog rule: **comparative judgment beats absolute scoring.** Humans and LLMs rank a pair reliably but score one item on an absolute scale poorly. Use a tournament for: sorting/ranking candidates, exploration where "taste" decides, and evals with no fixed rubric.

Contrast with the absolute-scoring tools we already have — do not duplicate them:

| Tool | Method | Use when |
|---|---|---|
| `decision-helper` | Weighted absolute scoring of options against criteria | Criteria are explicit and weights known |
| `multi-persona-critique` | 5 personas score, then consensus | One artifact, multi-lens absolute judgment |
| **tournament (this file)** | Pairwise winner per round, bracket to one survivor | No reliable absolute rubric; ranking by comparison |

## Pattern

1. **Generate:** N agents attempt the SAME task different ways — they compete, they do not divide the work.
2. **Pair:** a judging agent receives two candidates and picks the winner. Comparative prompt only ("which is better and why"), no absolute score.
3. **Bracket:** a deterministic elimination loop holds rounds; winners advance until one survives.

```
candidates = [agent(task, seed=i) for i in range(N)]   # compete on the same task
round = candidates
while len(round) > 1:
    pairs = chunk(round, 2)                              # deterministic pairing
    round = [judge(a, b) for (a, b) in pairs]            # pairwise winner
winner = round[0]
```

Keep the bracket deterministic (fixed seeding, odd item byes carried forward) so the run is reproducible. The judge is comparative only; never ask it for an absolute 1–10 score — that reintroduces the weakness the tournament avoids.

## Pair-with

- `workflow-patterns.md` — the catalog entry that points here.
- `decision-helper` / `multi-persona-critique` — pick those instead when an absolute rubric exists.
