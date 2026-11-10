// workflow-helpers.js
//
// Shared prompt-builder helpers for native .js workflows (fan-out-workflow.js,
// comprehensive-review-workflow.js). Both workflows attach the FULL /do skill
// stack to every dispatched agent and embed the /do mandatory injection block,
// so a dispatched workflow agent receives the SAME context it would have gotten
// from a direct /do dispatch — not a single bare skill.
//
// Model choice also lives here, in one table. Workflow scripts call
// modelFor(role, modelOverride) and never name a model themselves;
// scripts/validate-workflow-conformance.py fails a literal model string in any
// other workflow .js file.
//
// Two builders, used identically by both workflows:
//   - skillDirectives(skills): emit one exact Skill-tool call for EVERY skill
//     in the roster entry's skills list (the Phase-3 enhancement stack: primary
//     skill + testing (verification) + the
//     per-task-type anti-rationalization patterns the caller stacked).
//   - mandatoryInjections(): the /do Phase 4 Step 2 MANDATORY block — completeness
//     standard, density standard, base-instructions load, reference-loading
//     instruction. Verbatim from skills/meta/do/SKILL.md Phase 4 Step 2.
//
// Determinism: no Date.now()/Math.random(); pure string composition only.

import agentIndex from "../../../../agents/INDEX.json" with { type: "json" };
import skillIndex from "../../../INDEX.json" with { type: "json" };

const NAME_RE = /^[a-z0-9][a-z0-9-]*$/;

function indexNames(index, key, label) {
  const entries = index && index[key];
  if (!entries || typeof entries !== "object" || Array.isArray(entries)) {
    throw new Error(`Trusted ${label} index is unreadable or empty.`);
  }
  const names = Object.keys(entries);
  if (names.length === 0) {
    throw new Error(`Trusted ${label} index is unreadable or empty.`);
  }
  return new Set(names);
}

const KNOWN_AGENTS = indexNames(agentIndex, "agents", "agent");
const KNOWN_SKILLS = indexNames(skillIndex, "skills", "skill");

// --- Model choice -------------------------------------------------------------
// One model per role. The role states what the dispatched agent does:
//   gather: read-only locate, collect, or fetch. A later stage judges the result.
//   work:   edits, verification, findings that decide, and anything else.
//   lead:   synthesis across many agents, architecture, and final reports.
//           `undefined` makes agent() inherit the session model.
const ROLE_MODELS = { gather: "haiku", work: "opus", lead: undefined };
const MODEL_ALIASES = new Set(["haiku", "sonnet", "opus", "fable"]);
const MODEL_ID_RE = /^claude-[a-z0-9][a-z0-9.-]*$/;

// Return the caller's model override, or undefined when none is set. Throws on
// a value that is not a model alias or a `claude-` model ID. Call it at the top
// of run(): a throw inside a parallel() thunk becomes a silent null slot.
export function validateModelOverride(override) {
  if (override === undefined || override === null || override === "") {
    return undefined;
  }
  if (typeof override !== "string") {
    throw new TypeError("modelOverride: model name must be a string.");
  }
  if (!MODEL_ALIASES.has(override) && !MODEL_ID_RE.test(override)) {
    throw new TypeError(`modelOverride: unknown model ${JSON.stringify(override)}.`);
  }
  return override;
}

// Return the model for a role. `override` is the run arg `modelOverride`: when
// the owner names a model for the task, it wins for every role.
export function modelFor(role, override) {
  if (!Object.hasOwn(ROLE_MODELS, role)) {
    throw new TypeError(`modelFor: unknown role ${JSON.stringify(role)}.`);
  }
  return validateModelOverride(override) ?? ROLE_MODELS[role];
}

// --- Roster size --------------------------------------------------------------
// A named full-coverage pipeline (comprehensive-review, toolkit-improvement)
// given no tier runs every wave. Only an explicit tier shrinks it: the tier
// scripts/right-size-review.py computed from a real diff, or one the caller
// names. Owner, 2026-11-09: "Comprehensive review is no longer comprehensive
// with 1 wave". Rule owner: skills/meta/do/references/workflow-dispatch.md.
export const FULL_TIER = 4;

// Return the caller's tier, or FULL_TIER when none is set. Throws on a value
// that is not a finite number, so a mistyped tier never picks a roster
// silently. Call it at the top of run(), before any dispatch.
export function tierOrFull(tier) {
  if (tier === undefined || tier === null) return FULL_TIER;
  if (typeof tier !== "number" || !Number.isFinite(tier)) {
    throw new TypeError(`tier: expected a number, got ${JSON.stringify(tier)}.`);
  }
  return tier;
}

