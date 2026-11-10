// toolkit-improvement.js
//
// Native dynamic-Workflow variant of the toolkit continuous-improvement pipeline.
// The markdown flow at ./toolkit-improvement.md remains the cross-harness floor;
// this script is the deterministic-runtime FAST-PATH for Claude Code (+Factory)
// when the native Workflow tool is present. It mirrors the prose 10-phase flow
// EVALUATE -> RESEARCH -> SYNTHESIZE -> CRITIQUE -> REPORT -> ADR -> IMPLEMENT ->
// VALIDATE -> REMEDIATE -> RECORD, replacing the $IMPROVE_DIR/*.md disk
// round-trips with schema-validated typed agent() returns and a real parallel()
// barrier for the mandatory multi-wave evaluation.
//
// The prose pipeline MANDATES that all agents within an evaluation wave dispatch
// in a single message for true parallelism, with Wave 1 = 10 foundation
// evaluators (the prose agent-roster.md). This workflow honors that as a FIXED
// 10-agent EVALUATE barrier of research-subagent-executor specialists (the
// static-roster shape, like comprehensive-review-workflow.js Wave 1), then runs a
// dynamic tail (research/synthesize/critique/report/adr/implement/validate/
// remediate/record) through the research-coordinator-engineer (the synthesis +
// governance owner). The prose deep-dive Wave 2 + adversarial Wave 3 scale ABOVE
// the fixed-10 floor and run as additional barriers; the ADR + IMPLEMENT fan-outs
// are one-agent-per-cluster (data-driven). REMEDIATE runs only on a validation
// regression (tier-/data-gated).
//
// Safety defaults:
//   - The run stops after REPORT. ADR through RECORD run only when the caller
//     passes `implement: true` and a non-default work `branch`. These two args
//     carry the operator approval that the prose Phase 5 and Phase 6 gates ask
//     for; a request to "evaluate" never edits files.
//   - An unset tier runs all three evaluation waves (tier 4). Only an explicit
//     tier shrinks the evaluation.
//   - `maxAgents` caps the agents one run dispatches. The run logs and returns
//     what the cap dropped.
//   - Models come from modelFor(role, modelOverride) in workflow-helpers.js.
//
// Runtime contract (see ./comprehensive-review-workflow.js for the canonical
// description of the native primitives): meta is a pure object literal parsed
// before the body; parallel(thunks) is a hard barrier (failed slot -> null);
// agent({prompt, schema, model, agentType}) returns a typed object; budget.
// remaining() bounds the tail. No Date.now()/Math.random()/new Date().

import {
  branchRule,
  editBlocker,
  mandatoryInjections,
  modelFor,
  skillDirectives,
  tierOrFull,
  validateAgentName,
  validateModelOverride,
} from "./workflow-helpers.js";

