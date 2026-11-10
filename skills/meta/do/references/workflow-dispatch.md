# Workflow Dispatch (Phase 4 Steps 1b/1c)

Native-Workflow executor selection and roster rules, moved verbatim from `SKILL.md` Phase 4. Load on: a pipeline `pick`, Complex/tier-4 with no pick, or an explicit "run through a workflow" request.

**Step 1b (native Workflow dispatch): run the deterministic variant when the harness supports it, else the prose pipeline.** When the Phase 2 Step 0 self-route emitted a pipeline `pick` (#686), select the executor with this ADR decision table (`harness-conditional-workflow-dispatch`):

```
pick = route.pipeline                               # #686, may be null
cap  = scripts/detect-workflow-capability.py        # env proxy: {harness, workflow_capable}
reg  = scripts/workflow-registry.py                 # auto-derived {meta.name: path}
{scope, tier, tier_signal} = scripts/right-size-review.py   # #688 right-sizing (review picks only)
if not tier_signal: tier = unset                    # roster rule 1: no real diff, no tier
complex4 = (complexity == Complex) or (tier == 4)   # ADR native-fast-path Stage 2
pick_tier = (tier the caller named) or (tier if pick is a review pick else unset)

if pick is not None and reg.get(pick) and cap.workflow_capable and (Workflow tool in MY tool list):
        # Claude Code NAMED pipeline: env proxy AND LLM tool-list self-check
                                                            -> Workflow.run(reg[pick], {scope, tier: pick_tier})
elif cap.harness == "antigravity" and (run_workflow tool in MY tool list) and (pick is not None or complex4):
        # Antigravity CLI Python run_workflow path (skills/process/workflow/references/fan-out-workflow.py)
                                                            -> run_workflow(fan-out-workflow.py, {scope, tier, roster})
elif cap.harness == "antigravity" and complex4:
        # Antigravity CLI /teamwork subagent path (define_subagent + invoke_subagent Workspace="branch"|"share")
                                                            -> dispatch parallel subagents via invoke_subagent (antigravity-execution.md)
elif pick is not None and reg.get(pick):                    -> run the prose pipeline markdown (unchanged)
elif pick is None and complex4 and cap.workflow_capable and (Workflow tool in MY tool list):
        # NO named pipeline + Complex/tier-4: generic native fan-out (Stage 2)
                                                            -> Workflow.run("fan-out-workflow", {scope, tier, roster})
elif pick is None and complex4:                             # Workflow tool absent -> floor
                                                            -> dispatch multiple Agent tools in one message (prose fan-out, unchanged)
else:                                                       -> agent + skill direct (simpler; unchanged)
```

Pass the right-size tier only to review picks, and only when the script returns `tier_signal: true` (a real diff). On an empty diff or a git error the script still prints `tier: 1`: drop it, so `comprehensive-review` runs every wave. `toolkit-improvement` gets a tier only when the caller names one.

Build `roster` from the Phase-3 enhancement signals, sized by the roster rule below. **Each entry is `{agentType, skills: [...], lens}` — `skills` is a LIST carrying the FULL Phase-3 stack a direct dispatch would build.** Per agent, emit `Call the Skill tool with \`skill-name\`.` once per callable `skills` element and the four /do mandatory injections. Native forms: `comprehensive-review-workflow.js` (named pipeline), `fan-out-workflow.js` (generic Complex/tier-4). Both pseudocode gates (env proxy AND the orchestrator's own tool-list self-check) must hold; a `pick` with no registry entry is prose-only.

**File ownership batching:** batch fan-out items by file ownership before opening PRs — branches touching the same file merge serially and each later one goes CONFLICTING (evidence: PRs #789/#791/#793 each added rows to pr-workflow SKILL.md, costing a remediation wave). Put shared-file items on one branch or declare a merge order.

**Banner parity (R4):** expand the pipeline name → phase list for the routing banner on BOTH paths, so it reads identically regardless of executor (e.g. complexity-trigger fan-out shows `fan-out → synthesize`).

**Step 1c (inline-authored Workflow scripts): when the user explicitly asks to "run through a workflow" with no named pipeline `pick`, the orchestrator MUST dictate roster size and skill stacks — never delegate those to the Workflow tool** (whose defaults skew toward many-skeptic adversarial fan-outs and rarely emit the exact Skill-tool call). Before any inline `script:`, build the same `roster` Step 1b uses and pin:

| Constraint | Rule |
|------------|------|
| **Agent count** | Dictate explicit roster length with the roster rule below, not the Workflow tool's "comprehensiveness" heuristics. |
| **Model** | Never write a model name in a script. Import `modelFor` from `skills/process/workflow/references/workflow-helpers.js` and set `model: modelFor(role, modelOverride)`: `gather` for read-only collection a later stage judges, `work` for edits, verification, and findings that decide, `lead` for synthesis and final reports. Pass `modelOverride` only when the user names a model for the task. `scripts/validate-workflow-conformance.py` fails a literal model string. |
| **Skill stacks** | EVERY `agent()` prompt MUST contain `Call the Skill tool with \`skill-name\`.` once per callable element of its roster entry's `skills` list. Empty `skills` is a routing bug — fail closed and re-route. |
| **Adversarial passes** | Default to **single skeptic per finding**, not 3–5. Escalate to 3 only on a request for "adversarial," "heavy refute," or "high-stakes review," and only on findings surviving the first pass. |
| **Phase count** | Reuse a registry pipeline's phase shape (`comprehensive-review-workflow`, `fan-out-workflow`, `research-pipeline`) over inventing novel phase names. |

## Roster rule

This file owns the agent-count rule for every fan-out, native or prose. Other files link here instead of restating a number.

1. **Start at the smallest roster, except for a named full-coverage pipeline.** With no tier, use the smallest row for the request class. `comprehensive-review` and `toolkit-improvement` are the exception: with no `tier` they run every wave (`tierOrFull` in `workflow-helpers.js` returns tier 4), because the name promises full coverage. Owner, 2026-11-09: "Comprehensive review is no longer comprehensive with 1 wave". Only an explicit tier shrinks them: one `scripts/right-size-review.py` computed from a real diff (`tier_signal: true`), or one the caller names. Never pass a tier the script returned with `tier_signal: false`.
2. **Go larger only on a stated reason.** Use a higher tier when the user asks for more depth ("thorough", "deep", "full", "adversarial"), or when `scripts/right-size-review.py` returns that tier for the diff. Pass the tier explicitly in the run args.
3. **Dispatch at most 10 agents in one parallel barrier.** Split a larger roster into waves of 10 or fewer.
4. **The table sets the ceiling for each class.** Fewer agents is allowed when the scope has fewer independent parts. More is not.
5. **`toolkit-improvement` also takes `maxAgents`** (default 40), a cap on the whole run. The run logs and returns what the cap dropped.
6. **A workflow edits files only behind the edit gate.** `comprehensive-review-workflow` and `toolkit-improvement` report by default. Pass `implement: true` and a non-default work `branch` only after the operator asks for fixes or implementation (`editBlocker` in `workflow-helpers.js`); `main`, `master`, and `trunk` are refused.

| Request class | Roster ceiling | Skeptic pass |
|---------------|----------------|--------------|
| PR review, no tier or Tier 1 (≤5 files, 1 package) | 3 reviewers | none default; 1 skeptic on user request |
| PR review, Tier 2 / Tier 3 from `right-size-review.py` | prose path 12 / 17 reviewers, in waves of ≤10; native `comprehensive-review-workflow` 4 / 7 | 1 skeptic on "Critical" findings only |
| PR review, Tier 4 from `right-size-review.py`, a user request for a full review, or `comprehensive-review` with no tier | prose path 27 reviewers, in waves of ≤10; native `comprehensive-review-workflow` 13 | 1 skeptic on Critical+High findings |
| Adversarial validation of N findings | 1 skeptic × N (not 3 × N) | escalate to 3 only on user-flagged "heavy pushback" |
| Research fan-out | 3–5 researchers per `research-pipeline` Wave 1 | n/a |
| Generic complexity-trigger fan-out | use `fan-out-workflow` registered roster | n/a |

Inline `script:` shape (exact Skill-tool calls in EVERY worker, count from the roster):

```js
const ROSTER = [/* dictated count, NOT model-chosen */
  {agentType: "reviewer-system",       skills: ["review", "testing"], lens: "security"},
  {agentType: "reviewer-domain",       skills: ["review", "testing"], lens: "domain"},
  {agentType: "reviewer-perspectives", skills: ["review", "testing"], lens: "newcomer"},
];
const findings = await parallel(ROSTER.map(r => async () => {
  const prompt = `${skillDirectives(r.skills)}\n${buildPrompt(r)}`;
  return agent({prompt, agentType: r.agentType, schema: FINDINGS_SCHEMA, model: modelFor("work", modelOverride)});
}));
```

Catching a model-chosen N (`parallel(Array.from({length: N}, ...))`) or a missing exact Skill-tool call means **stop and rebuild the script from the roster rule above**.
