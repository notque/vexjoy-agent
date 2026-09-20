---
name: assessment
description: "Read-only inspection and decision support: codebase orientation, repository comparison, service health, ADR consultation, weighted decisions, and adversarial critique. Use review for code-change findings and workflow for implementation."
user-invocable: true
allowed-tools: [Read, Bash, Grep, Glob, Task, Agent]
routing:
  not_for: "code review with findings (use review), building or fixing (use workflow)"
  triggers:
    - "inspect without changing"
    - "read-only"
    - "codebase overview"
    - "repo value analysis"
    - "service health"
    - "consult on ADR"
    - "help me decide"
    - "decision matrix"
    - "devil's advocate"
    - "roast this"
  category: analysis
  pairs_with: [review, workflow, security]
---

# Assessment

Choose the narrowest mode that answers the request. Assessment is read-only: do
not create reports, clone repositories, alter ADRs, restart services, or write
consultation artifacts unless the user separately authorizes those mutations.
Inspection commands must not change the target. Cite file paths, command output,
or supplied evidence for material claims; label inferences.

## Inspection and codebase orientation

Honor repository instruction files before exploring. Do not open likely secrets
(`.env`, private keys, credential stores). Identify the stack from manifests,
then trace entry points, module boundaries, configuration, persistence, external
interfaces, tests, and one representative end-to-end flow. Prefer searches
derived from the detected stack over a fixed catalog. Limit broad scans and state
what was sampled.

For onboarding, report how to run and test the project when the repository gives
those commands; the few abstractions needed to navigate it; where the requested
kind of change belongs; and uncertainties plus evidence that would resolve them.

Do not convert frequency into a rule without enough independent examples.
Generated, vendored, test, and legacy code are separate populations. A convention
claim must include its numerator, denominator, and scope.

## Repository value analysis

Compare an external repository with the local system at the capability level,
not by counting similarly named files. Verify every proposed gap against the
local repository before recommending adoption. Classify it as `already covered`,
`partial`, or `missing`, and distinguish reusable mechanism from project-specific
surface. Report expected value, integration cost, and evidence. Do not clone or
implement unless authorized.

## Service health

Build a manifest from user input or existing definitions: process identity,
health source, port, and freshness threshold. Check independent signals when
available: process, health payload/freshness, and listener. Never infer health
from a health file alone.

| Evidence | Status |
|---|---|
| process absent | `DOWN` |
| process present; health missing or stale | `WARNING` |
| health reports error | `ERROR` |
| required connection absent beyond its configured threshold | `WARNING` |
| required port not listening | `ERROR` |
| all configured checks pass | `HEALTHY` |

Report the exact failed signal and observed value. Remediation is advisory; never
restart or mutate a service without explicit authorization. Endpoint and CVE
audits belong to their dedicated skills when available.

## ADR consultation

Read the full ADR and repository constraints. Obtain independent lenses in
parallel: premise/simpler alternative, user/operator burden, and system
coupling/failure concentration. Add domain specialists only when needed. Give
reviewers the same ADR snapshot; record its hash when persisting a consultation
so synthesis cannot silently mix revisions.

Synthesize evidence, not votes. Preserve each concern and severity. Any supported
blocking concern makes the result `BLOCKED`; `NEEDS_CHANGES` remains unresolved
until its condition is addressed. When artifacts are authorized, write reviewer
outputs before synthesis and synthesize from those files, not ephemeral task
returns. Never overwrite prior consultation files without confirmation.

## Weighted decision

Eliminate hard-constraint failures before ranking. Freeze criteria and weights
before scoring; if they change later, retain both runs. Compute
`sum(score * weight) / sum(weights)` in code and show uncertainty for inputs that
can change the winner. Persist only when the user requested a decision record.

## Adversarial critique

Choose lenses that create real tension for this target rather than fixed
personas. Give reviewers the same proposals and evidence, run them independently,
then map agreement, disagreement, hidden assumptions, and falsifying evidence.
Validate repository claims to file and line. Keep claims about the artifact
separate from rhetoric about its author. “Roast” changes tone, not the evidence
bar, read-only boundary, or authorization scope.

## Handoff

Lead with the answer and confidence. Include the smallest supporting evidence
set, important limitations, and the next decision—not an exhaustive exploration
diary. If asked to act, hand off to the skill that owns the mutation rather than
treating assessment as permission.
