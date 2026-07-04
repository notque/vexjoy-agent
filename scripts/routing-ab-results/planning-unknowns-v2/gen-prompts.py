#!/usr/bin/env python3
"""Generate A/B prompts for planning-unknowns-v2.

12 scenarios (v1's 6 + 6 new) x 2 samples per arm. Sample ids: s<N>a, s<N>b
(identical prompt text; independent generations give paired samples).
Arms: full = baseline refs (main), edited = refs with the 4 unknowns edits.
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
        "s01",
        "plan-files",
        "Task: migrate a Flask app's auth from server-side sessions to JWT. "
        "Known midway surprise you must handle in the plan's structure: the "
        "sessions table is also read by a nightly analytics job. Write the "
        "complete task_plan.md for this migration, exactly as the reference "
        "prescribes, then show how the plan file looks after the analytics-job "
        "discovery during Phase 3.",
    ),
    (
        "s02",
        "plan-files",
        "Task: refactor a Go CLI tool to add a plugin system (plugin API, "
        "discovery, two built-in plugins ported, docs). Write the complete "
        "task_plan.md exactly as the reference prescribes.",
    ),
    (
        "s03",
        "pre-plan",
        "Greenfield task (Discussion mode, no prior artifacts): build a webhook "
        "receiver service that stores incoming events and retries downstream "
        "delivery. Run Phase 0 and Phase 1 Discussion mode per the reference. "
        "Present the gray-area output you would show the user. Then assume the "
        "user replies 'defaults are fine' and produce the Phase 2 context document.",
    ),
    (
        "s04",
        "pre-plan",
        "Greenfield task (Discussion mode, no prior artifacts): add CSV import "
        "of user contacts to a small SaaS app. Run Phase 0 and Phase 1 "
        "Discussion mode per the reference and present the gray-area output "
        "you would show the user.",
    ),
    (
        "s05",
        "spec",
        "Feature request: 'nightly report emailer' for an internal analytics "
        "tool. Execute Step 1 (Gather Context) per the reference: list, "
        "verbatim, every question you would ask the user before writing "
        "stories, then state what each answer changes in the spec.",
    ),
    (
        "s06",
        "pre-plan",
        "Task (Discussion mode): design a new internal CLI that tails and "
        "filters production service logs for developers. Run Phase 0 and "
        "Phase 1 Discussion mode per the reference and present the gray-area "
        "output you would show the user.",
    ),
    (
        "s07",
        "plan-files",
        "Task: rewrite a batch ETL job (CSV drops -> Postgres) as an "
        "incremental pipeline with dedupe and late-arrival handling. Write the "
        "complete task_plan.md exactly as the reference prescribes.",
    ),
    (
        "s08",
        "plan-files",
        "Task: migrate a docs site from Jekyll to Hugo (200 pages, custom "
        "shortcodes, redirects). Midway surprise to handle in the plan's "
        "structure: the search plugin you planned on is deprecated. Write the "
        "complete task_plan.md, then show the plan after that discovery in "
        "Phase 3.",
    ),
    (
        "s09",
        "pre-plan",
        "Greenfield task (Discussion mode, no prior artifacts): add rate "
        "limiting to a public REST API gateway. Run Phase 0 and Phase 1 "
        "Discussion mode per the reference and present the gray-area output "
        "you would show the user.",
    ),
    (
        "s10",
        "pre-plan",
        "Greenfield task (Discussion mode, no prior artifacts): per-tenant "
        "data export (users, orders) for a multi-tenant SaaS. Run Phase 0 and "
        "Phase 1 Discussion mode per the reference and present the gray-area "
        "output you would show the user.",
    ),
    (
        "s11",
        "spec",
        "Feature request: 'audit log viewer' for admins of an internal tool. "
        "Execute Step 1 (Gather Context) per the reference: list, verbatim, "
        "every question you would ask the user before writing stories, then "
        "state what each answer changes in the spec.",
    ),
    (
        "s12",
        "pre-plan",
        "Task (Discussion mode): build a notification-preferences center "
        "(email, in-app, digest) for an existing web app treated as greenfield "
        "module. Run Phase 0 and Phase 1 Discussion mode per the reference and "
        "present the gray-area output you would show the user.",
    ),
]

SAMPLES = ["a", "b"]

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
    n = 0
    for arm, refs in ARMS.items():
        outdir = RUN / "prompts" / arm
        outdir.mkdir(parents=True, exist_ok=True)
        for sid, ref_key, scenario in SCENARIOS:
            ref = refs[ref_key].read_text(encoding="utf-8")
            text = TEMPLATE.format(ref=ref, scenario=scenario)
            for s in SAMPLES:
                (outdir / f"{sid}{s}.txt").write_text(text, encoding="utf-8")
                n += 1
    print(f"wrote {n} prompts ({len(SCENARIOS)} scenarios x {len(SAMPLES)} samples x 2 arms)")


if __name__ == "__main__":
    main()
