// dynamic-roster.js — fixture: a FULLY-DYNAMIC-roster workflow. The roster is
// supplied entirely by the caller, so there are NO static agentType:/Skill("..")
// literals to pin. The contract declares roster:{dynamic:true} and agents:{dynamic
// :true}. The conformance validator must assert the STRUCTURAL invariant — the
// source emits a Skill( directive derived from a roster variable AND dispatches
// agentType from a roster variable — and PASS this file (not vacuously).
export const meta = {
  name: "fixture-dynamic-roster",
  description: "fully-dynamic roster; structural invariant present",
  contract: {
    phases: ["fan-out", "synthesize"],
    roster: { dynamic: true },
    agents: { dynamic: true },
    dynamic: true,
  },
};

function enterPhase(title) {
  if (typeof phase === "function") phase(title);
}

export default async function run({ scope, roster, synthAgentType } = {}) {
  enterPhase("fan-out");
  const workers = await parallel(
    roster.map((r) => () =>
      agent({
        prompt:
          `You are a ${r.lens} specialist. Invoke your methodology by name ` +
          `first: Skill("${r.skill}"). Scope: ${JSON.stringify(scope)}`,
        schema: { type: "object", required: ["summary"], properties: { summary: { type: "string" } } },
        agentType: r.agentType,
        phase: "fan-out",
      }),
    ),
  );
  enterPhase("synthesize");
  const synthesis = await agent({
    prompt: `Synthesize ${workers.length} worker outputs.`,
    schema: { type: "object", required: ["summary"], properties: { summary: { type: "string" } } },
    agentType: synthAgentType,
    phase: "synthesize",
  });
  return { workers_ran: workers.length, synthesis };
}
