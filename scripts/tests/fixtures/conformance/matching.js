// matching.js — fixture: a minimal native workflow whose meta.contract MATCHES
// its actual phases / static Wave-1 roster / agentType+Skill tokens. Each roster
// entry carries a `skills` LIST and the body emits one Skill("..") per element.
// The conformance validator must PASS this file.
export const meta = {
  name: "fixture-matching-workflow",
  description: "minimal conformant fixture",
  contract: {
    phases: ["wave-1", "verify"],
    roster: [
      { agentType: "reviewer-system", skills: ["systematic-code-review", "verification-before-completion"] },
      { agentType: "reviewer-perspectives", skills: ["roast", "verification-before-completion"] },
    ],
    agents: { static: 2, dynamic: false },
    dynamic: true,
  },
};

function enterPhase(title) {
  if (typeof phase === "function") phase(title);
}

// Emit one Skill("..") directive per element of the skills list.
function skillDirectives(skills) {
  return (skills || []).map((s) => `Skill("${s}")`).join(" ");
}

const WAVE1 = [
  { agent: "reviewer-system", skills: ["systematic-code-review", "verification-before-completion"] },
  { agent: "reviewer-perspectives", skills: ["roast", "verification-before-completion"] },
];

export default async function run({ scope, tier } = {}) {
  enterPhase("wave-1");
  const wave1 = await parallel(
    WAVE1.map((r) => () =>
      agent({
        prompt:
          `You are ${r.agent}. Invoke your methodologies by name first: ` +
          `${skillDirectives(r.skills)}. Scope: ${JSON.stringify(scope)}`,
        schema: { type: "object", required: ["verdict", "findings"], properties: { verdict: { type: "string", enum: ["APPROVE"] }, findings: { type: "array" } } },
        agentType: r.agent,
      }),
    ),
  );
  enterPhase("verify");
  await agent({
    prompt: `Adversarially verify. tier=${tier}`,
    schema: { type: "object", required: ["disposition"], properties: { disposition: { type: "string", enum: ["AGREE"] } } },
  });
  return { wave1_count: wave1.length };
}
