# routing-ab golden fixtures

Byte-level snapshots of every artifact the PRE-EXTENSION `scripts/routing-ab-test.py`
(commit 7d923221, before feat/route-ab-harness) produced over `../corpus.json` with
`pre_route_stub.json`, manifest stub `"STUB MANIFEST v1"`, the `../answers/*.json`
Haiku stubs, and `../judge-output.json`.

`scripts/tests/test_routing_ab_harness.py::TestLegacyByteIdentical` runs the current
script in legacy mode (no `--manifest-arm`) over the same inputs and byte-compares.
A diff here means the extension broke back-compat.

Regenerate ONLY from a commit whose legacy behavior is known-good, with the same
stubbing the test applies (see `load_harness` + `run_legacy_pipeline`), then copy
queries.json, manifest-used.txt, raw.json, judge-input.json, uid-map.json,
scoreboard.json, pre-route-map.json, and prompts/ here.

2026-07-01: prompts/ regenerated after the PROMPT_TEMPLATE git rule was
back-ported from production skills/meta/do/SKILL.md (genuine-git-only).
All other artifacts are unchanged pre-extension snapshots.
