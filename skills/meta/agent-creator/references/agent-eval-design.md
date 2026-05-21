# Agent Evaluation Design

> **Scope**: How to design activation evals (does the right agent get picked?) and output evals (does the picked agent do the work well?) for a vexjoy-agent operator. Both kinds of eval are designed at scaffold time, not retrofitted after routing failures appear.
> **Load when**: scaffolding a new agent, debugging a routing miss, or auditing whether an existing agent's description still matches its body.

---

## Two Evals, One Agent

A working agent passes two independent tests:

| Eval | Question | What it scores | When it runs |
|------|----------|----------------|--------------|
| **Activation eval** | Did the router pick this agent for the right requests? | The `description` + `triggers` fields | At scaffold time and whenever description changes |
| **Output eval** | Did the picked agent deliver the work? | The agent body, references, and gates | After dispatch, on real or synthetic tasks |

A perfect output eval cannot save an agent the router never picks. A perfect activation eval cannot save an agent that picks correctly but produces wrong work. Design both, in this order.

---

## Activation Eval

The router (and the Haiku selector) reads `name` and `description` first. The activation eval tests whether those two fields produce the right routing decision across realistic phrasings.

### Three case classes

Every agent needs cases in all three columns. Three each is the floor; five each is comfortable.

| Class | What it is | Purpose |
|-------|------------|---------|
| **should-trigger** | Phrases a real user would say when they want this agent | Confirms the description covers the intended domain |
| **should-not-trigger** | Phrases that look related but belong to a different agent | Confirms the boundary clause excludes off-domain work |
| **near-miss** | Phrases on the edge — same words, different intent | Confirms the description disambiguates rather than triggering on keyword overlap |

### Worked example: `kubernetes-helm-engineer`

Description: *"Kubernetes deployments and Helm charts: manifest authoring, values overrides, release upgrades, RBAC. Not for cluster diagnostics — see kubernetes-troubleshooter."*

| Phrase | Class | Should this agent route? | Why |
|--------|-------|--------------------------|-----|
| "write a helm chart for our redis deployment" | should-trigger | yes | Direct domain match: helm + chart + deployment |
| "override the image tag in values.yaml for staging" | should-trigger | yes | Adjacent term match: values overrides |
| "upgrade the prometheus release to 2.45" | should-trigger | yes | Adjacent term: release upgrade |
| "the pods are crashlooping in production" | should-not-trigger | no — route to `kubernetes-troubleshooter` | Boundary clause excludes diagnostics |
| "explain how kubernetes namespaces work" | should-not-trigger | no — route to a docs/explainer | Domain-adjacent but no authoring task |
| "helm me figure out why my chart isn't installing" | near-miss | yes — keyword "helm" + authoring problem | Resolves to authoring; the install failure is the symptom |
| "kubernetes is helmed by the control plane" | near-miss | no | Keyword "helm" appears but as a verb in unrelated context |

### Recording the cases

Save the cases in the SCAFFOLD-phase notes so they survive into the activation eval seed. Format:

```markdown
## Activation eval seeds — {agent-name}

### should-trigger
1. <phrase>
2. <phrase>
3. <phrase>

### should-not-trigger (with redirect target)
1. <phrase> → <other-agent-or-skill>
2. <phrase> → <other-agent-or-skill>
3. <phrase> → <other-agent-or-skill>

### near-miss
1. <phrase> — <should it trigger? why?>
2. <phrase> — <should it trigger? why?>
3. <phrase> — <should it trigger? why?>
```

These seeds live in `agents/{name}/references/activation-cases.md` (or appended to an existing notes file). The Post-Write Checklist in `agent-frontmatter-template.md` requires this file before commit.

### Manual pass vs. automated pass

For most agents, a mental routing pass over the cases is enough at scaffold time:

1. Read each phrase.
2. Predict which agent the router selects.
3. Compare against the expected routing.
4. Adjust the description until predictions match expectations.

