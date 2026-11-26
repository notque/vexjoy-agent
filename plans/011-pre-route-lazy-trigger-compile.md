# Plan 011: pre-route compiles only the trigger patterns a request can match

> **Executor instructions**: follow this plan step by step. Run every
> verification command and confirm the expected result before the next step.
> If a STOP condition occurs, stop and report. Do not improvise. Do not run
> any step marked OWNER-GATED. When done, update this plan's row in
> `plans/README.md`, unless a reviewer dispatched you and maintains the index.
>
> **Drift check (run first)**: `git diff --stat c68ac1fe..HEAD -- scripts/pre-route.py scripts/tests/test_pre_route.py`
> If an in-scope file changed, compare the "Current state" excerpts with the
> live code. A mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: perf
- **Kind**: fix
- **Planned at**: commit `c68ac1fe`, 2026-11-26

## Why this matters

Every `/do` request runs `python3 "$SDIR/pre-route.py" --request-file "$REQUEST_FILE" --json-compact`
(`skills/meta/do/SKILL.md:179`). On the planning host it takes 209 ms
(median of 5). A profile shows about 180 ms of that in `build_match_table`,
which compiles a regex for every force-route trigger (761 patterns) before it
looks at the request, though a typical request matches none of them. The
`functools.cache` on `_build_pattern` helps only when one process routes many
requests (`scripts/routing-benchmark.py`); the CLI routes one request per
process, so it pays the full compile every time.

A scratch prototype (lazy `pattern`, plus a substring prefilter in
`score_matches`) cut a cold `route()` from 126-143 ms to 2.3 ms and compiled
0 patterns for `fix the flaky parser test in the payments module`. It returned
results identical to today's code on all 292 requests in
`scripts/routing-benchmark.json` plus 7 edge cases, including a non-ASCII
request.

## Current state

- `scripts/pre-route.py`: the deterministic force-route guardrail.
  - Lines 646-655, the match entry:

    ```python
    @dataclass
    class MatchEntry:
        """A single trigger-to-target mapping."""

        name: str
        entry_type: str  # "skill" or "agent"
        agent: str | None
        force_route: bool
        trigger: str
        pattern: re.Pattern[str]
    ```
  - Lines 759-797, `@functools.cache def _build_pattern(trigger_lower: str) -> re.Pattern[str]`.
    Single-word trigger: `rf"\b{re.escape(word)}\b"`. Multi-word: each word
    escaped, joined by `(?:[\s_-]+\S+){0,2}[\s_-]+`, interior edges use
    `(?<![^\W_])` / `(?![^\W_])`, and the last word takes
    `TRIGGER_INFLECTION = r"(?:s|es|d|ed|er|ers|ing)?"` (line 737). All
    patterns use `re.IGNORECASE`.
  - Lines 801-835, `build_match_table(entries)`: for each `force_route` entry
    and each string trigger, `trigger_lower = trigger.lower()`,
    `pattern = _build_pattern(trigger_lower)` (line 823), then
    `MatchEntry(..., trigger=trigger_lower, pattern=pattern)` (line 832). This
    is the only `MatchEntry(` call in the repo.
  - Lines 924-941, `score_matches(table, request)`:

    ```python
    request_lower = request.lower()
    candidates: dict[str, ScoredMatch] = {}

    for entry in table:
        if not entry.pattern.search(request_lower):
            continue

        # Semantic guard check
        if _is_semantically_guarded(entry.name, request_lower, entry.trigger, entry.pattern):
            continue
    ```
  - Lines 1007-1008, `route()` builds the table on every call:
    `table = build_match_table(entries)` then
    `candidates = score_matches(table, request)`.
- Tests read `.pattern` on table entries, so it must stay an attribute that
  returns a compiled pattern: `scripts/tests/test_pre_route.py:460`
  (`table[0].pattern.search("let's run go test now")`) and `:726-731`
  (`make_game.pattern` passed to `_is_semantically_guarded`).
  `scripts/tests/test_routing_keyword_fixes.py:65,78` call `_build_pattern`
  directly and `:136-143` call `build_match_table` then `score_matches`.
- Why the prefilter is exact: `_build_pattern` adds only boundaries,
  separators, intervening-word gaps, and a last-word suffix around each
  escaped trigger word. So every word of `trigger_lower` appears as a literal
  substring of any lowercased request the pattern matches. For ASCII text,
  `str.lower()` agrees with `re.IGNORECASE`. For non-ASCII text it does not:
  Python's `re.IGNORECASE` also matches U+0130, U+0131, U+017F, and U+212A to
  ASCII letters, and today `route("ſhip it")` force-routes to `pr-workflow`.
  The prefilter therefore runs only when `request_lower.isascii()`.
