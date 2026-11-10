# Plan 004: One command runs the CI lint job locally

> **Executor instructions**: follow this plan step by step. Run every
> verification command and confirm the expected result before the next step.
> If a STOP condition occurs, stop and report. Do not improvise. Do not run
> any step marked OWNER-GATED. When done, update this plan's row in
> `plans/README.md`, unless a reviewer dispatched you and maintains the index.
>
> **Drift check (run first)**: `git diff --stat c0f87bbf..HEAD -- scripts/ci-local.sh tests/test_ci_local_script.py CONTRIBUTING.md .github/workflows/test.yml`
> If an in-scope file changed, compare the "Current state" excerpts with the
> live code. A mismatch is a STOP condition. `test.yml` is read-only input
> here; if its `lint` job changed, rebuild the step list in step 1 from the
> live file and continue.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: dx
- **Kind**: fix
- **Planned at**: commit `c0f87bbf`, 2026-11-09

## Why this matters

The CI `lint` job runs 27 steps: index generation, ruff twice, and about 23
validators and generator checks. No Makefile or script runs them locally, and
`AGENTS.md` asks only for the two ruff commands before a push. A contributor
or agent therefore learns about a failing validator from CI, one push at a
time. After this plan,
`bash scripts/ci-local.sh` runs the same commands in the same order, and a
test fails when the script and the workflow diverge.

## Current state

`.github/workflows/test.yml:14-88` is the `lint` job. Its `run:` steps, in
order, at the planned commit:

```text
24  pip install ruff==0.15.12 pyyaml                      (setup; not mirrored)
26  python scripts/generate-skill-index.py && python scripts/generate-agent-index.py
28  python scripts/add-companion-skills.py --check
29  ruff check . --config pyproject.toml
30  ruff format --check . --config pyproject.toml
31  python scripts/validate-references.py --check-do-framing
33  python scripts/validate-references.py --check-placeholders
36  python scripts/validate-references.py --check-size
37  python scripts/validate-references.py --check-skill-calls
38  python scripts/validate_positive_instruction_docs.py --fleet
39  python scripts/validate-doc-commands.py --check-sdir
40  python scripts/validate-skill-frontmatter.py
41  python scripts/validate-index-integrity.py
45  python scripts/validate-promoted-successors.py
49  python scripts/validate-pipeline-index.py
52  python scripts/generate-routing-map.py --check
53  python scripts/generate-skills-doc.py --check
56  python scripts/validate-skill-names.py
61-65  (named, multi-line) fail when `git ls-files` lists an INDEX.local.json
67  (named) python scripts/generate-routing-map.py && git diff --exit-code -- docs/routing-map.md
71  python scripts/validate-negative-controls.py
75  python scripts/validate-merged-index.py
77  python scripts/validate-do-references.py
78  python scripts/validate-doc-links.py
79  python scripts/validate-doc-commands.py
80  python scripts/validate-doc-commands.py --scope toolkit
83  python scripts/validate_component_models.py
88  python scripts/validate-workflow-conformance.py
```

The multi-line step, `test.yml:61-65`:

```yaml
      - name: No tracked INDEX.local.json
        run: |
          if git ls-files | grep -E '(^|/)INDEX\.local\.json$'; then
            echo "tracked INDEX.local.json found (private-inclusive index must stay local)"; exit 1
          fi
```

Facts that shape the script:

- Line 67 rewrites the tracked file `docs/routing-map.md` and then diffs it.
  With uncommitted edits to that file the step fails for a reason unrelated
  to CI. The script must detect that case and say so.
- CI pins `ruff==0.15.12` because 0.16.0 reformats markdown code blocks
  (`test.yml:21-23`). A local `ruff` at another version can disagree with CI.
- `scripts/validate-doc-counts.py` (line 79) counts top-level `scripts/*.py`
  files and compares the count with `README.md`. A `.sh` file does not change
  it. Do not add a `.py` file under `scripts/`.
- CI calls `python`. Local machines may have only `python3`.

Conventions:

- Shell scripts: `#!/usr/bin/env bash`, a header comment that states purpose
  and usage, then `set -euo pipefail`. Exemplar: `scripts/worktree-preflight.sh`.
  Match it. Mode `755`.
- Repo-config contract tests live in `tests/`. Exemplar:
  `tests/test_pytest_config.py`.
- `CONTRIBUTING.md` documents test commands in the `## Testing` section
  (lines 86-104) as a fenced `bash` block followed by short paragraphs.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Syntax | `bash -n scripts/ci-local.sh` | exit 0, no output |
