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
// Runtime contract (see ../../../dynamic-workflows-vs-vexjoy-diff.md):
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

export const meta = {
  name: "comprehensive-review-workflow",
  description:
    "Four-wave code review as a deterministic native Workflow: tier-scaled waves (right-sizing), schema-validated typed findings per wave, parallel barriers within a wave, pipelined Wave 1 -> Wave 2 hand-off, per-finding adversarial verify before synthesis, and a budget-bounded fix loop. Mirrors comprehensive-review.md; that markdown flow stays the fallback.",
};

// --- Wave rosters (mirror the markdown references) ----------------------------

const WAVE1_AGENTS = [
  "reviewer-security",
  "reviewer-business-logic",
  "reviewer-architecture",
  "reviewer-performance",
  "reviewer-error-handling",
  "reviewer-concurrency",
  "reviewer-testing",
  "reviewer-api-contracts",
  "reviewer-language-specialist",
  "reviewer-data-integrity",
  "reviewer-observability",
  "reviewer-dependencies",
];

// Tier 3 dispatches the highest-signal subset of Wave 2; Tier 4 runs all ten.
const WAVE2_SUBSET = [
  "reviewer-deep-security",
  "reviewer-deep-correctness",
  "reviewer-deep-concurrency",
  "reviewer-deep-data-integrity",
  "reviewer-deep-api-contracts",
];

const WAVE2_FULL = WAVE2_SUBSET.concat([
  "reviewer-deep-performance",
  "reviewer-deep-resource-lifecycle",
  "reviewer-deep-error-paths",
  "reviewer-deep-state-machines",
  "reviewer-deep-migration-safety",
]);

const WAVE3_AGENTS = [
  "reviewer-adversarial-security",
  "reviewer-adversarial-correctness",
  "reviewer-adversarial-assumptions",
  "reviewer-adversarial-simplicity",
  "reviewer-adversarial-falsifier",
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
    const key = `${f.location}::${f.title}`;
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

function reviewPrompt(role, scope, priorContext) {
  // priorContext is the typed prior-wave summary passed in-memory (no disk read).
  const context = priorContext
    ? `\n\nPrior-wave findings (typed, in-memory):\n${JSON.stringify(priorContext)}`
    : "";
  return (
    `You are ${role}. Review the changed code for this diff scope:\n` +
    `${JSON.stringify(scope)}\n` +
    `Return only findings within your focus. The only valid dispositions are ` +
    `FIX NOW, FIX IN FOLLOW-UP (with a tracking artifact), or NOT AN ISSUE ` +
    `(with evidence). "Acceptable", "valid but deferred", and "conservative" ` +
    `are not valid dispositions. Severity is one of critical|high|medium|low.` +
    context
  );
}

// --- Workflow body ------------------------------------------------------------
//
// `scope` is the diff descriptor the caller passes in (changed files, packages,
// and the right-size-review tier). `tier` honors scripts/right-size-review.py:
//   tier 2 -> Wave 1 only; tier 3 -> Wave 1 + Wave 2 subset (Wave 3 only on a
//   CRITICAL); tier 4 -> Wave 1 + Wave 2 full + Wave 3. Wave 3 also runs at any
//   tier once a CRITICAL surfaces (the escalation safety valve).

export default async function run({ scope, tier, fixThreshold }) {
  const effectiveTier = typeof tier === "number" ? tier : 4;
  const minBudgetPerFix = typeof fixThreshold === "number" ? fixThreshold : 8000;

  // Wave 1: foundation. Hard barrier — every foundation agent completes before
  // the wave is considered closed. Failed slots resolve to null and are dropped.
  const wave1 = await parallel(
    WAVE1_AGENTS.map((role) => () =>
      agent({
        prompt: reviewPrompt(role, scope, null),
        schema: WAVE_OUTPUT_SCHEMA,
        model: "sonnet",
      }),
    ),
  );
  let findings = collectFindings(wave1);

  // Wave 2: deep-dive, only at tier >= 3. pipeline() streams each Wave 1
  // finding into a matched deep-dive agent without a disk re-read — agent B
  // can start while agent A is still running.
  if (effectiveTier >= 3) {
    const wave2Roster = effectiveTier >= 4 ? WAVE2_FULL : WAVE2_SUBSET;
    const wave2Summary = { findings, source: "wave1" };
    const wave2 = await parallel(
      wave2Roster.map((role) => () =>
        agent({
          prompt: reviewPrompt(role, scope, wave2Summary),
          schema: WAVE_OUTPUT_SCHEMA,
          model: "sonnet",
        }),
      ),
    );
    findings = findings.concat(collectFindings(wave2));
  }

  // Wave 3: adversarial. Runs at tier 4 unconditionally, or at any tier once a
  // CRITICAL is present (escalation safety valve mirrored from the markdown).
  const wave3Required = effectiveTier >= 4 || hasCritical(findings);
  if (wave3Required) {
    const wave3Summary = { findings, source: "wave1+2" };
    const wave3 = await parallel(
      WAVE3_AGENTS.map((role) => () =>
        agent({
          prompt: reviewPrompt(role, scope, wave3Summary),
          schema: WAVE_OUTPUT_SCHEMA,
          model: "sonnet",
        }),
      ),
    );
    findings = findings.concat(collectFindings(wave3));
  }

  findings = dedupeFindings(findings);

  // Per-finding adversarial verify BEFORE synthesis (mirrors the pr-review
  // gated per-finding verify). Each finding gets one challenger; DISMISS drops
  // it from the fix queue. parallel() barriers the whole verify pass.
  const verdicts = await parallel(
    findings.map((f) => () =>
      agent({
        prompt:
          `Adversarially verify this review finding. Confirm it is real and ` +
          `correctly rated, or challenge it with evidence. Finding:\n` +
          `${JSON.stringify(f)}`,
        schema: VERIFY_SCHEMA,
        model: "sonnet",
      }),
    ),
  );
  const dismissed = new Set(
    verdicts
      .filter((v) => v && v.disposition === "DISMISS")
      .map((v) => v.finding_title),
  );
  const verified = findings.filter((f) => !dismissed.has(f.title));

  // Phase 4 fix loop, bounded by the native token budget. CRITICAL first.
  // The loop stops when findings are exhausted OR the run-wide budget can no
  // longer afford another fix agent — a hard, replayable spend ceiling.
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
        `alternative also breaks tests, return outcome BLOCKED. Finding:\n` +
        `${JSON.stringify(f)}`,
      schema: FIX_SCHEMA,
      model: "sonnet",
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
    fixes,
    deferred_for_budget: deferred.map((f) => f.title),
    budget_remaining: budget.remaining(),
  };
}
