# Domain-to-toolkit research contract

Produce a component manifest, not a prose survey. Start from the live agent,
skill, pipeline, and dependency inventories. Parallel research is useful only
for independent subdomains; every finding retains source, date/version, and
confidence.

Classify each subdomain as deterministic operation, bounded judgment, artifact
generation, or orchestration. Reuse an existing component when its contract
covers the action; name the uncovered delta before proposing a new one. Validate
candidate chains against `dag-compatibility-matrix.md` and the exact step types
in `pipeline-scaffolder/references/step-menu.md`.

Output JSON:

```json
{"domain":"...","subdomains":[{"name":"...","task_type":"...","evidence":[],"reuse":{"component":"...","gap":"..."},"chain":[]}],"shared":{"references":[],"scripts":[],"hooks":[]},"routing":[],"anti_features":[],"human_blockers":[]}
```

Human confirmation is required for legal/compliance interpretation, credentials,
irreversible actions, spending, and policy ownership. Unavailable research or an
ambiguous task type remains a gap; it does not justify inventing a component.
Load `domain-research/references/task-type-guide.md` only for classification
boundaries.
