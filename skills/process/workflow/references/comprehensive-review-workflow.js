// comprehensive-review-workflow.js
//
// Native dynamic-Workflow variant of the four-wave comprehensive review.
// The markdown flow at ./comprehensive-review.md remains the documented
// fallback; this script is the deterministic-runtime OPTION for diffs that
// benefit (tier >= 3, or wide multi-package changes). It mirrors the same
// waves but replaces the $REVIEW_DIR/*.md disk round-trips with
// schema-validated typed agent() returns, real barriers (parallel) and
// item-streaming (pipeline), and a token-budget-bounded fix loop.
//
// Safety default: the run reports and edits nothing. The fix loop runs only
// when the caller passes `implement: true` and a non-default work `branch`
// (editBlocker in workflow-helpers.js). Every fix agent checks the branch.
//
// Runtime contract (see docs/dynamic-workflows-vs-vexjoy-diff.md):
//   - meta is a pure object literal (name + description) parsed before the body.
//   - parallel(thunks) is a hard barrier; a failed agent resolves to null.
//   - pipeline(items, ...stages) streams items through stages without a barrier.
//   - agent({prompt, schema, model}) forces a StructuredOutput tool call,
//     validates against schema at the tool layer, auto-retries on mismatch,
//     and returns a typed object — no markdown re-parse, no disk read.
//   - budget.remaining() returns run-wide tokens left; agent() throws when
//     exhausted. The fix loop is bounded by it.
//   - Wall-clock and randomness are unavailable by design, so determinism is
//     bit-stable across replay. This script uses neither.

import {
  branchRule,
  editBlocker,
  engineerForPath,
  mandatoryInjections,
  modelFor,
  referenceDirective,
  referenceForPath,
  skillDirectives,
  tierOrFull,
  validateModelOverride,
  WORKER,
} from "./workflow-helpers.js";

export const meta = {
  name: "comprehensive-review-workflow",
  description:
    "Four-wave code review as a deterministic native Workflow: tier-scaled waves (right-sizing), schema-validated typed findings per wave, parallel barriers within a wave, pipelined Wave 1 -> Wave 2 hand-off, per-finding adversarial verify before synthesis, and a budget-bounded fix loop. With no tier the run covers every wave; an explicit tier shrinks it. Report-only by default: the fix loop runs only with implement: true plus a non-default work branch. Each reviewer is a fresh general-purpose worker that loads its review-skill reference and attaches its full skill stack (one exact Skill-tool call per skill) plus the /do mandatory injections. Mirrors comprehensive-review.md; that markdown flow stays the fallback.",
  // --- Conformance contract (pure literal — no calls/variables; see
  //     scripts/validate-workflow-conformance.py + adr/native-fast-path-portable-floor.md
  //     Stages 0-1). This is the declared dispatch shape the conformance gate
  //     asserts the actual script against. STATIC validation pins phases + the
  //     fixed Wave-1 barrier (countable). DYNAMIC validation records the real
  //     dispatch trace and asserts SHAPE + SKILLS, NOT count, where dynamic:true.
  //     name + description stay BEFORE this nested object so the non-greedy
  //     meta-name parser in workflow-registry.py still resolves meta.name.
  contract: {
    // Phase titles this script enters at runtime via phase(). Order matters.
    phases: ["wave-1", "wave-2", "wave-3", "verify", "fix"],
    // Wave-1 is a FIXED barrier: a literal 4-agent roster, every run. Countable.
    // Each entry carries a `skills` LIST (the full stack the agent attaches via
    // one exact Skill-tool call per element) — the gate asserts EACH declared skill has a
    // corresponding exact Skill-tool call in source.
    roster: [
      { agentType: "general-purpose", skills: ["review", "testing"] },
      { agentType: "general-purpose", skills: ["review", "testing"] },
      { agentType: "general-purpose", skills: ["review", "testing"] },
      { agentType: "general-purpose", skills: ["assessment", "testing"] },
    ],
    // The Wave-1 barrier dispatches exactly 4 agents on every run (static).
    agents: { static: 4, dynamic: false },
    // Wave-2/3 rosters are literal arrays (countable) but tier-gated, and the
    // per-finding verify pass + the budget-bounded fix loop fan out over
    // RUNTIME data (findings.length, budget) — NOT statically countable.
    // Honest limit: the gate asserts SHAPE + SKILLS for these, not COUNT.
    dynamic: true,
  },
};