- Conventions: comments explain why, in plain sentences (see the comment
  block at `scripts/pre-route.py:66-81`). Tests use the `pre_route` and
  `real_entries` fixtures at `scripts/tests/test_pre_route.py:29-43`; every
  test in that file runs with the `use_public_index` fixture (line 19).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Build the untracked indexes (fresh worktree) | `python3 scripts/generate-skill-index.py && python3 scripts/generate-agent-index.py` | exit 0; writes gitignored `skills/INDEX.json`, `agents/INDEX.json` |
| Targeted tests | `python3 -m pytest scripts/tests/test_pre_route.py scripts/tests/test_routing_keyword_fixes.py -n 0 -q` | all pass |
| Routing benchmark (CI job) | `python3 scripts/routing-benchmark.py --verbose` | exit 0 |
| Lint | `ruff check . --config pyproject.toml` | exit 0 |
| Format | `ruff format --check . --config pyproject.toml` | exit 0 |
| Lint job | `bash scripts/ci-local.sh` | exit 0 |

Local ruff may be newer than the CI pin (0.15.12); `scripts/ci-local.sh` warns
about that. A format complaint about a file you did not touch is not yours.

## Scope

**In scope** (the only files to modify):
- `scripts/pre-route.py`
- `scripts/tests/test_pre_route.py`

**Out of scope** (do not touch, though they look related):
- `_build_pattern`'s regex construction: matching behavior must not change.
- `_is_semantically_guarded`, the guard tables, and `SUGGEST_ONLY_TRIGGERS`.
- `scripts/routing-benchmark.py` and `scripts/routing-benchmark.json`.
- `skills/**` frontmatter triggers.

## Git workflow

- Branch: `perf/pre-route-lazy-trigger-compile`.
- One commit. Message: one lowercase past-tense sentence, no type prefix, no
  trailing period, then a blank line and `Verified-By: tests`. Example from
  `git log`: `dropped the trivial intent skip so every /d route runs the intent check again, trivial ones included, at the owner's call`.
- Do not push, open a PR, merge, deploy, or tag.

## Steps

### Step 1: Record today's routing results

Build the indexes (table above), then save today's decisions for the whole
benchmark corpus plus edge cases:

```bash
python3 - <<'EOF' > /tmp/pre-route-before.json
import importlib, json, sys
sys.path.insert(0, "scripts")
pr = importlib.import_module("pre-route")
entries = pr.load_entries()
data = json.load(open("scripts/routing-benchmark.json"))
reqs = [c["request"] for c in data["test_cases"]]
reqs += ["fix the flaky parser test", "push my changes now", "PUSH my changes now", "ſhip it",
         "create a PR for this", "run the go tests", "security audit of foo.go", "pr-review this", "pr_review this"]
print(json.dumps({r: pr.route(r, entries=entries) for r in reqs}, sort_keys=True))
EOF
```

**Verify**: `python3 -c "import json; print(len(json.load(open('/tmp/pre-route-before.json'))))"` → a number of at least 290.

### Step 2: Write the failing tests

Add to `scripts/tests/test_pre_route.py`, in a new class
`TestLazyTriggerCompile`:

1. `test_request_naming_no_trigger_compiles_nothing(self, pre_route, real_entries)`:
   `pre_route._build_pattern.cache_clear()`, then
   `pre_route.route("zzqx blorp quux", entries=real_entries)`; assert
   `pre_route._build_pattern.cache_info().currsize == 0`.
2. `test_matching_request_compiles_only_its_candidates(self, pre_route, real_entries)`:
   `cache_clear()`, `result = pre_route.route("push my changes now", entries=real_entries)`;
   assert `result["skill"] == "pr-workflow"` and
   `0 < pre_route._build_pattern.cache_info().currsize < 50`.
3. `test_non_ascii_request_still_force_routes(self, pre_route, real_entries)`:
   `result = pre_route.route("ſhip it", entries=real_entries)`; assert
   `result["skill"] == "pr-workflow"` and `result["match_type"] == "force_route"`.
4. `test_prefilter_never_hides_a_regex_match(self, pre_route, real_entries)`:
   load the request strings from `scripts/routing-benchmark.json` (path from
   the repo root: `Path(__file__).resolve().parents[2] / "scripts" / "routing-benchmark.json"`;
   the cases are under the `test_cases` key, each with a `request` field).
   For each ASCII request, lowercase it; for each entry in
   `pre_route.build_match_table(real_entries)`, assert that
   `entry.pattern.search(req)` being truthy implies
   `all(w in req for w in entry.trigger.split())`. On failure, report the
   request and trigger.

**Verify**: `python3 -m pytest scripts/tests/test_pre_route.py -n 0 -q -k TestLazyTriggerCompile` → tests 1 and 2 fail (the table compiles every pattern); 3 and 4 pass.