// --- Edit gate ----------------------------------------------------------------
// A workflow edits files only when the caller passes `implement: true` and a
// non-default work `branch`. The two args carry the operator's approval; a
// request to review or evaluate never edits.
export const DEFAULT_BRANCHES = ["main", "master", "trunk"];
const BRANCH_RE = /^[A-Za-z0-9][A-Za-z0-9._/-]*$/;

// Return why editing must not run, or null when the caller cleared the gate.
export function editBlocker(implement, branch) {
  if (implement !== true) return "implement is not set; no file is edited by default";
  if (typeof branch !== "string" || !BRANCH_RE.test(branch)) {
    return "implement needs `branch`: the non-default work branch to edit on";
  }
  if (DEFAULT_BRANCHES.includes(branch)) {
    return `implement refuses the default branch ${branch}`;
  }
  return null;
}

// The rule every editing agent gets: edit only on the caller's work branch.
export function branchRule(branch) {
  return (
    `\nBranch rule: before any edit, run \`git branch --show-current\`. Edit only ` +
    `when it prints \`${branch}\`. If it prints anything else, including ` +
    `${DEFAULT_BRANCHES.join(", ")}, make no edit and report every task as ` +
    `blocked, naming the branch you found. Never switch, create, or reset a ` +
    `branch, and never commit or push.\n`
  );
}

// --- Engineer selection -------------------------------------------------------
// Map a file path (a bare path or `path:line`) to the engineer agent that edits
// that file type. Returns undefined when no listed engineer fits; the caller
// then dispatches without agentType.
const ENGINEER_BY_EXTENSION = {
  py: "python-general-engineer",
  go: "golang-general-engineer",
  ts: "typescript-frontend-engineer",
  tsx: "typescript-frontend-engineer",
  jsx: "typescript-frontend-engineer",
  js: "nodejs-api-engineer",
  mjs: "nodejs-api-engineer",
  cjs: "nodejs-api-engineer",
  rs: "rust-general-engineer",
  kt: "kotlin-general-engineer",
  swift: "swift-general-engineer",
  php: "php-general-engineer",
  md: "technical-documentation-engineer",
};

export function engineerForPath(path) {
  if (typeof path !== "string") return undefined;
  const file = path.replace(/:\d+.*$/, "");
  const match = /\.([A-Za-z0-9]+)$/.exec(file);
  const name = match ? ENGINEER_BY_EXTENSION[match[1].toLowerCase()] : undefined;
  return name && KNOWN_AGENTS.has(name) ? name : undefined;
}

export function validateAgentName(name, label = "agentType") {
  if (typeof name !== "string") {
    throw new TypeError(`${label}: agent name must be a string.`);
  }
  if (!NAME_RE.test(name)) {
    throw new TypeError(`${label}: invalid agent name ${JSON.stringify(name)}.`);
  }
  if (KNOWN_SKILLS.has(name)) {
    throw new TypeError(`${label}: ${name} is a skill, not an agent.`);
  }
  if (!KNOWN_AGENTS.has(name)) {
    throw new TypeError(`${label}: unknown agent ${name}.`);
  }
  return name;
}

export function validateSkillNames(skills, label = "skills") {
  if (!Array.isArray(skills)) {
    throw new TypeError(`${label}: skills must be an array.`);
  }
  if (skills.length === 0) {
    throw new TypeError(`${label}: expected at least one skill.`);
  }

  const names = [];
  const seen = new Set();
  for (const name of skills) {
    if (typeof name !== "string") {
      throw new TypeError(`${label}: skill name must be a string.`);
    }
    if (!NAME_RE.test(name)) {
      throw new TypeError(`${label}: invalid skill name ${JSON.stringify(name)}.`);
    }
    if (KNOWN_AGENTS.has(name)) {
      throw new TypeError(`${label}: ${name} is an agent, not a skill.`);
    }
    if (!KNOWN_SKILLS.has(name)) {
      throw new TypeError(`${label}: unknown skill ${name}.`);
    }
    if (!seen.has(name)) {
      seen.add(name);
      names.push(name);
    }
  }
  return names;
}

export function validateRoster(roster, label = "roster") {
  if (!Array.isArray(roster)) {
    throw new TypeError(`${label}: roster must be an array.`);
  }
  if (roster.length === 0) {
    throw new TypeError(`${label}: expected at least one roster entry.`);
  }
  return roster.map((entry, index) => {
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
      throw new TypeError(`${label}[${index}]: roster entry must be an object.`);
    }
    return {
      ...entry,
      agentType: validateAgentName(entry.agentType, `${label}[${index}].agentType`),
      skills: validateSkillNames(entry.skills, `${label}[${index}].skills`),
    };
  });
}

// Emit the A/B-winning action contract for every validated skill in the list.
export function skillDirectives(skills) {
  const list = validateSkillNames(skills);
  return `\n${list.map((s) => `Call the Skill tool with \`${s}\`.`).join("\n")}`;
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