export const meta = {
  name: "toolkit-improvement",
  description:
    "Toolkit continuous-improvement pipeline as a deterministic native Workflow: EVALUATE -> RESEARCH -> SYNTHESIZE -> CRITIQUE -> REPORT -> ADR -> IMPLEMENT -> VALIDATE -> REMEDIATE -> RECORD. Evaluate-only by default: the run stops after REPORT, and ADR through RECORD run only with implement: true plus a non-default work branch. EVALUATE is a mandatory parallel barrier of 10 research-subagent-executor foundation evaluators (distinct dimensions); deep-dive + adversarial waves follow and run by default; an explicit tier below 4 drops them. The research-coordinator-engineer then researches ecosystem practice, synthesizes + de-dupes findings, applies skeptical critique, and reports the decision surface. With implement set, it writes one ADR per cluster the critique kept, domain engineers implement each ADR on the work branch, the governance engineer validates and remediates, and the coordinator records the reusable patterns. maxAgents caps total dispatch. Each agent attaches its full skill stack (one exact Skill-tool call per skill) plus the /do mandatory injections. Mirrors toolkit-improvement.md; that markdown flow stays the cross-harness floor.",
  // --- Conformance contract (pure literal — no calls/variables; see
  //     scripts/validate-workflow-conformance.py + adr/native-fast-path-portable-floor.md
  //     Stage 3). STATIC validation pins the phases + the FIXED 10-agent EVALUATE
  //     barrier (the parallel-wave mandate, countable). DYNAMIC validation records
  //     the real dispatch trace and asserts SHAPE + SKILLS, NOT count, where
  //     dynamic:true. name + description stay BEFORE this nested object so the
  //     non-greedy meta-name parser in workflow-registry.py still resolves meta.name.
  contract: {
    // Phase titles entered at runtime via enterPhase(). EVALUATE (the fixed 10-
    // agent barrier) is the first entered phase; the prose deep-dive (Wave 2) and
    // adversarial (Wave 3) evaluation waves are tier-gated phases of their own
    // (like comprehensive-review wave-2/wave-3), so the fixed-10 EVALUATE barrier
    // stays count-pinnable. The deterministic flag/scope step precedes EVALUATE.
    phases: [
      "evaluate",
      "deep-dive",
      "adversarial",
      "research",
      "synthesize",
      "critique",
      "report",
      "adr",
      "implement",
      "validate",
      "remediate",
      "record",
    ],
    // EVALUATE is a FIXED barrier: 10 research-subagent-executor foundation
    // evaluators on every run (the prose Wave 1 of 10 dimensions). Each carries a
    // `skills` LIST (the full evaluation stack attached via one exact Skill-tool call per
    // element). The distinct evaluation dimension is a RUNTIME property of the
    // prompt, not the roster shape, so the static roster is ten identical-type
    // entries (the gate pins the type + skills + count).
    roster: [
      { agentType: "research-subagent-executor", skills: ["toolkit", "testing"] },
      { agentType: "research-subagent-executor", skills: ["toolkit", "testing"] },
      { agentType: "research-subagent-executor", skills: ["toolkit", "testing"] },
      { agentType: "research-subagent-executor", skills: ["toolkit", "testing"] },
      { agentType: "research-subagent-executor", skills: ["toolkit", "testing"] },
      { agentType: "research-subagent-executor", skills: ["toolkit", "testing"] },
      { agentType: "research-subagent-executor", skills: ["toolkit", "testing"] },
      { agentType: "research-subagent-executor", skills: ["toolkit", "testing"] },
      { agentType: "research-subagent-executor", skills: ["toolkit", "testing"] },
      { agentType: "research-subagent-executor", skills: ["toolkit", "testing"] },
    ],
    // The EVALUATE barrier dispatches at least the fixed 10 on every run (static).
    agents: { static: 10, dynamic: false },
    // The deep-dive (Wave 2) + adversarial (Wave 3) waves scale the evaluation
    // ABOVE the fixed-10 floor; RESEARCH/SYNTHESIZE/CRITIQUE/REPORT/VALIDATE/
    // RECORD are single passes; ADR + IMPLEMENT fan out one agent per cluster
    // (data-driven) and run only with implement: true; REMEDIATE runs only on a
    // regression. Honest limit: the gate asserts SHAPE + SKILLS for the tail,
    // not COUNT.
    dynamic: true,
  },
};

// Map each dispatched agent to the FULL skill stack it invokes by name (one exact
// Skill-tool call per element). The foundation/deep-dive/adversarial evaluators run the
// evaluation methodology + earn the verification gate; the coordinator
// researches, synthesizes, critiques, reports, and writes ADRs with the same stack.
// The governance engineer implements skill, agent, and doc ADRs, and runs VALIDATE
// and REMEDIATE; the hook and Python engineers implement their file types. The literal skill names live in these `skills: [...]`
// arrays so the conformance gate resolves them; the body emits the directives by
// delegating each entry's list to skillDirectives().
const AGENT_SKILLS = {
  "research-subagent-executor": ["toolkit", "testing"],
  "research-coordinator-engineer": ["toolkit", "testing"],
  "toolkit-governance-engineer": ["toolkit", "testing"],
  "hook-development-engineer": ["programming", "testing"],
  "python-general-engineer": ["programming", "testing"],
};

// The mandated minimum EVALUATE size: the prose Wave 1 of 10 foundation
// dimensions, all dispatched in one parallel barrier. Deeper runs scale ABOVE
// this floor with the deep-dive + adversarial waves, never below it.
const MIN_EVALUATE_AGENTS = 10;
const COORDINATOR_AGENT = "research-coordinator-engineer";
// Edits to skills, agents, routing, and docs, plus the VALIDATE and REMEDIATE
// passes, go to the governance engineer. The coordinator never edits files.
const GOVERNANCE_AGENT = "toolkit-governance-engineer";
const HOOK_AGENT = "hook-development-engineer";
const PYTHON_AGENT = "python-general-engineer";

// Total agents one run may dispatch when the caller sets no `maxAgents`. A
// tier-4 evaluation uses 29, which leaves room for a small implement tail.
const DEFAULT_MAX_AGENTS = 40;
// Widest parallel() barrier for the data-driven ADR and IMPLEMENT fan-outs.
const MAX_PARALLEL = 10;

// The prose Wave 1 foundation dimensions (agent-roster.md). One distinct
// evaluation lens per EVALUATE agent; the fixed-10 barrier covers all of them.
const FOUNDATION_DIMENSIONS = [
  "security: injection vectors, credential exposure, path traversal, unsafe subprocess",
  "architecture: PHILOSOPHY.md adherence — determinism, progressive disclosure, router-as-orchestrator",
  "performance: hook latency (<50ms), unnecessary I/O, token-efficiency of skill/agent design",
  "testing: coverage gaps on critical paths (hooks, security scripts), test quality",
  "documentation: stale docs, references to missing files, descriptions that mismatch behavior",
  "naming: kebab-case, group-prefix consistency, inconsistent verbs across components",
  "dependencies: missing-but-used packages, broad version pins, stdlib-replaceable deps",
  "error-handling: bare except, silent swallowing, hooks that exit 2 on unexpected errors",
  "observability: stderr usefulness, CLAUDE_HOOKS_DEBUG support, meaningful exit codes",
  "type-design: missing annotations on public functions, Any overuse, TypedDict vs dict",
];

