---
summary: "Five-minute path from install to first /do."
read_when:
  - "onboarding a new user"
---

# Start Here

Install the toolkit, then describe your task with `/do`. The router selects the relevant agent, skill, and checks.

## What You Need

- Linux or macOS. On Windows, use Git for Windows: the installer runs under its bash, and the hooks run under its `sh`.
- Python 3.10 or later. `install.sh` stops when it finds no 3.10+ interpreter; set `VEXJOY_PYTHON=/path/to/python3` to choose one.
- git and bash.
- pip with network access. The installer installs `requirements.txt`.
- npm, optionally. It installs Jev's Vercel gateway; without it, `/d` falls back to `/do`.
- [Claude Code](https://docs.claude.com/en/docs/claude-code). Confirm it works:

```bash
claude --version
```

Codex CLI, Factory, Reasonix, and Antigravity CLI are optional. The installer mirrors the components each runtime supports. Use `/do` in Claude Code, Factory, Reasonix, and Antigravity CLI; use `$do` in Codex.

If you plan to use an optional runtime, check that its CLI runs before installation (for example, `codex --version`). Claude Code has the broadest hook coverage; the other runtimes receive only the components and lifecycle events they support.

## Install

The install reaches past `~/.claude/`, and some of its hooks block commits and pushes in every repo. Skim [What the Installer Changes](#what-the-installer-changes) and [Gates in Every Repo](#gates-in-every-repo) before you run it, or run `./install.sh --dry-run` to print the plan without writing anything.

```bash
git clone https://github.com/notque/vexjoy-agent.git ~/vexjoy-agent
cd ~/vexjoy-agent
./install.sh
```

Several files assume the checkout lives at `~/vexjoy-agent`, so clone it there. In a main checkout the installer links each entry into `~/.claude/`, so `git pull` updates appear immediately. Pass `--copy` for a stable snapshot instead (`--symlink` selects the default explicitly). The installer puts the toolkit in `~/.claude/` and creates the supported mirrors for other installed runtimes.

Verify the result:

```bash
python3 ~/.claude/scripts/install-doctor.py check
python3 ~/.claude/scripts/install-doctor.py inventory
```

`check` validates the installation, settings, hook paths, and local data access. `inventory` shows what each runtime can see. Rerun `./install.sh` after pulling changes if you chose copies.

### Codex users

Codex integration requires v0.144.1 or later. Codex runs 62 of the 76 hook registrations; 14 are unsupported. A registration is one hook file on one event. Some run on native Codex events and the rest through `hooks/codex-hook-adapter.py`, so this is not full Claude Code parity.

After installation or a hook update, run `/hooks` in Codex and approve changed definitions. Codex does not run changed hook commands until they are trusted.

## Try It

Open a project directory and start Claude Code:

```bash
claude
```

Then ask for an overview or give it a concrete task:

```text
/do what can you do?
/do give me an overview of this codebase
/do debug why this test fails
/do write a blog post about [topic]
```

You do not need to choose an agent or skill. State the outcome you want; `/do` handles routing and applies the relevant workflow and verification.

If a check reports missing or stale mirrors, rerun `./install.sh`, then repeat the two verification commands. The inventory output is the authoritative view of what the installed runtimes can currently discover.

## What Was Installed

- **Agents** provide domain knowledge.
- **Skills** define reusable methods such as debugging, review, research, and writing.
- **Hooks** run checks at configured lifecycle events.
- **Commands** provide entry points such as `/do`.
- **Scripts** perform deterministic operations.

These components load when you start Claude Code in any directory. See the root README for architecture, runtime differences, and implementation details.

## What the Installer Changes

`./install.sh` writes all of the following. `./install.sh --dry-run` writes nothing, but it prints only the engine's plan (the `~/.claude/` and runtime-home rows); it does not list the git hook, pip, npm, `~/.bashrc`, or permission steps.

| Where | What changes | Opt out |
|---|---|---|
| This checkout's `.git/hooks/` | Writes `post-merge`, which runs `vexinstall sync --target all` after every `git pull`, and `pre-commit`, which blocks a commit carrying private overlay names (`scripts/check-private-leak.py`). An existing hook the installer did not write is left alone, and worktrees are skipped. | `VEXJOY_NO_GIT_HOOKS=1` |
| `~/.claude/` agents, skills, commands, hooks, scripts | Links each entry to this checkout, or copies it with `--copy` (the default for worktrees and `/tmp` checkouts). Entries the installer does not own, at the paths it needs, move to `~/.claude/vexjoy/trash/`, as do dangling links and legacy toolkit entries. Trash older than 14 days is deleted on the next install or sync. | `--copy`, `--no-takeover`, `.local/profile.yaml` |
| `~/.claude/settings.json` | Merges the toolkit's hook registrations (your own entries stay) and adds the `env` variables you have not set ([Recommended Settings](REFERENCE.md#recommended-settings)). Backs the old file up to `~/.claude/vexjoy/backups/` first. | `.local/profile.yaml` (per hook) |
| Other runtime homes | Mirrors what each runtime supports into `~/.codex`, `~/.factory`, `~/.hermes`, `~/.reasonix`, `~/.gemini`, and `~/.cline` when that home exists, and first creates the home of each runtime whose command is on PATH (not Cline's). Writes `~/.codex/hooks.json` and turns hooks on in `~/.codex/config.toml`. Replaces the `hooks` key of `~/.factory/settings.json` and `~/.reasonix/settings.json`, and the toolkit's events in `~/.gemini/config/hooks.json`. Each file is backed up first. | `--target <t>` |
| Account profiles | When `~/.claude-accounts/accounts.json` exists (`scripts/manage-accounts.py`), links each profile's `skills`, `agents`, `commands`, `hooks`, and `scripts` to `~/.claude` when the profile has none of its own, and merges the toolkit's hooks into its `settings.json`. | None |
| Python packages | Installs `requirements.txt` with pip for the installer's Python and for the hook Python, using `--break-system-packages` when pip supports it and `--user` as the fallback. | `VEXJOY_NO_DEPS=1` |
| npm packages | Runs `npm ci --ignore-scripts` in `scripts/jev_gateway` and in each copied `scripts/jev_gateway` under `~/.claude`, `~/.codex`, `~/.factory`, `~/.hermes`, and `~/.reasonix`. | `VEXJOY_NO_DEPS=1` |
| `~/.bashrc`, `~/.local/share/no-agent-summary/` | Copies a Bun preload there and adds a managed `~/.bashrc` block that exports it in `BUN_OPTIONS`. The preload stops Claude Code's background-agent summary calls. | None |
| Permissions | `chmod 700` on `~/.claude` and `~/.claude/learning`; `chmod 600` on `~/.claude/settings.json`, `~/.claude/history.jsonl`, and the Factory, Reasonix, and Antigravity hook settings. | None |
| `~/.claude/vexjoy/` | Engine state: the ledger, reports, backups, trash, a lock, `overlays.json` for private skill roots, and `bin/python3`, the Python every hook runs under. | None |

Two things keep the install in sync afterwards: the `post-merge` hook after `git pull`, and the `sync-to-user-claude` SessionStart hook whenever Claude Code starts in this checkout. Both run `vexinstall sync --target all`, which never moves entries it does not own. The SessionStart sync skips worktrees and `/tmp` checkouts, and stops when `VEXJOY_SYNC_DISABLED=1` is set.

`./install.sh --uninstall` and `--rollback` undo an install; see the README's Installation flags and [installer-layout.md](installer-layout.md).

## Gates in Every Repo

The installer registers its hooks in `~/.claude/settings.json`, so they run in every repo you open with Claude Code, not only this one. These hooks block an action:

| Hook | Blocks | Turn off |
|---|---|---|
| `pretool-branch-safety` | `git commit` on `main` or `master` | `BRANCH_SAFETY_BYPASS` |
| `pretool-review-before-push-gate` | `git push`, `git subtree push`, `gh pr create`, and `gh pr edit --base` until `/pr-review` records the commit (`scripts/review-record.py mark`). It applies to every repo except non-fork `github.com/notque` ones, and blocks when it cannot tell. Bypasses are logged to `~/.claude/state/review-gate/bypass.log`. | `REVIEW_PUSH_GATE_BYPASS` |
| `ci-merge-gate` | `gh pr merge` while CI checks fail or are pending | `CI_MERGE_GATE_BYPASS` |
| `security-review-hook` | `git commit` when the staged changes have HIGH or CRITICAL findings | `VEXJOY_SECURITY_REVIEW_SKIP` |
| `pretool-ruff-format-gate` | `git push` when changed Python files fail `ruff format`, in repos that enforce ruff format | `RUFF_FORMAT_GATE_BYPASS` |
| `pretool-plan-gate` | Write and Edit under the project root's `agents/` or `skills/` until a `task_plan.md` modified in the last 24 hours exists there | `PLAN_GATE_BYPASS` |
| `pretool-adr-creation-gate` | Writing a new `agents/<name>.md`, `skills/<name>/SKILL.md`, `pipelines/<name>/SKILL.md`, or top-level hook file when no ADR for it exists in `~/.vexjoy-agent/<repo>/adrs/` or the repo's `adr/` | `ADR_CREATION_GATE_BYPASS` |
| `pretool-worktree-edit-guard` | An agent working in a worktree editing the main checkout | `WORKTREE_EDIT_GUARD_BYPASS` |
| `pretool-config-protection` | Write, Edit, and MultiEdit to a linter or formatter config file (ESLint, Prettier, Biome, `ruff.toml`, `.golangci.*`, `setup.cfg`, and similar; not `pyproject.toml`), so the source gets fixed instead of the rule | `CONFIG_PROTECTION_BYPASS` |
| `pretool-private-name-leak-gate` | Commits, pushes, and PR text that name a private component; it does nothing without `~/private-skills` or when every target repo is a private GitHub repo | `PRIVATE_NAME_GATE_BYPASS` |
| `pipeline-phase-gate` | Writes that advance a pipeline phase before the phase's artifact exists | `PIPELINE_PHASE_GATE_BYPASS` |
| `pretool-synthesis-gate` | Writes during an ADR session that has no synthesis yet | `SYNTHESIS_GATE_BYPASS` |

Turn a gate off by setting its variable to `1` in the environment that launches Claude Code, for example `BRANCH_SAFETY_BYPASS=1 claude`. Setting it inside a running session does not reach the hooks. Every hook reads such a variable; [hooks/README.md](../hooks/README.md#bypass) explains the names. To drop a hook for good, list it under `disabled.hooks` in `.local/profile.yaml` and rerun `./install.sh`.

`pretool-unified-gate` adds safety checks to every Bash, Write, Edit, and Read call. It blocks:

- `git add -f` on ignored paths, and shell writes to `.gitignore`;
- destructive commands such as a broad `rm -rf`, `DROP DATABASE`, `TRUNCATE TABLE`, `chmod 777`, a force-push to `main` or `master`, `git branch -D`, `mkfs`, `dd if=`, and `terraform destroy` without `-target`;
- a new agent or skill without a registered ADR;
- writes to credential and other sensitive files (reading one only warns);
- dev servers bound to a public interface;
- sysadmin footguns such as piping a download into a shell;
- edits to the live hooks or a `.claude/settings.json` outside a feature branch;
- raw `git push`, `gh pr create`, and `gh pr merge`, but only when `CLAUDE_OPERATOR_PROFILE` is not `personal`, the default.

It fails open if it crashes. Its overrides are documented only in the hook source, on purpose: a deny that turns out to be a false positive should not teach anyone, or any agent, to switch the guard off.

Everything else is advisory. `pretool-dispatch-spec-gate` only warns unless `DISPATCH_SPEC_GATE_MODE=deny` is set, and `pretool-routing-gate` runs only on Antigravity CLI. No Stop or SubagentStop hook blocks: `stop-drift-guard` can wake a stopped session in this checkout to report drift, and `subagent-completion-guard` emits a deny that SubagentStop ignores.

## Where Next

- [For Knowledge Workers](for-knowledge-workers.md): writing, research, data analysis, moderation, and HTML artifacts.
- [For Developers](for-developers.md): architecture, extension points, agents, and skills.
- [For AI Power Users](for-ai-wizards.md): routing, hooks, and pipeline internals.
- [For AI Agents](for-claude-code.md): machine-dense component inventory.
