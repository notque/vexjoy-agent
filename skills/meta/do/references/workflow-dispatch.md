# Workflow dispatch

The pipeline index supplies phase names and contracts. Validate a selected
pipeline against the live manifest/index, then pass its name to
`build-dispatch.py`; a pipeline never replaces the agent or skill.

Dispatch dependencies sequentially with relevant prior-result paths. Dispatch
independent, non-overlapping ownership in parallel. A phase failure blocks its
dependents and retains its receipt. When both workflow and quality-loop apply,
quality-loop is outer and the selected workflow executes within implementation.