// Repo agents are retired (plan 009). Every reviewer is a fresh general-purpose
// worker (WORKER) that reads one review reference from the review skill, so each
// lens still runs in its own independent context. REVIEWERS maps each reference
// slug to that reference and to the FULL skill stack the worker invokes by name
// (one exact Skill-tool call per element). reviewer-{system,domain,code} run the
// review methodology; reviewer-perspectives runs the assessment (multi-persona)
// lens; every reviewer also runs testing (verification gate — the /do Phase-3
// stack for review).
const REVIEWERS = {
  "reviewer-system": { agent: "general-purpose", ref: { skill: "review", file: "reviewer-system.md" }, skills: ["review", "testing"] },
  "reviewer-domain": { agent: "general-purpose", ref: { skill: "review", file: "reviewer-domain.md" }, skills: ["review", "testing"] },
  "reviewer-code": { agent: "general-purpose", ref: { skill: "review", file: "reviewer-code.md" }, skills: ["review", "testing"] },
  "reviewer-perspectives": { agent: "general-purpose", ref: { skill: "review", file: "reviewer-perspectives.md" }, skills: ["assessment", "testing"] },
};

// One roster entry: a general-purpose worker, the reference it loads, its skill
// stack, and the wave-specific lens.
function reviewer(slug, lens) {
  const r = REVIEWERS[slug];
  return { agent: r.agent, name: slug, ref: r.ref, skills: r.skills, lens };
}

// The per-finding verify pass dispatches the challenger reference with its stack.
const VERIFY_REVIEWER = "reviewer-perspectives";

// The fix loop dispatches the engineer that owns the finding's file type
// (engineerForPath, a private overlay agent when indexed) or a general-purpose
// worker that loads the file type's reference (referenceForPath), with this stack.
const FIX_SKILLS = ["programming", "testing"];

// --- Wave rosters: the four review references, applied through wave-specific
//     lenses. Each entry is a separate fresh worker, so the SAME four reviewer
//     references scale in depth across waves without inventing per-topic
//     roles. This mirrors the lens-based scheme in
//     comprehensive-review/references/wave-{1,2,3}-*.md. ----------------------
const WAVE1_AGENTS = [
  reviewer("reviewer-system", "security, input validation, error handling, API contracts"),
  reviewer("reviewer-domain", "business logic, edge cases, data integrity, state transitions"),
  reviewer("reviewer-code", "conventions, naming, dead code, performance, test coverage"),
  reviewer("reviewer-perspectives", "newcomer clarity, user-advocate, senior-maintainer view"),
];

// Tier 3 dispatches the deep-dive subset; Tier 4 adds the remaining lenses.
const WAVE2_SUBSET = [
  reviewer("reviewer-system", "deep security + concurrency + resource lifecycle"),
  reviewer("reviewer-domain", "deep correctness + data integrity + migration safety"),
  reviewer("reviewer-code", "deep performance + error paths + state machines"),
];

const WAVE2_FULL = WAVE2_SUBSET.concat([
  reviewer("reviewer-system", "API-contract compatibility + observability gaps"),
  reviewer("reviewer-perspectives", "senior-maintainer + meta-process review"),
]);

const WAVE3_AGENTS = [
  reviewer("reviewer-perspectives", "contrarian + falsifier: try to break the change"),
  reviewer("reviewer-system", "adversarial security: assume hostile input everywhere"),
  reviewer("reviewer-domain", "adversarial assumptions: challenge every invariant"),
  reviewer("reviewer-code", "simplicity challenge: is this over-engineered?"),
];

// --- Schemas (mirror skills/shared-patterns/schemas/) -------------------------

const FINDING_SCHEMA = {
  type: "object",
  required: ["title", "location", "severity"],
  properties: {
    title: { type: "string" },
    // file:line, matching the review-output-base finding pattern.
    location: { type: "string", pattern: "^[\\w./\\-]+:\\d+" },
    severity: { type: "string", enum: ["critical", "high", "medium", "low"] },
    description: { type: "string" },
    recommendation: { type: "string" },
    reviewer: { type: "string" },
  },
};