// The prose Wave 2 deep-dive lenses (scale ABOVE the fixed-10 floor).
const DEEPDIVE_DIMENSIONS = [
  "dead code: unused functions, zero-trigger skills, orphaned reference files, unreferenced agents",
  "ADR compliance: components without ADRs, Proposed-but-unimplemented, overridden decisions",
  "concurrency: unlocked shared-state access, race conditions in the hook system, telemetry DB access",
  "migration safety: settings.json schema breaks, skill renames, removed skills without deprecation",
  "python quality: mixed os.path/pathlib, deprecated patterns, oversized functions",
  "hook reliability: malformed-stdin handling, missing stdin timeout, exit-2-on-error fail-open",
  "script quality: missing --help, positional args, stdout/stderr misuse, missing __main__ guards",
  "pipeline coherence: artifact-over-memory, phase gates, missing interactive gates, hardcoded paths",
  "skill coverage gaps: common workflows with no skill, partial coverage, agents without skills",
  "routing correctness: dead force_routing key, missing INDEX entries, broad/narrow triggers, bad pairs_with",
];

// The prose Wave 3 adversarial lenses (challenge Wave 1+2 consensus, don't pile on).
const ADVERSARIAL_DIMENSIONS = [
  "contrarian: which findings are fine and don't need fixing; which fixes make things worse",
  "skeptical senior: which findings have concrete file:line evidence vs speculation; which risk regressions",
  "user advocate: which findings improve UX vs internal details users never see",
  "newcomer: what is confusing or undocumented; what trips up a first-time contributor",
  "meta-process auditor: are ADR creation, skill eval, learning capture actually being followed",
];

// --- Schemas (mirror the STYLE of comprehensive-review-workflow.js) -----------

// One evaluation dimension's typed finding set (mirrors a wave{N}-raw.md report).
const FINDING_SCHEMA = {
  type: "object",
  required: ["id", "severity", "description"],
  properties: {
    id: { type: "string" },
    severity: { type: "string", enum: ["critical", "high", "medium", "low"] },
    location: { type: "string" },
    description: { type: "string" },
    proposed_fix: { type: "string" },
    confidence: { type: "string", enum: ["high", "medium", "low"] },
  },
};

const EVALUATION_SCHEMA = {
  type: "object",
  required: ["dimension", "findings"],
  properties: {
    dimension: { type: "string" },
    findings: { type: "array", items: FINDING_SCHEMA },
    clean_areas: { type: "array", items: { type: "string" } },
  },
};

// RESEARCH output: ecosystem best-practice signal (the prose research-raw.md).
const RESEARCH_SCHEMA = {
  type: "object",
  required: ["practices"],
  properties: {
    practices: {
      type: "array",
      items: {
        type: "object",
        required: ["practice", "priority"],
        properties: {
          practice: { type: "string" },
          priority: { type: "string", enum: ["high", "medium", "low"] },
          gap_vs_toolkit: { type: "string" },
        },
      },
    },
  },
};

// SYNTHESIZE output: de-duped, ranked, clustered findings (the prose
// evaluation_report.md). Each cluster becomes one ADR candidate.
const SYNTHESIS_SCHEMA = {
  type: "object",
  required: ["clusters"],
  properties: {
    clusters: {
      type: "array",
      items: {
        type: "object",
        required: ["title", "severity"],
        properties: {
          title: { type: "string" },
          severity: { type: "string", enum: ["critical", "high", "medium", "low"] },
          agreement_count: { type: "number" },
          findings: { type: "array", items: { type: "string" } },
        },
      },
    },
  },
};

// CRITIQUE output: a disposition per cluster (the prose critique_report.md).
// `id` is the cluster id that withClusterIds() assigned; it ties a disposition
// to its cluster. `title` is for the reader only.
const CRITIQUE_SCHEMA = {
  type: "object",
  required: ["dispositions"],
  properties: {
    dispositions: {
      type: "array",
      items: {
        type: "object",
        required: ["id", "disposition"],
        properties: {
          id: { type: "string" },
          title: { type: "string" },
          disposition: { type: "string", enum: ["confirm", "downgrade", "dismiss", "elevate"] },
          corrected_severity: { type: "string", enum: ["critical", "high", "medium", "low"] },
          reasoning: { type: "string" },
        },
      },
    },
  },
};

