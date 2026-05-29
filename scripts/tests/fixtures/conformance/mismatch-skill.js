// mismatch-skill.js — fixture: meta.contract.roster declares reviewer-system uses
// Skill("systematic-code-review"), but the source never emits that Skill token for
// it (the Skill directive is missing). The conformance validator must FAIL on the
// STATIC roster/skill check (declared skill absent from source tokens).
export const meta = {
  name: "fixture-mismatch-skill",
  description: "contract roster skill is not present in source",
  contract: {
    phases: ["wave-1"],
    roster: [{ agentType: "reviewer-system", skill: "systematic-code-review" }],
    agents: { static: 1, dynamic: false },
    dynamic: false,
  },
};

function enterPhase(title) {
  if (typeof phase === "function") phase(title);
}

export default async function run({ scope } = {}) {
  enterPhase("wave-1");
  await agent({
    // No Skill("...") token at all — the declared skill is unbacked.
    prompt: `You are reviewer-system. Review scope: ${JSON.stringify(scope)}`,
    schema: { type: "object", required: ["verdict"], properties: { verdict: { type: "string", enum: ["APPROVE"] } } },
    agentType: "reviewer-system",
  });
  return {};
}
