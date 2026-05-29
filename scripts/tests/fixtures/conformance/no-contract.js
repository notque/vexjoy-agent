// no-contract.js — fixture: a native workflow with meta.name but NO meta.contract.
// Such a file is prose-only / legacy and is EXEMPT: the conformance validator must
// SKIP it (not fail it).
export const meta = {
  name: "fixture-no-contract",
  description: "no conformance contract declared — exempt from the gate",
};

export default async function run() {
  return {};
}
