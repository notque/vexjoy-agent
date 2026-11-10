# Contributing

Use this guide to add components, check your changes, and open a PR.

## Standards

Keep contributions specific, testable, and concise.

| Criterion | Pass | Fail |
|-----------|------|------|
| **Specific** | Actionable steps, exit criteria | Vague advice ("be careful") |
| **Verifiable** | Evidence requirements | Trusts LLM confidence |
| **Battle-tested** | Real workflows, relevant checks | Hypothetical "should work" |
| **Minimal** | What guides the agent, nothing else | Verbose human explanations |
| **Dense** | Every word carries instruction | Prose where a table works |

## Component Types

| Component | Location | Format | Purpose |
|-----------|----------|--------|---------|
| Agent | `agents/{name}.md` | YAML frontmatter + markdown | Domain expertise |
| Skill | `skills/{category}/{name}/SKILL.md` | YAML frontmatter + phased instructions | Workflow methodology |
| Hook | `hooks/{name}.py` | Python, JSON in/out | Event-driven automation |
| Script | `scripts/{name}.py` | Python CLI | Deterministic operations |

Put domain knowledge in agents, procedures in skills, event responses in hooks, and repeatable operations in scripts.

## Adding Components

The toolkit has creator agents. Tell `/do` what you want.

**Agent:**
```
/do create an agent for [domain]
```

**Skill:**
```
/do create a skill for [workflow]
```

**Hook:**
```
/do create a hook for [purpose]
```

The creator handles file structure, frontmatter, index registration, and routing integration. Test routing after creation:

```
/do [request that should trigger your new component]
```

## PR Workflow

The full cycle, in order:

1. **Branch** from main (`feature/`, `fix/`, `refactor/`)
2. **Implement** changes
3. **Review** using the risk-selected lane in `pr-workflow`
4. **Fix** confirmed findings and rerun affected checks
5. **Edit** the agent or skill file yourself when a finding should change behavior
6. **Commit** (one lowercase past-tense sentence; see Conventions)
7. **Push** to remote
8. **PR** via `gh pr create`
9. **CI** passes
10. **Merge**

The `pr-workflow` skill automates steps 3 through 9.

## Quality Gates

Before submitting:

- `ruff check . --config pyproject.toml` passes
- `ruff format --check . --config pyproject.toml` passes
- `python3 scripts/validate-references.py --agent <name>` passes for each agent whose references you added; CI also runs it with `--check-do-framing`, `--check-placeholders`, `--check-size`, and `--check-skill-calls`
- New components appear in INDEX after running generators
- No secrets in committed files

## Testing

pytest, with pytest-xdist for parallel runs. Tests live in `hooks/tests/`, `scripts/tests/`, `tests/`, and `skills/**/tests/`.

```bash
pip install pytest pytest-xdist               # or: pip install -e ".[dev]"
pytest                                        # fast tier, parallel (what PR CI runs)
pytest -m "not performance"                   # full tier minus timing budgets
pytest -m performance -n 0                    # timing budgets; run serially
pytest hooks/tests/test_foo.py -n 0 -v        # one file, serial (skips worker startup)
```

`pyproject.toml` sets an xdist worker count (`-n`) and `--dist loadfile` by default, so pytest-xdist must be installed. `--dist loadfile` keeps each file on one worker.

The default marker filter in `pyproject.toml` skips `slow and integration` (install end-to-end, live Chromium) and `performance` (wall-clock budgets). CI runs the fast tier on every PR and the full tier on push to main and nightly. Mark a new test `performance` if it asserts a timing budget, and `slow` plus `integration` if it drives a real external tool.

Tests must be safe to run in parallel: write under `tmp_path`, change env and cwd with `monkeypatch`, and give any hook-created `/tmp` state a unique session id. The root `conftest.py` strips live session ids and API keys so tests stay offline and never touch a running session's state.

Doc-structure checks (reference sizes, Skill-call wording, joy-check fleet scan, `$SDIR` portability) are validators in `scripts/`, run by the CI lint job, not per-file pytest cases.

Run the whole CI lint job locally before you push:

```bash
bash scripts/ci-local.sh            # every lint-job step, in CI order
bash scripts/ci-local.sh --tests    # the same, then the fast pytest tier
```

The script stops at the first failing step. It regenerates the untracked `INDEX.json` files and `docs/routing-map.md`, exactly as CI does. CI pins ruff; the script warns when your local ruff is another version.

Hooks: feed JSON, assert JSON output. Scripts: deterministic input/output verification. Agents and skills use the validators and review methodology in `skills/meta/toolkit/`.

## Conventions

**Commit messages.** One lowercase past-tense sentence saying what changed and why, with no type prefix and no trailing period: `moved the hook timeouts to seconds so a stuck hook stops holding the session`. The full rule is in [AGENTS.md](AGENTS.md) (Writing style).

**Attribution.** No "Generated with Claude Code" or `Co-Authored-By` lines; the repo's `.claude/settings.json` sets `attribution` to empty strings. Trailer lines such as `Claude-Session: <url>` are allowed after a blank line.

**Branch safety.** Create feature branches for all work. The pretool hook enforces this.

**INDEX.json is generated.** Run `scripts/generate-agent-index.py` and `scripts/generate-skill-index.py`. Do not hand-edit.

**Scripts are deterministic.** LLM judgment goes in agents and skills, not scripts.

**50ms hook budget.** Hooks fire on every tool call. Keep them fast. `scripts/benchmark-hooks.py` validates this.

**Wabi-sabi in docs.** Write like a human. Contractions fine. Fragments fine. Banned words include "delve", "robust", "streamline", and "empower"; the full list is `scripts/data/banned-patterns.json`, and `scripts/scan-ai-patterns.py` catches violations.

**ADRs are local-only.** `adr/` is gitignored, so an ADR named in code or docs (`ADR-103`, an `adr/` path) is not in a clone. Cite it by name as local-only; never link to it.