const WAVE_OUTPUT_SCHEMA = {
  type: "object",
  required: ["verdict", "findings"],
  properties: {
    verdict: { type: "string", enum: ["BLOCK", "FIX", "APPROVE"] },
    summary: { type: "string", minLength: 10 },
    findings: { type: "array", items: FINDING_SCHEMA },
    positives: { type: "array", items: { type: "string" } },
  },
};

// Per-finding adversarial verdict (mirrors the pr-review per-finding verify).
const VERIFY_SCHEMA = {
  type: "object",
  required: ["finding_title", "disposition"],
  properties: {
    finding_title: { type: "string" },
    disposition: {
      type: "string",
      enum: ["AGREE", "CHALLENGE", "DOWNGRADE", "DISMISS"],
    },
    rationale: { type: "string" },
  },
};

const FIX_SCHEMA = {
  type: "object",
  required: ["finding_title", "outcome"],
  properties: {
    finding_title: { type: "string" },
    outcome: { type: "string", enum: ["FIXED", "BLOCKED"] },
    files_changed: { type: "array", items: { type: "string" } },
    note: { type: "string" },
  },
};

// --- Helpers ------------------------------------------------------------------

const SEVERITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3 };
const SEVERITY_DOWNGRADE = { critical: "high", high: "medium", medium: "low", low: "low" };

function dedupeKey(f) {
  return `${f.location}::${f.title}`;
}

function downgradeSeverity(severity) {
  return SEVERITY_DOWNGRADE[severity] ?? severity;
}

function collectFindings(waveOutputs) {
  // waveOutputs: array of (typed wave result | null from a failed barrier slot).
  const out = [];
  for (const result of waveOutputs) {
    if (result && Array.isArray(result.findings)) {
      out.push(...result.findings);
    }
  }
  return out;
}

function hasCritical(findings) {
  return findings.some((f) => f.severity === "critical");
}

function dedupeFindings(findings) {
  // Same file:line + title -> keep the higher severity, merge reviewer credit.
  const byKey = new Map();
  for (const f of findings) {
    const key = dedupeKey(f);
    const prior = byKey.get(key);
    if (!prior) {
      byKey.set(key, { ...f, reviewers: [f.reviewer].filter(Boolean) });
      continue;
    }
    if (SEVERITY_ORDER[f.severity] < SEVERITY_ORDER[prior.severity]) {
      prior.severity = f.severity;
      prior.recommendation = f.recommendation || prior.recommendation;
    }
    if (f.reviewer && !prior.reviewers.includes(f.reviewer)) {
      prior.reviewers.push(f.reviewer);
    }
  }
  return [...byKey.values()].sort(
    (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity],
  );
}

function reviewPrompt(roster, scope, priorContext) {
  // roster is {agent, name, ref, skills, lens}; priorContext is the typed prior-wave summary
  // passed in-memory (no disk read). skillDirectives emits one exact call per
  // element of roster.skills (the full stack) — the call resolves path-
  // independent inside a native Workflow agent() dispatch (proven this session).
  // mandatoryInjections() embeds the /do completeness/density/base-instructions/
  // reference-loading block so a workflow agent gets the same context as a direct
  // /do dispatch.
  const context = priorContext
    ? `\n\nPrior-wave findings (typed, in-memory):\n${JSON.stringify(priorContext)}`
    : "";
  return (
    `You are a ${roster.name} review worker. Apply this review lens: ${roster.lens}.` +
    skillDirectives(roster.skills) +
    referenceDirective(roster.ref) +
    `\nReview the changed code for this diff scope:\n` +
    `${JSON.stringify(scope)}\n` +
    `Return only findings within your lens. The only valid dispositions are ` +
    `FIX NOW, FIX IN FOLLOW-UP (with a tracking artifact), or NOT AN ISSUE ` +
    `(with evidence). "Acceptable", "valid but deferred", and "conservative" ` +
    `are not valid dispositions. Severity is one of critical|high|medium|low.` +
    mandatoryInjections() +
    context
  );
}

