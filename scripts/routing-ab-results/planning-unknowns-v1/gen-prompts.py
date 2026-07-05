#!/usr/bin/env python3
"""Generate A/B prompts for planning-unknowns-v1.

Arms: full = baseline refs (main), edited = refs with the 4 unknowns edits.
Each prompt = one reference file verbatim + a planning scenario. The model
follows the reference and emits the artifact. Judge compares pairs blind.
"""

from pathlib import Path

RUN = Path(__file__).resolve().parent
REPO = RUN.parents[2]
REFS = REPO / "skills/process/planning/references"

ARMS = {
    "full": {
        "plan-files": RUN / ".baseline-plan-files.md",
        "pre-plan": RUN / ".baseline-pre-plan.md",
        "spec": RUN / ".baseline-spec.md",
    },
    "edited": {
        "plan-files": REFS / "plan-files.md",
        "pre-plan": REFS / "pre-plan.md",
        "spec": REFS / "spec.md",
    },
}

SCENARIOS = [
    (
        "s1",
        "plan-files",
        "Task: migrate a Flask app's auth from server-side sessions to JWT. "
        "Known midway surprise you must handle in the plan's structure: the "
        "sessions table is also read by a nightly analytics job. Write the "
        "complete task_plan.md for this migration, exactly as the reference "
        "prescribes, then show how the plan file looks after the analytics-job "
        "discovery during Phase 3.",
    ),
    (
        "s2",
        "plan-files",
        "Task: refactor a Go CLI tool to add a plugin system (plugin API, "
        "discovery, two built-in plugins ported, docs). Write the complete "
        "task_plan.md exactly as the reference prescribes.",
    ),
    (
        "s3",
        "pre-plan",
        "Greenfield task (Discussion mode, no prior artifacts): build a webhook "
        "receiver service that stores incoming events and retries downstream "
        "delivery. Run Phase 0 and Phase 1 Discussion mode per the reference. "
        "Present the gray-area output you would show the user. Then assume the "
        "user replies 'defaults are fine' and produce the Phase 2 context document.",
    ),
    (
        "s4",
        "pre-plan",
        "Greenfield task (Discussion mode, no prior artifacts): add CSV import "
        "of user contacts to a small SaaS app. Run Phase 0 and Phase 1 "
        "Discussion mode per the reference and present the gray-area output "
        "you would show the user.",
    ),
    (
        "s5",
        "spec",
        "Feature request: 'nightly report emailer' for an internal analytics "
        "tool. Execute Step 1 (Gather Context) per the reference: list, "
        "verbatim, every question you would ask the user before writing "
        "stories, then state what each answer changes in the spec.",
    ),
    (
        "s6",
        "pre-plan",
        "Task (Discussion mode): design a new internal CLI that tails and "
        "filters production service logs for developers. Run Phase 0 and "
        "Phase 1 Discussion mode per the reference and present the gray-area "
        "output you would show the user.",
    ),
]

TEMPLATE = """You are a planning agent. Follow the reference document below exactly. \
Where the reference tells you to ask the user, show the questions/output you would \
present; where the scenario supplies answers, use them. Output only the requested \
artifact in markdown.

<reference>
{ref}
</reference>

Scenario:
{scenario}
"""


def main():
    for arm, refs in ARMS.items():
        outdir = RUN / "prompts" / arm
        outdir.mkdir(parents=True, exist_ok=True)
        for sid, ref_key, scenario in SCENARIOS:
            ref = refs[ref_key].read_text(encoding="utf-8")
            (outdir / f"{sid}.txt").write_text(TEMPLATE.format(ref=ref, scenario=scenario), encoding="utf-8")
    print(f"wrote {len(SCENARIOS)} prompts per arm")


if __name__ == "__main__":
    main()
