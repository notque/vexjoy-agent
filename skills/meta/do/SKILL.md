---
name: do
description: "Classify a request, validate names against the live routing manifest, and dispatch the matched agent, skill, pipeline, and rigor stack."
user-invocable: true
argument-hint: "<request>"
allowed-tools: [Read, Bash, Grep, Glob, Skill, Task]
routing:
  triggers: ["route task", "classify request", "which agent", "delegate to skill", "smart router"]
  category: meta-tooling
---

# /do - Smart Router

`/do` routes work; it does not perform Simple-or-larger work itself. Preserve
the user's request verbatim in the task spec and deliver the completed outcome,
not merely a plan. A truly trivial action is limited to the explicitly named
file and at most a few obvious edits; repository exploration, git operations,
comparisons, and multi-file work are routed.

Show `/do > Phase N: NAME — description...` at each phase and the routing banner
before dispatch.

## 1. Classify

Use `trivial | simple | medium | complex`; uncertainty rounds upward. Creation
of an agent, skill, pipeline, hook, feature, plugin, workflow, or voice profile
is a creation request and needs its repository creation gates. Independent
subtasks may fan out; dependent stages remain sequential.

## 2. Select from the live manifest

Resolve the installed scripts directory through `.claude`, `.hermes`,
`.factory`, `.codex`, `.reasonix`, then run:

```bash
bash "$SDIR/get-routing-manifest.sh"
```

Route by meaning, not trigger words. Names must remain in their manifest
sections: agents in `AGENTS`, skills in `SKILLS`, pipelines in `PIPELINES`.
Never promote a skill into the agent slot. Prefer the narrowest domain agent;
`general-purpose` is allowed only with a written reason that no listed agent
covers the domain. Simple+ requires a methodology skill; use `workflow` only
when no narrower skill fits. A pipeline is additional phase structure, not a
replacement for agent or skill, and is warranted by a semantic match, genuine
multi-phase shape, or complex classification.

Run the deterministic guard after semantic selection:

```bash
REQUEST_FILE=$(mktemp)
printf '%s' "$REQUEST" > "$REQUEST_FILE"
python3 "$SDIR/pre-route.py" --request-file "$REQUEST_FILE" --json-compact
rm -f "$REQUEST_FILE"
```

High-confidence protected git/security force routes override a conflicting
semantic skill choice. Other results are guard signals, not permission to
replace the semantic route. Keep stacks returned for protected language/domain
operands.

The banner identifies agent, skill, optional pipeline, and extra rigor with a
brief reason for each. A real multi-file diff uses `right-size-review.py` and
outranks the generic comprehensive-review path. Honor local-only requests by
injecting `shared-patterns/local-only.md`.

**COMBINATION DOCTRINE.** Agent, skill, pipeline, and stack compose rather than
compete. For fan-out, each extra agent keeps distinct ownership. cross-repo and
real-diff work follow the same section integrity rule. The skill selection gate
is HARD — non-negotiable: review→review,
debug→workflow (systematic-debugging pipeline), audit→review, and plan→workflow.
For whole-repo work, check live indexes for near-matches before using the
general-purpose fallback. Cross-repo dispatch retains the same rule. Force-route
guards and built-in verification gates remain authoritative. Real-diff
right-sizing feedback may re-route or re-dispatch; session-end telemetry is a
fallback receipt, never routing authority.

**Step 1:** Apply the selected agent, skill, and pipeline after manifest
membership validation.

**Step 2: Apply skill override** only for an explicit methodology verb or a
protected guard result; semantic domain ownership remains unchanged.

**Step 3:** Show the route and build its handoff.

### Phase 3: ENHANCE

| Signal | Action |
|---|---|
| Objective with done-criteria | Stack `workflow` |
| User-level `voice-example-profile` | Stack `writing` |

## 3. Build the handoff

For Simple+, supply a task spec with: unchanged `request_verbatim`, outcome
`intent`, constraints/authority, decisions, relevant prior results, gaps,
acceptance evidence, owned files, ownership boundary, and operator context.
Use `context_mode: summary` unless file excerpts are necessary. Do not duplicate
an investigation when a durable evidence path is available.

Creation requests require the repository ADR/plan gates. Medium+ code changes
use the quality loop; explicit or selected workflows use workflow dispatch. If
both apply, quality-loop is outer and the workflow runs inside implementation.
Load `references/quality-loop.md` or `references/workflow-dispatch.md` only for
those cases.

## 4. Dispatch

Run `python3 "$SDIR/build-dispatch.py" --json '<decision>'`; do not manually
construct tool calls or the routing marker. The decision has this shape:

The emitted instruction begins "Call the Skill tool with". The builder emits
one instruction per callable selected skill; agents and pipelines are not
Skill-tool calls.

```json
{
  "agent": "manifest-agent",
  "skill": "manifest-skill",
  "pipeline": "optional-manifest-pipeline",
  "complexity": "simple|medium|complex",
  "model": "inherit",
  "context_mode": "summary",
  "provider": "anthropic|openai|other",
  "manual_model_override": false,
  "health": "-",
  "fallback_reason": "required only for general-purpose",
  "stack": [],
  "task_spec": {},
  "flags": {"worktree": false, "local_only": false, "thinking_override": null},
  "token_remaining": 480000
}
```

The builder validates index membership, emits the sole routing telemetry marker,
and produces exact skill calls. Agents and pipelines never become Skill-tool
calls. Fan-out uses one builder invocation and one dispatch per agent, with
separate ownership. `model: inherit` is required by default for Medium+; never
pass the literal word `inherit` as an agent tool model name.

An absent match must still produce agent+skill via the documented fallbacks.

**Step 4: Auto-Pipeline Fallback** uses the closest live pipeline only when the
request genuinely has phases; otherwise keep the agent+skill route.

**Lazy-completion check.** Reject an agent's premature “done” when enumerable
scope or acceptance evidence is missing, then re-dispatch.

### Phase 4: EXECUTE

Dispatch the built action and deliver its result.

## Error Handling

Routing failures use `references/error-handling.md`; telemetry investigations
use `references/routing-telemetry.md`.

## References

Load only the references named by the applicable gate above.