// REPORT output: the dual-column decision surface (the prose comparison_report.md).
const REPORT_SCHEMA = {
  type: "object",
  required: ["rows"],
  properties: {
    rows: {
      type: "array",
      items: {
        type: "object",
        required: ["finding", "final_severity"],
        properties: {
          finding: { type: "string" },
          original_severity: { type: "string" },
          critique_disposition: { type: "string" },
          final_severity: { type: "string", enum: ["critical", "high", "medium", "low"] },
          contested: { type: "boolean" },
        },
      },
    },
    statistics: { type: "string" },
    top_adr_candidates: { type: "array", items: { type: "string" } },
  },
};

// ADR output: one ADR descriptor per cluster (the prose adr/NNN-*.md).
const ADR_SCHEMA = {
  type: "object",
  required: ["title", "decision"],
  properties: {
    title: { type: "string" },
    context: { type: "string" },
    decision: { type: "string" },
    validation_requirements: { type: "array", items: { type: "string" } },
    components: { type: "array", items: { type: "string" } },
  },
};

// IMPLEMENT output: one implementation log per ADR (the prose impl-adr-NNN.md).
const IMPLEMENT_SCHEMA = {
  type: "object",
  required: ["adr_title", "outcome"],
  properties: {
    adr_title: { type: "string" },
    outcome: { type: "string", enum: ["implemented", "partial", "blocked"] },
    changes: { type: "array", items: { type: "string" } },
    test_results: { type: "string" },
    blocked_tasks: { type: "array", items: { type: "string" } },
  },
};

// VALIDATE output: the regression gate (validation-results.md).
const VALIDATE_SCHEMA = {
  type: "object",
  required: ["verdict"],
  properties: {
    verdict: { type: "string", enum: ["pass", "regressed"] },
    results: { type: "array", items: { type: "string" } },
    regressed_skills: { type: "array", items: { type: "string" } },
  },
};

// REMEDIATE output: regression recovery (the prose remediation-*.md).
const REMEDIATE_SCHEMA = {
  type: "object",
  required: ["outcome"],
  properties: {
    outcome: { type: "string", enum: ["resolved", "escalated"] },
    fixes_applied: { type: "array", items: { type: "string" } },
    escalation_reason: { type: "string" },
  },
};

// RECORD output: recorded patterns + session summary (the prose session-summary.md).
const RECORD_SCHEMA = {
  type: "object",
  required: ["summary"],
  properties: {
    summary: { type: "string" },
    patterns: { type: "array", items: { type: "string" } },
    adrs_created: { type: "number" },
    adrs_implemented: { type: "number" },
  },
};

// --- Helpers ------------------------------------------------------------------

// Defensive phase marker: the native runtime guarantees agent/parallel/budget,
// but does NOT document a phase() global. Guard the call so the real runtime
// never throws if phase is absent, while the conformance harness's mock records
// the entered phase. Phase titles match meta.contract.phases.
function enterPhase(title) {
  if (typeof phase === "function") {
    phase(title);
  }
}

// Build one evaluator's prompt for its assigned dimension + wave. skillDirectives
// emits one exact Skill-tool call per element of the research-subagent-executor stack
// (resolves path-independent inside a native Workflow agent() dispatch).
// mandatoryInjections() embeds the /do completeness/density/base-instructions/
// reference-loading block. Each evaluator gets a DISTINCT dimension and writes
// its own typed result (no shared file), mirroring the prose wave-raw.md isolation.
function evaluatorPrompt(dimension, wave, scope, priorFindings) {
  const prior = priorFindings
    ? `\nPrior-wave findings (do not duplicate; ${wave === "adversarial" ? "challenge these" : "focus on what they missed"}):\n${JSON.stringify(priorFindings)}`
    : "";
  return (
    `You are a ${wave} toolkit evaluator (research-subagent-executor).` +
    skillDirectives(AGENT_SKILLS["research-subagent-executor"]) +
    `\nYour evaluation dimension: ${dimension}.\nEvaluate this toolkit scope:\n` +
    `${JSON.stringify(scope)}\n` +
    `Report only findings you have verified by reading the actual source file. ` +
    `Each finding needs an id, severity (critical|high|medium|low), file:line ` +
    `location, description, a concrete proposed fix, and a confidence rating. ` +
    `Stay within your dimension — the coordinator synthesizes across dimensions.` +
    prior +
    mandatoryInjections()
  );
}

// Build a prompt for a named agent: task, that agent's skill stack, the typed
// payload, and the mandatory injections. Same context as a direct /do dispatch.
function agentPrompt(agentName, task, payload) {
  return (
    task +
    skillDirectives(AGENT_SKILLS[agentName]) +
    `\n${JSON.stringify(payload)}` +
    mandatoryInjections()
  );
}

// Build a coordinator prompt (RESEARCH/SYNTHESIZE/CRITIQUE/REPORT/ADR/RECORD).
function coordinatorPrompt(task, payload) {
  return agentPrompt(COORDINATOR_AGENT, task, payload);
}