// Defensive phase marker: the native runtime guarantees agent/parallel/pipeline/
// budget, but does NOT document a phase() global. Guard the call so the real
// runtime never throws if phase is absent, while the conformance harness's mock
// records the entered phase. Phase titles match meta.contract.phases.
function enterPhase(title) {
  if (typeof phase === "function") {
    phase(title);
  }
}

// --- Workflow body ------------------------------------------------------------
//
// `scope` is the diff descriptor the caller passes in (changed files, packages,
// and the right-size-review tier). `tier` honors scripts/right-size-review.py:
//   tier <= 2 -> Wave 1 only; tier 3 -> Wave 1 + Wave 2 subset (Wave 3 only on a
//   CRITICAL); tier 4 -> Wave 1 + Wave 2 full + Wave 3. Wave 3 also runs at any
//   tier once a CRITICAL surfaces (the escalation safety valve). An unset tier
//   runs every wave (tier 4): 4 + 5 + 4 = 13 reviewers. Only an explicit tier
//   shrinks the review (owner, 2026-11-09: "Comprehensive review is no longer
//   comprehensive with 1 wave").
// `implement` + `branch` clear the fix gate: `implement: true` and a work branch
// that is not main, master, or trunk. Pass both only after the operator asks
// for fixes. Otherwise the run stops after verify and returns `fix_blocked`.
// `reviewOnly: true` stops after verify even when `implement` is set (the prose
// --review-only flag).
// `modelOverride` is a model the owner named for this task. When set, every
// agent runs on it. Unset: every agent runs the `work` model, because reviewers
// and verifiers return findings that decide and the fix loop edits files.