For load-bearing agents (called many times per day, or guarding destructive actions), back the cases with a script that runs the actual router against each phrase and asserts the selected agent. This converts the seeds into a regression test.

### Fixing a failing activation case

| Failure | Fix the description by |
|---------|------------------------|
| should-trigger phrase routes elsewhere | Add the missing adjacent term to the description |
| should-not-trigger phrase routes here | Tighten the boundary clause (`Not for X — see Y`) |
| near-miss routes wrong direction | Replace ambiguous keyword in description with the disambiguating phrase from the case |

After a description change, re-run all cases — fixing one can break another.

---

## Output Eval

Once the right agent is picked, the output eval scores the work it produces. Output evals are heavier than activation evals — design them with fewer cases but richer assertions.

### Dimensions to score

| Dimension | Question | Signal |
|-----------|----------|--------|
| **Task success** | Did the agent produce the requested artifact? | File exists, command exits 0, test passes |
| **Format adherence** | Does the output match the contract (frontmatter, headings, table format)? | Parser passes, schema validates |
| **Tool choice** | Did the agent use the right tools, and only those? | Tool log review; no Edit calls from a Reviewer |
| **Validation steps** | Did the agent run its own gates before claiming completion? | Phase artifacts present, gates produced output |
| **Citation quality** | Are factual claims backed by file paths or tool results? | Spot check: pick three claims, verify the citation |
| **Failure handling** | When a gate fails, does the agent stop and report instead of rationalizing past it? | Inject a synthetic failure; observe the response |

### Case design

Output eval cases come from three sources:

1. **Happy-path tasks** — the obvious requests this agent handles every day
2. **Edge cases** — boundary conditions, missing inputs, conflicting constraints
3. **Regression cases** — every production miss becomes a permanent case

The first two are seeded at scaffold time. The third is built up over the agent's life. A regression case lives forever; deleting one is how silent failures return.

### Train / validation separation

When the description is being optimized for activation, split the cases:

| Set | Purpose | Size |
|-----|---------|------|
| **Train** | Cases used to iterate on the description | 60% |
| **Validation** | Cases held back to catch overfit | 40% |

If the train set passes 100% but the validation set fails, the description is memorizing phrases instead of capturing the domain. Rewrite for generalization.

For output evals, the same split applies when iterating on the agent body, references, or gates.

---

## Where the Evals Live

| Artifact | Path | Purpose |
|----------|------|---------|
| Activation seeds | `agents/{name}/references/activation-cases.md` | should-trigger / should-not-trigger / near-miss phrases |
| Output cases | `agents/{name}/references/output-cases.md` (when warranted) | Happy-path + edge + regression tasks with assertions |
| Regression log | `retro/{name}-misses.md` (when warranted) | Production misses, with the case that should have caught them |

Lightweight agents may keep both seed files merged; heavyweight agents (orchestrators, destructive-action gatekeepers) split them. The author decides at scaffold time and writes the path into the agent's reference loading table.

---

## Quick Authoring Checklist

When scaffolding a new agent:

1. Write the description per `agent-frontmatter-template.md` Description Craft.
2. List 3 should-trigger phrases. The description's adjacent terms cover at least 2.
3. List 2 should-not-trigger phrases with redirect targets. The boundary clause excludes them.
4. List 2 near-miss phrases with verdicts and reasoning.
5. Save the lists to `agents/{name}/references/activation-cases.md`.
6. Mental-pass the cases against the description. Fix the description if any case fails.
7. Add a row to the agent's Reference Loading Table pointing at the activation cases file.
8. (Output eval) When the agent is load-bearing, write 3 happy-path tasks with observable success criteria.

This is the activation half of the Post-Write Checklist items 7 and 8 in `agent-frontmatter-template.md`. Step 7's mental pass is the floor; steps 5 and 6 produce the artifact that makes the test repeatable.
