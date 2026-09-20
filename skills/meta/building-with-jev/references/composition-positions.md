# Composition positions

A Jev judgment occupies one of 11 positions relative to a function F.

| # | Position | Form | Governing rule | Script |
|---|----------|------|----------------|--------|
| 1 | Operand | `F(Jev(...))` — probability feeds F | Version question defs with the consumer; it is a belief, not a natural quantity | none |
| 2 | Post-judge | `F(x) -> Jev judges result` | Only the post-judge sees what the call printed; a pre-gate cannot | `jev-browser-verify.py` |
| 3 | Gate | `if Jev(x): apply F` | A gate is a filter, not authorization; validate operation+target in code; every error path fails open | none in this repo yet |
| 4 | Selector | Jev picks which F runs | Dispatch stays in code; per-option consequences are your cost model; confidence-gate the selection | `jev-route.py` |
| 5 | Comparator | Semantic sort key inside rank/sort | Comparability needs a shared rubric; measure recall separately from rerank quality | none in this repo yet |
| 6 | Prior | Jev seeds a deterministic refinement | It is a heuristic prior, not a posterior; refine with real observations | none |
| 7 | State-estimator | Jev estimates probs; deterministic policy acts | The model never commands; interventions are enumerated in code | none in this repo yet |
| 8 | Metric | Jev as judge inside an optimizer loop | Optimizer metrics must be repeatable; verify judge variance on your data | `jev-harness.py` |
| 9 | Verifier | Jev judges spec-conformance | Verdicts are evidence, not enforcement; the checker enumerates requirements in code | `jev-browser-verify.py` |
| 10 | Discretizer | Unstructured state -> typed values code requires | Jev selects from candidates you produce; it never generates | `jev-browser-decide.py` |
| 11 | Bounds/budget | Jev decides how far to continue | Termination conditions stay conservative and code-owned | `jev-compact.py` |

## Logical operators

- **Negation**: ask one question in the form code branches on. Code may compute `1 - p(X)` from that same answer; a separately asked `not X` Noul is another judgment and need not equal the complement. Double negatives cost accuracy.
- **AND / OR over parallel Nouls**: combine in code with an explicit labeled policy. Never multiply — same-state answers are not independent.
- **FOR-ALL / EXISTS**: batch one Noul per item in one request, then aggregate in code (`min` = AND, `max` = EXISTS) with an explicit escalation rule.
- **Chains**: decompose into gate -> act -> post-judge. Never encode multi-hop logic in one question.

## Walk the positions (dissolving a skill phase)

1. Pick the construct (operator, algorithm, or workflow step) that the skill phase wraps.
2. Walk positions 1-11. For each: is there a judgment-shaped hole? Most are trivially no.
3. For each lit cell, apply the economics inversion: was this step previously infeasible because a judgment cost seconds and cents? If yes, it is a newly-feasible candidate.
4. Name the governing rule from the table and enforce it in code. No nameable rule means the cell is a metaphor.
5. Falsify: labeled cases, split A/B, judge-variance check. A candidate that survives becomes a catalog row.