export default async function run({
  scope,
  tier,
  fixThreshold,
  modelOverride,
  implement,
  branch,
  reviewOnly,
} = {}) {
  // Reject a bad model name before any dispatch.
  validateModelOverride(modelOverride);
  const effectiveTier = tierOrFull(tier);
  const fixBlocked = reviewOnly === true ? "reviewOnly is set" : editBlocker(implement, branch);
  const minBudgetPerFix = typeof fixThreshold === "number" ? fixThreshold : 8000;

  // Wave 1: foundation. Hard barrier — every foundation agent completes before
  // the wave is considered closed. Failed slots resolve to null and are dropped.
  enterPhase("wave-1");
  const wave1 = await parallel(
    WAVE1_AGENTS.map((r) => () =>
      agent({
        prompt: reviewPrompt(r, scope, null),
        schema: WAVE_OUTPUT_SCHEMA,
        model: modelFor("work", modelOverride),
        agentType: r.agent,
      }),
    ),
  );
  let findings = collectFindings(wave1);

  // Wave 2: deep-dive, only at tier >= 3. pipeline() streams each Wave 1
  // finding into a matched deep-dive agent without a disk re-read — agent B
  // can start while agent A is still running.
  if (effectiveTier >= 3) {
    enterPhase("wave-2");
    const wave2Roster = effectiveTier >= 4 ? WAVE2_FULL : WAVE2_SUBSET;
    const wave2Summary = { findings, source: "wave1" };
    const wave2 = await parallel(
      wave2Roster.map((r) => () =>
        agent({
          prompt: reviewPrompt(r, scope, wave2Summary),
          schema: WAVE_OUTPUT_SCHEMA,
          model: modelFor("work", modelOverride),
          agentType: r.agent,
        }),
      ),
    );
    findings = findings.concat(collectFindings(wave2));
  }

  // Wave 3: adversarial. Runs at tier 4 unconditionally, or at any tier once a
  // CRITICAL is present (escalation safety valve mirrored from the markdown).
  const wave3Required = effectiveTier >= 4 || hasCritical(findings);
  if (wave3Required) {
    enterPhase("wave-3");
    const wave3Summary = { findings, source: "wave1+2" };
    const wave3 = await parallel(
      WAVE3_AGENTS.map((r) => () =>
        agent({
          prompt: reviewPrompt(r, scope, wave3Summary),
          schema: WAVE_OUTPUT_SCHEMA,
          model: modelFor("work", modelOverride),
          agentType: r.agent,
        }),
      ),
    );
    findings = findings.concat(collectFindings(wave3));
  }

  findings = dedupeFindings(findings);

  // Per-finding adversarial verify BEFORE synthesis (mirrors the pr-review
  // gated per-finding verify). Each finding gets one challenger (a worker that
  // loads VERIFY_REVIEWER's reference, with its skill stack); DISMISS drops it from the fix queue. parallel()
  // barriers the whole verify pass.
  enterPhase("verify");
  const verdicts = await parallel(
    findings.map((f) => () =>
      agent({
        prompt:
          `You are a ${VERIFY_REVIEWER} review worker. Adversarially verify this ` +
          `review finding. Confirm it is real and correctly rated, or challenge ` +
          `it with evidence.` +
          skillDirectives(REVIEWERS[VERIFY_REVIEWER].skills) +
          referenceDirective(REVIEWERS[VERIFY_REVIEWER].ref) +
          `\nFinding:\n${JSON.stringify(f)}` +
          mandatoryInjections(),
        schema: VERIFY_SCHEMA,
        model: modelFor("work", modelOverride),
        agentType: WORKER,
      }),
    ),
  );
  const dismissed = new Set();
  const challenged = [];
  const verified = [];
  for (let i = 0; i < findings.length; i++) {
    const f = findings[i];
    const v = verdicts[i];
    const key = dedupeKey(f);
    if (v && v.disposition === "DISMISS") {
      dismissed.add(key);
      continue;
    }
    if (v && v.disposition === "DOWNGRADE") {
      verified.push({
        ...f,
        severity: downgradeSeverity(f.severity),
        verification: { disposition: "DOWNGRADE", rationale: v.rationale || "" },
      });
      continue;
    }
    if (v && v.disposition === "CHALLENGE") {
      challenged.push(key);
      verified.push({
        ...f,
        challenged: true,
        verification: { disposition: "CHALLENGE", rationale: v.rationale || "" },
      });
      continue;
    }
    verified.push(
      v
        ? { ...f, verification: { disposition: v.disposition, rationale: v.rationale || "" } }
        : f,
    );
  }
  verified.sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]);

  // The fix gate: stop before any edit unless the caller passed implement: true
  // with a non-default work branch. The verified findings are the report.
  if (fixBlocked != null) {
    return {
      tier: effectiveTier,
      wave3_ran: wave3Required,
      total_findings: findings.length,
      verified_findings: verified.length,
      verified,
      dismissed: [...dismissed],
      challenged,
      review_only: true,
      implement_requested: implement === true,
      fix_blocked: fixBlocked,
      fixes: [],
      unfixed: verified.map((f) => f.title),
      deferred_for_budget: [],
      budget_remaining: budget.remaining(),
    };
  }

  // Phase 4 fix loop, bounded by the native token budget. CRITICAL first.
  // The loop stops when findings are exhausted OR the run-wide budget can no
  // longer afford another fix agent — a hard, replayable spend ceiling. Every
  // fix agent gets the branch rule: edit only on the caller's work branch.
  enterPhase("fix");
  const queue = verified.slice();
  const fixes = [];
  const deferred = [];
  while (queue.length > 0) {
    if (budget.remaining() < minBudgetPerFix) {
      deferred.push(...queue.splice(0));
      break;
    }
    const f = queue.shift();
    const result = await agent({
      prompt:
        `Apply the fix for this verified review finding, then confirm it ` +
        `compiles and relevant tests pass. If the fix breaks tests and an ` +
        `alternative also breaks tests, return outcome BLOCKED. On a branch ` +
        `mismatch return outcome BLOCKED.` +
        branchRule(branch) +
        skillDirectives(FIX_SKILLS) +
        referenceDirective(referenceForPath(f.location)) +
        `\nFinding:\n${JSON.stringify(f)}` +
        mandatoryInjections(),
      schema: FIX_SCHEMA,
      model: modelFor("work", modelOverride),
      agentType: engineerForPath(f.location) ?? WORKER,
    });
    if (result) {
      fixes.push(result);
    }
  }

  return {
    tier: effectiveTier,
    wave3_ran: wave3Required,
    total_findings: findings.length,
    verified_findings: verified.length,
    dismissed: [...dismissed],
    challenged,
    review_only: false,
    implement_requested: true,
    fix_blocked: null,
    branch,
    fixes,
    deferred_for_budget: deferred.map((f) => f.title),
    budget_remaining: budget.remaining(),
  };
}
