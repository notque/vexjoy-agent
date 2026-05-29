// matching.js — fixture: a minimal native workflow whose meta.contract MATCHES
// its actual phases / static Wave-1 roster / agentType+Skill tokens. The
// conformance validator must PASS this file.
export const meta = {
  name: "fixture-matching-workflow",
  description: "minimal conformant fixture",
  contract: {
    phases: ["wave-1", "verify"],
    roster: [
      { agentType: "reviewer-system", skill: "systematic-code-review" },
      { agentType: "reviewer-perspectives", skill: "roast" },
    ],
    agents: { static: 2, dynamic: false },
    dynamic: true,
  },
};

function enterPhase(title) {
  if (typeof phase === "function") phase(title);
}

const WAVE1 = [
  { agent: "reviewer-system", skill: "systematic-code-review" },
  { agent: "reviewer-perspectives", skill: "roast" },
];

export default async function run({ scope, tier } = {}) {
  enterPhase("wave-1");
  const wave1 = await parallel(
    WAVE1.map((r) => () =>
      agent({
        prompt:
          `You are ${r.agent}. Invoke your review methodology by name first: ` +
          `Skill("${r.skill}"). Scope: ${JSON.stringify(scope)}`,
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
