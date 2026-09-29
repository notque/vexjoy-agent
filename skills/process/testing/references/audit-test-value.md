# Test Value: Authoring Gate and Audit

One value bar for three jobs. The authoring gate checks every new or changed
test when you write it. Audit mode sweeps existing tests for low-value,
implementation-coupled, or duplicate tests and the test-only production seams
they keep alive. Campaign mode prunes one whole subsystem's test surface.
Optimize for confidence, not deletion count.

Test layout in this repo: `scripts/tests/`, `hooks/tests/`, and top-level
`tests/`. pytest config lives in `pyproject.toml`.

## Authoring gate

Before you add a test, answer four questions. A missing answer means do not add
it yet.

1. What observable behavior, invariant, or independent contract does it protect?
2. What credible regression makes it fail?
3. Why does existing coverage not already catch that failure? Each contract has
   one primary test owner at the strongest boundary. Another layer needs its
   own distinct risk, such as a subprocess, file I/O, or hook-event failure the
   owner cannot reach. Prefer a new `pytest.mark.parametrize` case or a shared
   fixture over a near-duplicate test. Consolidate duplicated setup in the same
   change.
4. Does it need a production seam (module global, flag, wrapper, injection
   hook, `_private` helper made importable) that no production caller needs? If
   yes, move the test to the real boundary instead: the script's CLI, the
   hook's stdin/stdout event contract, or the module's public function.

Then check the test against every [junk pattern](#junk-patterns). A match fails
the gate unless the [retention bar](#retention-bar) names the contract it
independently guards. A test that breaks under a behavior-preserving refactor
asserts implementation, not behavior. Rewrite it at the owning boundary before
you land it.

A bug regression test must fail on the pre-fix code for the intended reason and
pass after the fix at the owner boundary. A regression test that never failed
proves the mock, not the fix. One regression at the owner boundary covers the
bug. Do not replay the same scenario at every layer it crosses.

## Junk patterns

The shared checklist for every mode. The authoring gate rejects a new test that
matches one, and audits hunt for existing tests that do.

- assertion-free coverage probes;
- self-comparisons and identity copiers;
- copied fixtures, inventories, manifests, or export lists (for example, a
  hardcoded list of skills, agents, or hooks that mirrors the directory);
- exact source, import, or string greps;
- private predicate or call-shape tests duplicated at real boundaries;
- duplicate invocations of the same contract;
- per-hook or per-script replays of a shared helper's tests;
- tests whose only purpose is preserving test-only globals, wrappers, or
  importable privates;
- dead production code whose only callers are tests;
- expected values produced by the helper or renderer under test;
- mocks that implement the asserted behavior, or one identical mock standing in
  for different APIs;
- fixtures that supply the result, ordering, or callback the owner should
  produce, or persistence asserted against a store the path never writes;
- capability tests that restate declared flags or frontmatter instead of
  exercising the behavior the flag promises;
- negative controls that pass for an unrelated reason, such as a denial from a
  different guard or a rejection the production path never reaches;
- names or fixtures that promise more than the input exercises, such as a
  "blocks the write" test that never asserts the hook's block decision.

## Value bar

A test justifies its maintenance cost by protecting behavior, a credible
regression, or an independently meaningful contract. In an audit, an existing
test that must change for a behavior-preserving refactor is suspect, not
automatically deletable. The authoring gate still rejects new ones.

Before you judge a candidate, read the complete test and its production owner:
entry point, callers, callees, sibling implementations, overlapping tests, CI
wiring in `.github/workflows/`, and relevant `git log`. Read the root and any
scoped `CLAUDE.md` first. When the test claims dependency-backed behavior,
inspect the dependency source or types directly.

## Discovery

Keep discovery read-only and report evidence before editing. For broad scope,
run parallel discovery lanes:

- `scripts/` and `scripts/tests/`;
- `hooks/` and `hooks/tests/`;
- top-level `tests/`, validators (`scripts/validate-*.py`), and `install.sh`
  coverage;
- a cross-cutting sweep for the [junk patterns](#junk-patterns).

Outside campaign mode, prefer a few high-confidence candidates over a large
speculative inventory.

## Retention bar

Keep a test when it independently enforces a contract others depend on:

- hook event contract (stdin JSON in, decision or context out, exit codes);
- script CLI flags, exit codes, and output format that other tools or CI read;
- skill and agent frontmatter, `INDEX.json` schema, and routing behavior;
- `install.sh` and sync behavior;
- database schema and migrations (learning db, telemetry store);
- security gates: secret scans, leak gates, public-bind and path guards;
- defaults, file layout, or byte-exact output a consumer parses.

Also keep:

- call ordering when order is observable behavior;
- regressions with a credible failure mode;
- source inspection when it is the cheapest independent guard: it fails when
  the contract changes (the user-facing key, byte, or path) and survives an
  identifier-only refactor;
- a retained test that fails on the baseline. Treat it as a possible product
  bug: reproduce it and fix the owner instead of deleting the test.

Static or slow is not a deletion reason. A test that resembles implementation
may still be the independent contract. Prove otherwise before you remove it.

## Candidate evidence

Record every field before editing. A missing field means the candidate is not
ready for deletion.

- exact test name and location;
- what failure it can actually detect;
- non-test callers of the covered production or support seam;
- stronger remaining owner-boundary proof, or why no proof is needed;
- relevant history and the reason the test or seam exists;
- production or test-support deletion it unlocks;
- risk and the focused validation command.

## Edit shape

Choose one coherent owner-boundary batch. Delete obsolete test-only globals,
wrappers, importable privates, and dead production paths instead of keeping
aliases. Move retained regressions to their canonical owner's test file.
Consolidate repeated assertions into one parametrized contract.

Prefer net-negative production LOC. Do not add replacement tests that restate
the same implementation. Do not turn uncertain candidates into cleanup to raise
deletion counts.

## Campaign mode

Prune one whole subsystem's test surface, such as one hook family, one script
family, or the validators. Scope the campaign to the subsystem's test files
and the production seams they touch. Inventory every test in scope, record
[candidate evidence](#candidate-evidence) for each deletion, and land it as one
or more coherent PRs. Stop at the subsystem boundary; queue anything outside it
as a follow-up.

## Validation

1. Run the smallest owner and sibling tests:
   `python -m pytest <path> -n 0 -q`.
2. For a removed source grep or plan assertion, run the script, validator, or
   `--dry-run` that owns the real contract.
3. Run `ruff check . --config pyproject.toml` and
   `ruff format --check . --config pyproject.toml`, then `git diff --check`.
4. If you removed or renamed scripts or tests, run
   `python3 scripts/validate-doc-counts.py` and
   `python3 scripts/validate-references.py`.
5. Run the full default suite: `python -m pytest --tb=short -q`.
6. Inspect `git diff --numstat`. Report production and tooling LOC separately
   from tests and test support.
7. After final audit edits, run the `review` skill on the diff.

## Landing and continuation

Commit, push, open a PR, or merge only when the user asks. Use the
`pr-workflow` skill. Land one coherent PR at a time. After it merges, refresh
from current `main` and rerun read-only discovery for the next high-confidence
batch.

## Handoff

Report:

- root cause and removed low-value categories;
- production owner simplifications;
- retained false positives and why they stay;
- focused and full proof actually run;
- production versus test LOC;
- PR and merge state;
- named follow-ups.