// Dispatch one fixed-roster evaluation wave in a single parallel() barrier. The
// CALLER enters the wave's phase (with a literal title, so the static gate sees
// it) before invoking this; the harness then attributes each wave's agents to its
// own phase, keeping the fixed-10 EVALUATE barrier count-pinnable. Each dimension
// is a DISTINCT lens; failed slots resolve to null and are filtered. Evaluators
// return findings that decide, so they run the `work` model.
async function runWave(dimensions, wave, scope, priorFindings, modelOverride) {
  const raw = await parallel(
    dimensions.map((dimension) => () =>
      agent({
        prompt: evaluatorPrompt(dimension, wave, scope, priorFindings),
        schema: EVALUATION_SCHEMA,
        model: modelFor("work", modelOverride),
        agentType: "research-subagent-executor",
      }),
    ),
  );
  return raw.filter((x) => x != null);
}

// Run thunks in barriers of at most MAX_PARALLEL, in order.
async function boundedParallel(thunks) {
  const out = [];
  for (let i = 0; i < thunks.length; i += MAX_PARALLEL) {
    out.push(...(await parallel(thunks.slice(i, i + MAX_PARALLEL))));
  }
  return out;
}

// Count dispatched agents against the run cap. take() returns the items that
// fit, in order, and records and logs the ones it drops.
function makeAgentCap(maxAgents) {
  const limit =
    typeof maxAgents === "number" && Number.isFinite(maxAgents) && maxAgents >= 1
      ? Math.floor(maxAgents)
      : DEFAULT_MAX_AGENTS;
  let used = 0;
  const dropped = [];
  return {
    limit,
    dropped,
    used: () => used,
    take(items, phaseTitle, label) {
      const kept = items.slice(0, Math.max(0, limit - used));
      used += kept.length;
      const cut = items.slice(kept.length).map(label);
      if (cut.length > 0) {
        dropped.push({ phase: phaseTitle, agents: cut });
        if (typeof log === "function") {
          log(
            `toolkit-improvement: maxAgents=${limit} reached in ${phaseTitle}; ` +
              `dropped ${cut.length}: ${cut.join("; ")}`,
          );
        }
      }
      return kept;
    },
    // One single-agent pass: true when the cap has room for it.
    one(phaseTitle) {
      return this.take([phaseTitle], phaseTitle, (x) => x).length === 1;
    },
  };
}

// Return why IMPLEMENT must not run, or null when the caller cleared the gate.
// editBlocker (workflow-helpers.js) owns the implement + branch rule.
function implementBlocker(implement, evaluateOnly, branch) {
  if (evaluateOnly === true) return "evaluateOnly is set";
  return editBlocker(implement, branch);
}

// Pick the engineer that implements one ADR from the components it touches:
// hooks go to the hook engineer, a Python-only change to the Python engineer,
// and skills, agents, routing, docs, or a mixed set to the governance engineer.
function implementerFor(adr) {
  const components =
    adr && Array.isArray(adr.components)
      ? adr.components.filter((c) => typeof c === "string")
      : [];
  if (components.some((c) => /(^|\/)hooks\//.test(c))) return HOOK_AGENT;
  if (components.length > 0 && components.every((c) => /\.py(:\d+)?$/.test(c.trim()))) {
    return PYTHON_AGENT;
  }
  return GOVERNANCE_AGENT;
}

const SEVERITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3 };

const KEPT_DISPOSITIONS = new Set(["confirm", "downgrade", "elevate"]);

// Give each cluster a stable id (c1, c2, ...) in code, so the critique answers
// by id and a paraphrased title cannot detach a disposition from its cluster.
function withClusterIds(synthesis) {
  if (!synthesis || !Array.isArray(synthesis.clusters)) return synthesis;
  return {
    ...synthesis,
    clusters: synthesis.clusters.map((c, i) => ({ ...c, id: `c${i + 1}` })),
  };
}

// Split clusters by the critique's verdict. Fails closed: a cluster becomes an
// ADR only when a disposition with its id says confirm, downgrade, or elevate.
// `approved` carries the corrected severity, worst first, so the cap drops the
// least severe. `unreviewed` has no disposition under its id (the critic left
// it out, or no critique ran) and is never implemented.
function splitClusters(synthesis, critique) {
  const clusters = synthesis && Array.isArray(synthesis.clusters) ? synthesis.clusters : [];
  const dispositions = critique && Array.isArray(critique.dispositions) ? critique.dispositions : [];
  const byId = new Map();
  for (const d of dispositions) {
    if (d && typeof d.id === "string") byId.set(d.id, d);
  }
  const approved = [];
  const unreviewed = [];
  for (const c of clusters) {
    const d = byId.get(c.id);
    if (!d || typeof d.disposition !== "string") unreviewed.push(c);
    else if (KEPT_DISPOSITIONS.has(d.disposition)) {
      approved.push(d.corrected_severity ? { ...c, severity: d.corrected_severity } : c);
    } else if (d.disposition !== "dismiss") unreviewed.push(c);
  }
  approved.sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9));
  return { approved, unreviewed };
}

