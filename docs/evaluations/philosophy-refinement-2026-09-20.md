# Philosophy refinement: 2026-09-20

`docs/PHILOSOPHY.md` was reduced from 1,221 to 817 words (33.1%) while retaining the operational contracts lost by the rejected 2026-09-04 candidates.

## Method

- Split the original into its opening and seven `##` sections.
- Sent each segment separately to Jev with only its heading, text, and the document goal.
- Asked exactly 50 independent questions per segment: 400 local judgments total.
- Drafted one complete candidate; did not assemble independently optimized sentences.
- Compared the complete original and candidate with the same 50-question battery over three frozen repeats.
- Treated old evaluation cases as exposed regression evidence, not a fresh blind holdout.

## Segment results

| Segment | Jev disposition | Main action |
|---|---|---|
| Opening thesis | Tighten (94%) | Remove volatile framing; retain ordinary-request outcome |
| Understand and carry out the request | Tighten (59%) | Keep invisible capability discovery and task continuity |
| Add expertise where it changes the work | Tighten (56%) | Keep evidence standard; compress storage and routing mechanics |
| Use programs for repeatable operations | Tighten (88%) | Modernize the model/program boundary around current evidence |
| Install plugins through the Claude CLI | Move (61%) | Remove the runbook from core philosophy |
| Match structure to failure and recovery | Tighten (64%) | Keep recovery and artifact-checkpoint contracts; compress governance procedure |
| Respect authority and verify outcomes | Tighten (79%) | Preserve authority and observable-verification boundaries |
| Improve the toolkit with evidence | Move (66%) | Keep durable evidence rules; move changing procedure and history out of core |

## Preserved regression contracts

The candidate explicitly retains:

- ordinary requests should not require internal component names;
- a program inventories required artifacts and verifies coverage and counts before synthesis;
- missing or conflicting evidence is surfaced and prerequisites are repaired;
- uncertain heuristics begin advisory and require demonstrated value plus explicit governance before blocking;
- recurrence alone does not establish durable knowledge;
- hooks and prompts do not prove scheduling, arbitration, enforcement, or budgets;
- historical model results do not establish current capability;
- negative results retain scope, decision, and a concrete evidence location;
- activity and low use are not value measures by themselves.

## Complete-document comparison

Across three frozen repeats, Jev preferred the candidate on the overall completeness/currentness/concision tradeoff with 72.7% mean probability, versus 26.3% for the original and 1.0% tie. It strongly favored the candidate for:

- rechecking model-era assumptions: 99.7%;
- separating operations from core philosophy: 90.3%;
- selecting models versus programs from current evidence: 84.3%;
- value rather than activity metrics: 83.0%;
- smallest complete context: 72.3%.

The absolute `prefer_candidate` Noul was only 39%. This does not algebraically contradict the relative Choice: they are different primitives asking absolute and comparative questions. The comparative Choice was the decision-relevant primitive for the A/B selection.

Jev assigned 70.3% probability that another reduction of similar size would risk material loss. Iteration stopped rather than optimizing further for brevity.

## Validation

- `python3 scripts/validate-doc-links.py` — pass, 213 links.
- `python3 scripts/validate-doc-commands.py` — pass, 39 commands.
- `python3 scripts/check-whitespace.py docs/PHILOSOPHY.md` — pass.
- `git diff --check -- docs/PHILOSOPHY.md` — pass.
- `python3 scripts/validate-doc-counts.py` — passed after the related README inventory correction (165 scripts).

No fresh blind semantic holdout was run. The revision has deterministic validation and exposed-regression review, not new evidence that every downstream interpretation improves.
