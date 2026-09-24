# Uplift for weaker models

Improve a skill, agent, or shared guide until a weaker model (for example Opus 4.6) produces strong output with it. The loop: give the weaker model the guidance and a task, look hard at what it makes, turn every failure into a concrete rule, and run it again. Measure each round against a no-guidance baseline.

Use this when a skill works for a strong model but weaker models "don't know what to do": vague principles, missing values, stale instructions, or rules only an expert can apply. Write for the weakest reader: more explicit than a strong model needs. Extra tokens for a strong reader are an accepted cost.

## Results this method produced

| Target | Measure | No guidance | Old guidance | After uplift |
|---|---|---|---|---|
| Go agent and references (PR #1009) | code-quality rubric, 7 tasks | 57% | 62% | 98% (all acceptance tests passed in every arm) |
| `/d` skill attachment | right agent + all required skills, 57 requests | — | 55.8% dev, 42.9% held-out | 93.0% dev, 92.9% held-out (`/do`: 83.7%, 100%) |
| Shared UI design guides | Jev template-tells score (0 none – 3 pervasive), landing page | 2.0 | — | 0.7; sideways scroll, hidden sections, missing dark mode fixed |
| Python agent and references | 15-item rubric (acceptance, own tests, strict ruff, ruff format, `mypy --strict`, build backend, typing, docstrings, task checks), 6 tasks + 1 held-out | 58% dev, 63% held-out | 73% dev, 77% held-out | 88% dev, 80% held-out; 91% and 90% with one narrated line stripped (see Python rows below). Acceptance 98% → 100%, `mypy --strict` clean 7/14 → 13/14, builds 2/14 → 14/14 |

## Steps

### 1. Pick the target from data

Pick skills people use and skills that fail. Query the usage and routing databases (read-only):

```bash
sqlite3 -column ~/.claude/learning/usage.db \
  "select skill_name, count(*) n from skill_invocations
   where timestamp >= date('now','-60 day') group by 1 order by 2 desc limit 20;"
sqlite3 -column ~/.claude/learning/learning.db \
  "select phase, alignment, count(*), sum(route_mismatch) from jev_intent_alignments group by 1,2;"
```

Slash-command skills (`/d`, `/do`) don't appear in `skill_invocations`; use their routing tables instead. Report counts and patterns, never raw request text.

### 2. Build the task set and its checks first

- 4–8 realistic tasks that cover the skill's range, plus 1–2 **held-out** tasks the guidance never mentions. Held-out tasks show whether the guidance generalizes; report them separately.
- Write the checks before any run. Prefer deterministic checks (build, tests, race detector, linters, page checks, exact-match labels). Add a rubric of yes/no design checks (13–17 per task worked for Go). Numbers come from code, not judgment.
- For routing skills, label each request with the expected agent and skills from the real catalog (`agents/INDEX.json`, `skills/INDEX.json`), and score agent accuracy, skill recall, skill precision, and "full" (everything right).

### 3. Run the arms

Run every task in at least two arms: **no guidance** and **current guidance**. Two samples per task per arm is the minimum; say so when that is all you ran.

```bash
python3 scripts/weak_model_run.py --task tasks/pool.txt --out runs/r0/base-pool --format files
python3 scripts/weak_model_run.py --task tasks/pool.txt --out runs/r0/guided-pool --format files \
  --guidance agents/golang-general-engineer/references/go-modern-code.md
```

- The runner calls `claude -p --model claude-opus-4-6 --tools "" --output-format stream-json` and removes `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING`, which forces older models onto a deprecated thinking mode. It keeps every assistant text block (the `result` field holds only the last one, so a closing summary used to replace all the files), moves prose after the last file into `<out>.commentary`, writes `<out>.cost.json`, and exits 1 when a files-format reply has no files (rate-limit and session-limit replies).
- Run it from a directory outside the repo (the session scratchpad): `claude -p` loads the `CLAUDE.md` files above its working directory, which would leak guidance into the no-guidance arm.
- `--format html` keeps one HTML document; `--format files` splits `=== FILE: path ===` blocks into a directory (unsafe paths are refused).
- Run 2–6 generations at once. More trips rate limits; the session limit can end a run mid-round, so keep outputs on disk and resume only what's missing.
- Log the cost of each round: sum the `.cost.json` files (the Go loop was 56 calls, about $42; the `/d` loop about $20; the Python loop 70 calls, $39).

### 4. Score and look

1. Run the deterministic checks and the rubric on every output.
2. **Look at the artifacts yourself**: read the code, render the pages. For UI, take full-page screenshots at 375 and 1280 px, light and dark, **after scrolling to the bottom** (scroll-reveal content is blank otherwise), and run the page-check script in `skills/shared-patterns/ui-design-judgment.md` section 10.
3. Optionally ask Jev bounded questions about compact extracted facts (headings, button labels, CSS facts, error counts), never whole files. Keep requests under 3,500 tokens (`jev_transport.evaluate_packed`).
4. Check your harness before blaming the model. Tall screenshot windows break `100vh` heroes; screenshots taken before scrolling show blank sections. Run the acceptance tests against a reference solution before any model run, and make lint rules the task's own contract forces (for example a required `timeout` parameter) non-scoring. Fix the harness, then judge.

### 5. Turn failures into rules

For each failure seen in more than one output, or any serious one:

- Write a **concrete rule** with exact values, component names, or commands. "Wrap tables in `overflow-x: auto`" beats "make it responsive".
- Add a **before/after example** in the target's own language (code snippet, CSS, copy).
- Add a **check** the model can run before handing off (a command, a script, a yes/no question).
- **Delete stale or wrong instructions.** Weaker models follow them literally: `/d` told models to add four skills that no longer existed, and the Go guide cited a command that doesn't exist.
- Examples must use **different products and data than the tasks**. In the UI loop the model copied an example headline word for word into a real brief.
- Rules must not invent requirements: add "build everything the brief asks for and nothing it doesn't" when models add features, roles, or claims.
- Keep rules as defaults with reasons. Rigid bans (fonts, color ratios, animation counts) produce their own template look.

### 6. Rerun and stop

- Rerun the guided arm with the new guidance, and the held-out tasks. Keep the baseline from round 0.
- Stop when two rounds in a row gain little, or after three rounds. Report what you would try next.

### 7. Report and ship

Report a table per round: arm, runs, each metric, held-out separately, and cost. List the top failure patterns and the rule that now covers each. State caveats plainly: sample size, heuristic rubric, held-out tasks you saw while fixing (they are no longer clean), runs lost to rate limits.

Ship through the normal PR flow with the results in the PR body. Keep the harness, tasks, raw outputs, and scores in the session scratchpad or an `evals/` folder, not in the skill.

## Failure patterns seen so far

| Domain | Pattern | Rule that fixed it |
|---|---|---|
| All | Weak model follows stale instructions literally | Remove dead skill names, commands, and version claims; validate references |
| All | Copies example wording into real output | Examples use unrelated products and data; say "never reuse example words" |
| All | Invents features, roles, claims | "Everything the brief names, nothing it doesn't; mark placeholders" |
| UI | Page scrolls sideways at 375 px; nav vanishes on phones | `overflow-x: auto` wrappers, `min-width: 0`, a header menu button, a page-check script |
| UI | Sections hidden until scroll | Content visible by default; animation class added by JavaScript only |
| UI | No dark mode in standalone HTML | `@media (prefers-color-scheme: dark)` tokens by default |
| UI | Emoji and icon fonts render as empty boxes | Inline SVG icons |
| Go | Missing doc comments, old idioms (`wg.Add`, `errors.As`, `sort.Slice`, `context.Background()` in tests) | Version-gated idiom table with before/after code, `go fix -diff` in the checklist |
| Go | `defer` before `os.Exit`; `Shutdown` without `Close` | Verified `main`/`run` and serve/shutdown snippets |
| Routing | One skill attached, domain skill missing | One yes/no question per domain skill; code builds the attach list |
| Routing | Keyword shortcuts override the model | Only git/PR and security shortcuts may override |
| All | A run-these-commands checklist makes a tool-less model narrate ("now let me run the checks") inside the last file, a syntax error in 19 of 28 runs | State the reply format first ("every line in a file block is code"), put commands under "with a shell", never quote the bad phrase in the rule (the round that quoted it went from 8 to 11 files): 19 of 28 → 3 of 14 |
| Python | Invented build backends (`setuptools.backends._legacy:_Backend`, `hatchling.backends`): `pip install .` fails | Two exact backends to copy, plus `pip wheel --no-deps` in the checklist: 2/14 → 14/14 build |
| Python | `typing.List`/`Optional`, bare generics, `Any` returned from `json.loads`, no docstrings | Write/never-write table, `isinstance` narrowing example, docstring rule: `mypy --strict` clean 7/14 → 13/14, docstrings 0/14 → 12/12 dev |
| Python | `Decimal("NaN")` accepted as money | `is_finite()` after parsing: 4/4 failed → 0 |
| Python | `gather` + hand-written cancel loops, `wait_for` | `TaskGroup` + `asyncio.timeout` + `Semaphore` snippet; `CancelledError` rules |
| Python | Tests held to a lower bar: unused imports, imports inside test functions, `pytest.raises(Exception)` | "Tests meet the same bar", write the import block last from used names, exact type plus `match=` |
| Python | Hand-wrapped lines at 88 columns under a 120 config fail `ruff format --check` | Fits-on-one-line rule with a trailing-comma example; still failing in 6 of 14, the top open issue |