// --- Workflow body ------------------------------------------------------------
//
// run({scope, tier, depth, implement, branch, evaluateOnly, maxAgents, modelOverride}):
//   - scope: the toolkit evaluation descriptor (target dirs + focus).
//   - tier: right-size tier from /do. Unset -> all three evaluation waves
//     (tier 4). An explicit tier shrinks the run: tier <= 2 -> foundation wave
//     only; tier 3 -> foundation + deep-dive.
//   - depth: explicit override — "deep" forces all three evaluation waves.
//   - implement: `true` runs ADR -> RECORD after REPORT. Pass it only when the
//     operator asked for implementation. Any other value stops after REPORT.
//   - branch: the work branch IMPLEMENT edits on. Required with `implement`;
//     main, master, and trunk are refused. Every editing agent checks it.
//   - evaluateOnly: `true` stops after REPORT even when `implement` is set (the
//     prose --evaluate-only flag).
//   - maxAgents: cap on agents dispatched in this run (default 40). The run
//     drops what does not fit, logs it, and returns it in `dropped`.
//   - modelOverride: a model the owner named for this task. When set, every
//     agent runs on it. Unset: RESEARCH runs the `gather` model; SYNTHESIZE,
//     REPORT, and RECORD inherit the session model (`lead`); the rest run the
//     `work` model.