| New test | `python3 -m pytest tests/test_ci_local_script.py -n 0 -q` | all pass |
| Run it | `nice -n 10 bash scripts/ci-local.sh` | last line `ci-local: all N steps passed`, exit 0 |
| Lint | `ruff check . --config pyproject.toml` | `All checks passed!` |
| Format | `ruff format --check . --config pyproject.toml` | exit 0 |
| Doc gates | `python3 scripts/validate-doc-commands.py && python3 scripts/validate-doc-links.py && python3 scripts/validate-doc-counts.py` | exit 0 |

## Scope

**In scope** (the only files to modify):
- `scripts/ci-local.sh` (create)
- `tests/test_ci_local_script.py` (create)
- `CONTRIBUTING.md`: the `## Testing` section only

**Out of scope** (do not touch):
- `.github/workflows/test.yml`: read it; never edit it.
- `README.md`: it carries the script count and has unrelated uncommitted
  edits in the owner's tree.
- `AGENTS.md` and `CLAUDE.md`: instruction files; the owner edits those.
- Git hooks, `pre-commit` config, a Makefile: no install step, no
  persistence.
- The other CI jobs (`routing-benchmark`, `hook-health`, `mutation-check`,
  and the rest).

## Git workflow

- Branch: `feature/advisor-004-local-ci-script`.
- One commit. Message style: one lowercase past-tense sentence, no type
  prefix, no trailing period. Example from `CONTRIBUTING.md`:
  `moved the hook timeouts to seconds so a stuck hook stops holding the session`.
- No `Co-Authored-By` or "Generated with" lines.
- Do not push, open a PR, merge, deploy, or tag.

## Steps

### Step 1: Write the drift test first

Create `tests/test_ci_local_script.py`. It reads two files; it runs nothing.

1. Load `.github/workflows/test.yml` with `yaml.safe_load` and take
   `jobs["lint"]["steps"]`.
2. Build `expected`: the `run` string of every step that has one, skipping
   any that starts with `pip install`, and skipping multi-line strings
   (those containing `\n` after `.strip()`).
3. Read `scripts/ci-local.sh` as text. Build `script_cmds`: each `expected`
   command in the form the script uses, `re.sub(r"\bpython ", '"$PY" ', cmd)`.
   Commands without `python ` (the two ruff lines) stay unchanged.
4. `test_every_lint_step_is_mirrored`: each mirrored command appears in the
   script text. The failure message names the missing CI command and says
   "add it to scripts/ci-local.sh in workflow order".
5. `test_steps_keep_workflow_order`: the positions of the mirrored commands
   in the script text increase.
6. `test_index_local_guard_is_mirrored`: the script text contains
   `INDEX\.local\.json`.
7. `test_lint_job_was_parsed`: `len(expected) >= 20`, so a renamed job
   cannot pass vacuously.
8. `test_script_is_executable_bash`: first line is `#!/usr/bin/env bash`,
   the text contains `set -euo pipefail`, and `os.access(path, os.X_OK)`.

**Verify**: `python3 -m pytest tests/test_ci_local_script.py -n 0 -q` → fails
(the script does not exist yet).

### Step 2: Write `scripts/ci-local.sh`

Shape:

```bash
#!/usr/bin/env bash
# ci-local.sh - run the CI lint job (.github/workflows/test.yml, job "lint")
# locally, in workflow order.
#
# Usage:
#   bash scripts/ci-local.sh            # lint job only
#   bash scripts/ci-local.sh --tests    # lint job, then the fast pytest tier
#
# Exit: 0 when every step passes, 1 on the first failure.
# tests/test_ci_local_script.py fails when this list and the workflow differ.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
PY="${PYTHON:-$(command -v python || command -v python3)}"
```

Required behavior:

1. A `step` function prints `==> <command>`, runs it, counts it, and on
   failure prints `ci-local: FAILED at step <n>: <command>` to stderr and
   exits 1.
2. Before the first step, compare `ruff --version` with the version pinned in
   `test.yml` (read it with `grep -o 'ruff==[0-9.]*'`). On a mismatch print
   one `warning:` line to stderr and continue. Do not install anything.
3. Before the first step, if `git status --porcelain -- docs/routing-map.md`
   prints anything, print
   `warning: docs/routing-map.md has uncommitted changes; the regenerate step will report them`
   to stderr and continue.
4. Run every command from the "Current state" list except line 24, in that
   order, each written with `"$PY"` in place of `python` and otherwise
   character-for-character the same, so the drift test can find it.
