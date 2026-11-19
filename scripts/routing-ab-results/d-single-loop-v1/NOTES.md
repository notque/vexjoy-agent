## Notes on scoring

- Jev: run 2's prepare calls were served from the Jev answer cache (about 9 ms, no usage), so both runs of /d share the same attachment evidence; 14 live Jev calls.
- g14-project-skill: the expected skill is a private overlay skill and is absent from this checkout's manifest for that request (0 matches), so neither arm could pick it. The row is unscoreable here; labels were not changed after the run.
- g07-docs-from-source: both arms picked `workflow` with `doc-pipeline` in both runs; the frozen label accepts `writing` or `toolkit` as the skill.
- Before the full run, a one-task smoke run (g01, one run per router) cost $0.43 in model calls and one Jev call that failed (gateway bridge dependencies missing in the worktree; fixed by linking them).