export default async function run({
  scope,
  tier,
  depth,
  implement,
  branch,
  evaluateOnly,
  maxAgents,
  modelOverride,
} = {}) {
  // Reject a bad model name before any dispatch.
  validateModelOverride(modelOverride);
  const effectiveTier = tierOrFull(tier);
  const runDeepDive = depth === "deep" || effectiveTier >= 3;
  const runAdversarial = depth === "deep" || effectiveTier >= 4;
  const implementBlocked = implementBlocker(implement, evaluateOnly, branch);
  const cap = makeAgentCap(maxAgents);
  const dimensionLabel = (d) => d.split(":")[0];
  const minTailBudget = 8000;

  // Phase EVALUATE: the mandatory parallel barrier. The fixed 10 foundation
  // evaluators (the prose Wave 1) in one parallel() call, each on a DISTINCT
  // dimension (single-message dispatch is the prose parallelism mandate). The
  // deep-dive + adversarial waves run as their own tier-gated phases (scaling the
  // evaluation ABOVE the fixed-10 floor), so the EVALUATE barrier stays a clean
  // count-pinnable 10 unless the caller's maxAgents is below 10.
  enterPhase("evaluate");
  let findings = await runWave(
    cap.take(FOUNDATION_DIMENSIONS, "evaluate", dimensionLabel),
    "foundation",
    scope,
    null,
    modelOverride,
  );
  if (runDeepDive && budget.remaining() >= minTailBudget) {
    // Phase DEEP-DIVE: the prose Wave 2 — receives Wave 1 findings as context to
    // avoid duplication. Tier-gated, so its presence is honestly dynamic:true.
    enterPhase("deep-dive");
    const deep = await runWave(
      cap.take(DEEPDIVE_DIMENSIONS, "deep-dive", dimensionLabel),
      "deep-dive",
      scope,
      findings,
      modelOverride,
    );
    findings = findings.concat(deep);
  }
  if (runAdversarial && budget.remaining() >= minTailBudget) {
    // Phase ADVERSARIAL: the prose Wave 3 — challenges Wave 1+2 consensus rather
    // than piling on. Tier-gated presence (dynamic:true).
    enterPhase("adversarial");
    const adversarial = await runWave(
      cap.take(ADVERSARIAL_DIMENSIONS, "adversarial", dimensionLabel),
      "adversarial",
      scope,
      findings,
      modelOverride,
    );
    findings = findings.concat(adversarial);
  }

  // Phase RESEARCH: one coordinator gathers ecosystem best-practice signal to
  // calibrate the internal findings (the prose Phase 2; advisory, never blocks).
  // It rates each practice's priority and the gap against this toolkit, and the
  // coordinator can write and dispatch, so it is a `work` pass, not `gather`.
  enterPhase("research");
  let research = null;
  if (budget.remaining() >= minTailBudget && cap.one("research")) {
    research = await agent({
      prompt: coordinatorPrompt(
        `Gather current best practices, architectural patterns, and common ` +
          `pitfalls in LLM agent frameworks and AI workflow automation. For each, ` +
          `note priority (high|medium|low) and the gap vs this toolkit. ` +
          `Evaluation scope (typed):\n`,
        scope,
      ),
      schema: RESEARCH_SCHEMA,
      model: modelFor("work", modelOverride),
      agentType: COORDINATOR_AGENT,
    });
  }

  // Phase SYNTHESIZE: one coordinator de-dupes, ranks, and clusters the typed
  // findings + research into ADR candidates (the prose Phase 3). Synthesis
  // across many agents is a `lead` pass.
  enterPhase("synthesize");
  let synthesis = null;
  if (findings.length > 0 && budget.remaining() >= minTailBudget && cap.one("synthesize")) {
    synthesis = await agent({
      prompt: coordinatorPrompt(
        `De-duplicate these typed evaluation findings (merge same-issue, keep the ` +
          `most concrete description + agreement count), rank by severity then ` +
          `agreement, and group into logical clusters — each cluster is one ADR ` +
          `candidate. Integrate research-sourced gaps. Findings + research (typed):\n`,
        { findings, research },
      ),
      schema: SYNTHESIS_SCHEMA,
      model: modelFor("lead", modelOverride),
      agentType: COORDINATOR_AGENT,
    });
    synthesis = withClusterIds(synthesis);
  }

  // Phase CRITIQUE: one skeptical coordinator pass — challenge every cluster
  // before any ADR is written; cut false positives, fix severity (the prose
  // Phase 4).
  enterPhase("critique");
  let critique = null;
  if (synthesis && budget.remaining() >= minTailBudget && cap.one("critique")) {
    critique = await agent({
      prompt: coordinatorPrompt(
        `Challenge each finding cluster (do NOT validate). Assign one disposition ` +
          `per cluster: confirm | downgrade (corrected severity) | dismiss (cite ` +
          `evidence) | elevate (reasoning). Copy each cluster's \`id\` into its ` +
          `disposition unchanged; a cluster with no disposition under its id is ` +
          `not implemented. Concrete file:line = real; "probably" = ` +
          `not. Re-rank by assessed severity. Synthesis (typed):\n`,
        synthesis,
      ),
      schema: CRITIQUE_SCHEMA,
      model: modelFor("work", modelOverride),
      agentType: COORDINATOR_AGENT,
    });
  }

  // Phase REPORT: the dual-column decision surface — where evaluation + critique
  // agree and diverge (the prose Phase 5). The run stops here unless the caller
  // cleared the implement gate.
  enterPhase("report");
  let report = null;
  if (synthesis && budget.remaining() >= minTailBudget && cap.one("report")) {
    report = await agent({
      prompt: coordinatorPrompt(
        `Produce the dual-column decision surface: per finding show original ` +
          `severity, critique disposition, final severity, and a contested flag ` +
          `where the critique changed the ranking. Add statistics (confirmed/` +
          `downgraded/dismissed/elevated) and the top ADR candidates. Synthesis + ` +
          `critique (typed):\n`,
        { synthesis, critique },
      ),
      schema: REPORT_SCHEMA,
      model: modelFor("lead", modelOverride),
      agentType: COORDINATOR_AGENT,
    });
  }

  // The implement gate (the prose --evaluate-only flag + the Phase 5/6 operator
  // approval): stop before any ADR is written unless the caller passed
  // implement: true with a non-default work branch. Also stop with no report,
  // and with no critique: no cluster was reviewed, so none may be implemented.
  const { approved: clusters, unreviewed } = splitClusters(synthesis, critique);
  const unreviewedTitles = unreviewed.map((c) => c.title);
  if (unreviewed.length > 0) {
    log(
      `toolkit-improvement: ${unreviewed.length} cluster(s) have no critique ` +
        `disposition and are not implemented: ${unreviewedTitles.join(", ")}`,
    );
  }
  const stopReason =
    implementBlocked != null
      ? implementBlocked
      : critique == null
        ? "the critique did not run, so no cluster was reviewed"
        : null;
  if (stopReason != null || report == null) {
    return {
      tier: effectiveTier,
      evaluate_only: true,
      implement_requested: implement === true,
      implement_blocked: stopReason,
      unreviewed_clusters: unreviewedTitles,
      evaluators_ran: findings.length,
      deep_dive_ran: runDeepDive,
      adversarial_ran: runAdversarial,
      research,
      synthesis,
      critique,
      report,
      agents_dispatched: cap.used(),
      max_agents: cap.limit,
      dropped: cap.dropped,
      budget_remaining: budget.remaining(),
    };
  }

  // Phase ADR: one ADR per cluster the critique kept, written in parallel (the
  // prose Phase 6 single-message dispatch). The cluster set is data-driven, so the
  // fan-out count is honestly covered by contract.dynamic:true.
  enterPhase("adr");
  let adrs = [];
  if (clusters.length > 0 && budget.remaining() >= minTailBudget) {
    const rawAdrs = await boundedParallel(
      cap.take(clusters, "adr", (c) => c.title).map((cluster) => () =>
        agent({
          prompt: coordinatorPrompt(
            `Write one ADR for this finding cluster: context (original finding + ` +
              `critique disposition), a concrete decision/task list, concrete ` +
              `validation requirements (runnable commands + expected output), and ` +
              `the components touched. Read the referenced source before writing. ` +
              `Cluster (typed):\n`,
            cluster,
          ),
          schema: ADR_SCHEMA,
          model: modelFor("work", modelOverride),
          agentType: COORDINATOR_AGENT,
        }),
      ),
    );
    adrs = rawAdrs.filter((x) => x != null);
  }

  // Phase IMPLEMENT: one domain engineer per ADR (the prose Phase 7 domain
  // dispatch), chosen by implementerFor() from the ADR's components. Every
  // implementer gets the branch rule. Data-driven count.
  enterPhase("implement");
  let implementations = [];
  if (adrs.length > 0 && budget.remaining() >= minTailBudget) {
    const rawImpl = await boundedParallel(
      cap.take(adrs, "implement", (a) => a.title).map((adr) => () => {
        const implementer = validateAgentName(implementerFor(adr), "implementer");
        return agent({
          prompt: agentPrompt(
            implementer,
            `You are ${implementer}. Implement this ADR end-to-end: read each ` +
              `component before editing, execute every decision task, run ` +
              `language-appropriate tests after each change, and report a log ` +
              `(outcome, changes, test results, any blocked tasks). Stay within ` +
              `the components section.` +
              branchRule(branch) +
              `ADR (typed):\n`,
            adr,
          ),
          schema: IMPLEMENT_SCHEMA,
          model: modelFor("work", modelOverride),
          agentType: implementer,
        });
      }),
    );
    implementations = rawImpl.filter((x) => x != null);
  }

  // Phase VALIDATE: the governance engineer runs the regression gate — every
  // modified skill must pass validators and tests (the prose Phase 8).
  enterPhase("validate");
  let validation = null;
  if (implementations.length > 0 && budget.remaining() >= minTailBudget && cap.one("validate")) {
    validation = await agent({
      prompt: agentPrompt(
        GOVERNANCE_AGENT,
        `Run the regression gate over the implemented changes: ` +
          `every modified skill/agent must pass validators and tests. ` +
          `Edit nothing. Return verdict pass|regressed and the list of any ` +
          `regressed skills. Implementations (typed):\n`,
        implementations,
      ),
      schema: VALIDATE_SCHEMA,
      model: modelFor("work", modelOverride),
      agentType: GOVERNANCE_AGENT,
    });
  }

  // Phase REMEDIATE: regression recovery — runs ONLY when VALIDATE reports a
  // regression (the prose Phase 9, gated). Data-/tier-driven presence, so it is
  // honestly covered by contract.dynamic:true. It edits, so it gets the branch
  // rule and the governance engineer.
  enterPhase("remediate");
  let remediation = null;
  if (
    validation &&
    validation.verdict === "regressed" &&
    budget.remaining() >= minTailBudget &&
    cap.one("remediate")
  ) {
    remediation = await agent({
      prompt: agentPrompt(
        GOVERNANCE_AGENT,
        `Diagnose and fix these skill regressions (max 3 cycles before escalation): ` +
          `challenge whether the change was necessary, diagnose why the score ` +
          `dropped, and recover discoverability without reverting the ADR intent. ` +
          `Return outcome resolved|escalated; on a branch mismatch return escalated.` +
          branchRule(branch) +
          `Regressed skills (typed):\n`,
        validation.regressed_skills || [],
      ),
      schema: REMEDIATE_SCHEMA,
      model: modelFor("work", modelOverride),
      agentType: GOVERNANCE_AGENT,
    });
  }

  // Phase RECORD: name reusable patterns and the files that should carry them,
  // and write the session summary (the prose Phase 10). One coordinator pass;
  // the final report is a `lead` pass.
  enterPhase("record");
  let record = null;
  if (budget.remaining() >= minTailBudget && cap.one("record")) {
    record = await agent({
      prompt: coordinatorPrompt(
        `Name the reusable patterns and successful remediations from this run, ` +
          `each with the file that should carry it, and write a session summary ` +
          `(ADRs created/implemented, validation outcome, patterns recorded). ` +
          `Run results (typed):\n`,
        { adrs, implementations, validation, remediation },
      ),
      schema: RECORD_SCHEMA,
      model: modelFor("lead", modelOverride),
      agentType: COORDINATOR_AGENT,
    });
  }

  return {
    tier: effectiveTier,
    evaluate_only: false,
    implement_requested: true,
    implement_blocked: null,
    branch,
    evaluators_ran: findings.length,
    deep_dive_ran: runDeepDive,
    adversarial_ran: runAdversarial,
    research,
    synthesis,
    critique,
    report,
    unreviewed_clusters: unreviewedTitles,
    adrs_created: adrs.length,
    implementations_ran: implementations.length,
    validation,
    remediation,
    record,
    agents_dispatched: cap.used(),
    max_agents: cap.limit,
    dropped: cap.dropped,
    budget_remaining: budget.remaining(),
  };
}
