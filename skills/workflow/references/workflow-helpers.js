// workflow-helpers.js
//
// Shared prompt-builder helpers for native .js workflows (fan-out-workflow.js,
// comprehensive-review-workflow.js). Both workflows attach the FULL /do skill
// stack to every dispatched agent and embed the /do mandatory injection block,
// so a dispatched workflow agent receives the SAME context it would have gotten
// from a direct /do dispatch — not a single bare skill.
//
// Two builders, used identically by both workflows:
//   - skillDirectives(skills): emit one Skill("<name>") directive for EVERY skill
//     in the roster entry's skills list (the Phase-3 enhancement stack: primary
//     skill + test-driven-development/verification-before-completion + the
//     per-task-type anti-rationalization patterns the caller stacked).
//   - mandatoryInjections(): the /do Phase 4 Step 2 MANDATORY block — completeness
//     standard, density standard, base-instructions load, reference-loading
//     instruction. Verbatim from skills/meta/do/SKILL.md Phase 4 Step 2.
//
// Determinism: no Date.now()/Math.random(); pure string composition only.

// Emit a Skill("<name>") directive for EVERY skill in the list. The native
// runtime resolves Skill("name") path-independent inside an agent() dispatch
// (proven this session). Returns "" for an empty/absent list so a skill-less
// roster entry adds nothing.
export function skillDirectives(skills) {
  const list = Array.isArray(skills) ? skills.filter((s) => typeof s === "string" && s) : [];
  if (list.length === 0) return "";
  const lines = list.map((s) => `- Skill("${s}")`).join("\n");
  return (
    `\nInvoke EACH of these methodologies by name first, in order, then report ` +
    `through their structure:\n${lines}`
  );
}

// The /do Phase 4 Step 2 MANDATORY injection block, verbatim. Every dispatched
// workflow agent gets the same completeness/density/base-instructions/reference-
// loading context a direct /do dispatch injects. Static string (cacheable).
export function mandatoryInjections() {
  return (
    `\n\n## Operating standards (injected)\n` +
    `- Deliver the finished product. Ship the complete thing.\n` +
    `- Write dense: high fidelity, minimum words. Cut filler, prefer tables over ` +
    `paragraphs, report what changed — not how.\n` +
    `- Before starting work, also load \`agents/base-instructions.md\` for ` +
    `universal operational rules.\n` +
    `- Before starting work, read your agent .md file to find the Reference ` +
    `Loading Table. Load EVERY reference file whose signal matches this task. ` +
    `Load greedily — if multiple signals match, load all matching references.`
  );
}