### Step 3: Make `pattern` lazy and add the prefilter

In `scripts/pre-route.py`:

1. In `MatchEntry` (lines 646-655), remove the `pattern: re.Pattern[str]`
   field and add:

   ```python
       @property
       def pattern(self) -> re.Pattern[str]:
           """The trigger's regex, compiled on first use and cached by _build_pattern."""
           return _build_pattern(self.trigger)
   ```
2. In `build_match_table`, delete `pattern = _build_pattern(trigger_lower)`
   (line 823) and the `pattern=pattern,` argument (line 832). Change its
   docstring's first line to: `Collect force_route entries' triggers; each entry compiles its pattern on first use.`
3. In `score_matches`, before the loop, add:

   ```python
       # Every trigger word appears literally in any request its pattern matches (_build_pattern adds only
       # boundaries, gaps and a last-word inflection), so a missing word skips the compile. Non-ASCII text
       # skips this filter: re.IGNORECASE folds U+0130, U+0131, U+017F and U+212A onto ASCII letters,
       # which str.lower() does not.
       prefilter = request_lower.isascii()
   ```

   and make the first statement in the loop:

   ```python
           if prefilter and not all(word in request_lower for word in entry.trigger.split()):
               continue
   ```
4. In `_build_pattern`'s docstring, after the sentence that ends "recompiled
   every trigger regex.", add: `score_matches compiles only triggers whose words all appear in an ASCII request.`

**Verify**: `python3 -m pytest scripts/tests/test_pre_route.py scripts/tests/test_routing_keyword_fixes.py -n 0 -q` → all pass, including the 4 new tests.

### Step 4: Prove the decisions did not change

Rerun the step 1 script with the output going to `/tmp/pre-route-after.json`.

**Verify**: `cmp /tmp/pre-route-before.json /tmp/pre-route-after.json && echo SAME` → prints `SAME`.

### Step 5: Measure and run the gates

**Verify**:
- `printf 'fix the flaky parser test in the payments module' > /tmp/req.txt; for i in 1 2 3 4 5; do /usr/bin/time -f %e python3 scripts/pre-route.py --request-file /tmp/req.txt --json-compact > /dev/null; done` → every time under 0.10 s (it was about 0.21 s).
- `python3 scripts/routing-benchmark.py --verbose` → exit 0.
- `bash scripts/ci-local.sh` → exit 0.
- `rm -f /tmp/pre-route-before.json /tmp/pre-route-after.json /tmp/req.txt` → exit 0.

## Test plan

- New class `TestLazyTriggerCompile` in `scripts/tests/test_pre_route.py`
  with 4 tests: no compile for an unrelated request, a bounded compile for a
  matching request, the non-ASCII force route, and the prefilter soundness
  check over the benchmark corpus.
- Model after `TestScoreMatches` in the same file (fixtures `pre_route`,
  `real_entries`).
- Verification: `python3 -m pytest scripts/tests/test_pre_route.py scripts/tests/test_routing_keyword_fixes.py -n 0 -q` → all pass, including 4 new tests.

## Done criteria

- [ ] `python3 -m pytest scripts/tests/test_pre_route.py scripts/tests/test_routing_keyword_fixes.py -n 0 -q` exits 0
- [ ] Step 4 printed `SAME`
- [ ] `grep -n "pattern = _build_pattern" scripts/pre-route.py` returns no matches
- [ ] `python3 scripts/routing-benchmark.py --verbose` exits 0
- [ ] `bash scripts/ci-local.sh` exits 0
- [ ] `git status --short` shows no file outside the in-scope list
- [ ] `plans/README.md` row for 011 updated

## STOP conditions

Stop and report if:

- The code at the "Current state" locations does not match the excerpts.
- A step's verification fails twice after a reasonable fix attempt.
- The fix needs a file outside the in-scope list.
- Step 4 shows any difference, or test 4 of step 2 fails: the assumption
  "every trigger word appears literally in a matching ASCII request" is false
  for some trigger. Report the trigger; do not widen or drop the prefilter.
- `MatchEntry(` is constructed with `pattern=` anywhere besides
  `build_match_table` (`grep -rn "MatchEntry(" --include=*.py .`).

## Maintenance notes

- If `_build_pattern` ever adds alternatives for a trigger word (synonyms,
  stemming, a fuzzy match), the prefilter becomes unsound. Test 4 of step 2
  is the guard: keep it.
- The remaining CLI cost is interpreter start, index load, and private-entry
  gating, about 30 ms plus host overhead.
- Reviewer: check the non-ASCII branch keeps today's behavior and that no
  caller relied on `pattern` being a dataclass field (`dataclasses.fields`,
  `asdict`, or `replace` on `MatchEntry`).