5. The line 61-65 guard runs as its own step with the same `grep -E` pattern
   and message.
6. With `--tests`, after the lint steps run
   `nice -n 10 "$PY" -m pytest --tb=short -q` (the pyproject default: fast
   tier, 4 workers).
7. Last line on success: `ci-local: all <n> steps passed`.
8. Any other argument: print the usage lines and exit 2.

Set the mode: `chmod 755 scripts/ci-local.sh`.

**Verify**:
- `bash -n scripts/ci-local.sh` → exit 0
- `python3 -m pytest tests/test_ci_local_script.py -n 0 -q` → 5 passed

### Step 3: Run the script

Run `nice -n 10 bash scripts/ci-local.sh` in your worktree. `docs/` must have
no uncommitted change when you run it.

**Verify**: exit 0 and a last line `ci-local: all 27 steps passed` (27 at the
planned commit: 26 single-line steps plus the INDEX.local.json guard). Then
`git status --short` shows no file you did not create or edit.

If a step fails, run that one command by hand. If it fails for a reason
unrelated to your three files, it is a pre-existing failure: STOP and report
the command and its output. Do not fix it here.

### Step 4: Document it

In `CONTRIBUTING.md`, `## Testing` section, add after the paragraph that
begins "Doc-structure checks":

````markdown
Run the whole CI lint job locally before you push:

```bash
bash scripts/ci-local.sh            # every lint-job step, in CI order
bash scripts/ci-local.sh --tests    # the same, then the fast pytest tier
```

The script stops at the first failing step. It regenerates the untracked
`INDEX.json` files and `docs/routing-map.md`, exactly as CI does. CI pins
ruff; the script warns when your local ruff is another version.
````

**Verify**: the Doc gates and Lint and Format commands from the table → all
succeed. `grep -c "ci-local.sh" CONTRIBUTING.md` → `2`.

## Test plan

- New: `tests/test_ci_local_script.py`, 5 tests (step 1). They cover the
  regression this plan prevents: a lint step added to CI and not to the
  script.
- Manual proof of the drift test, then undo: delete one `step` line from the
  script, run the test, confirm `test_every_lint_step_is_mirrored` fails and
  names that command, then restore the line with `git checkout -- scripts/ci-local.sh`
  (only after the file is committed or staged; otherwise re-add the line by hand).
- Structure model: `tests/test_pytest_config.py`.

## Done criteria

- [ ] `python3 -m pytest tests/test_ci_local_script.py -n 0 -q` exits 0, 5 passed
- [ ] `nice -n 10 bash scripts/ci-local.sh` exits 0 and ends with `ci-local: all 27 steps passed`
- [ ] `bash scripts/ci-local.sh --bogus; echo $?` prints usage and `2`
- [ ] `test -x scripts/ci-local.sh && echo ok` prints `ok`
- [ ] `python3 scripts/validate-doc-counts.py` exits 0 (script count unchanged)
- [ ] `ruff check . --config pyproject.toml` and `ruff format --check . --config pyproject.toml` exit 0
- [ ] `git status --short` shows only the three in-scope files (plus `plans/README.md` if you maintain the index)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report if:

- The `lint` job's steps differ from the "Current state" list in a way the
  drift-check note does not cover (for example, the job was renamed or split).
- A step's verification fails twice after a reasonable fix attempt.
- The fix needs a file outside the in-scope list.
- A CI lint command fails on the unmodified base commit (step 3). The script
  is correct; the repo has a pre-existing failure the owner must see.
- Running the script changes a tracked file other than the ones you edited.
  The assumption "the lint job only writes untracked indexes and an
  unchanged `docs/routing-map.md`" is then false.
- `validate-doc-commands.py` rejects the new `CONTRIBUTING.md` block.
- A step would need `pip install`, a git hook, a deploy, a credential, a
  scheduled job, or a request to a third party.

## Maintenance notes

- Run the script and the test suite at `nice` 10 or higher and outside
  01:00-04:00 local time on this host.
- When a step is added to the CI `lint` job, add it to the script; the drift
  test fails until then. Multi-line `run:` steps are not checked by the test
  and need a hand-written mirror and a dedicated assertion.
- Deferred: mirroring the other CI jobs (`hook-health`, `mutation-check`,
  `routing-benchmark`). They are slower and some are advisory.
- Deferred, owner decision: point the "CI" bullet in `AGENTS.md` at this
  script. That file is an instruction file, so the owner edits it.
- A reviewer should check that the script installs nothing and writes no
  tracked file beyond what CI's own steps write.
