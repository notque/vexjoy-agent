# Agent evaluation receipts

Persist exact input, frozen expectation, raw output, model/agent version,
tools available, exit/timeout status, and PASS/FAIL reason for every case.

For router tests, assert both the selected route and forbidden alternatives.
For reviewer tests, use seeded real defects plus clean controls; finding many
issues is not success if clean controls trigger. For generators, validate the
artifact with deterministic consumers rather than grading prose alone.

Classify a repeated-run difference as harmless phrasing or an action-changing
flip. Only the latter is a consistency failure. A clarification request can be
the correct result for an intentionally ambiguous case; freeze that expectation
instead of forcing an answer.

Operational failures remain distinct from judgment failures:

- unknown agent: verify registration/frontmatter before changing its prompt;
- timeout: retain partial tool trace and determine loop vs legitimate workload;
- missing context: repair the fixture when the production caller supplies it;
- hallucinated evidence: require source-bound citations and add a clean control;
- routing regression: preserve the full competing manifest, not only winner.

After each change rerun every frozen case, not just the former miss. Record the
variant and case-by-case delta so a local fix cannot hide a regression.
