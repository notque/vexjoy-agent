# Feature lifecycle contract

State is owned by `python3 ~/.claude/scripts/feature-state.py`; never edit its
files directly. Resume the recorded phase. New end-to-end work runs DESIGN →
PLAN → IMPLEMENT → VALIDATE → RELEASE → RECORD.

| Phase | Required input | Durable output | Gate |
|---|---|---|---|
| DESIGN | request and repository evidence | `design.md` | approach, boundaries, risks, and rejected alternatives resolved |
| PLAN | accepted design | ordered tasks with owned files and checks | every design requirement mapped to an executable task |
| IMPLEMENT | accepted plan | source/test changes and deviation log | tasks complete; deviations recorded rather than hidden |
| VALIDATE | implementation | validation report | repository-required tests/build/lint plus acceptance criteria pass |
| RELEASE | passed validation and user authority | merge/deploy receipt | release mechanism succeeds and target state is observed |
| RECORD | release receipt | learning/ADR entry when warranted | incident-derived rule cites its evidence and boundary |

Do not advance on a worker claim. Missing artifacts route to their producing
phase. Validation failure routes to IMPLEMENT without weakening the check.
Release blockage preserves the validated candidate and reports the external
dependency.
