---
summary: "Developer map: dispatch model, adding components, shipping changes."
read_when:
  - "adding or changing a component"
  - "learning the dispatch model"
---

# For Developers

This guide covers dispatch, component creation, and shipping changes. Register new components with the router so users can request their work in plain English.

## Architecture in 60 Seconds

The main dispatch path is:

```
User request → Router (/do) → Agent (*.md) → Skill (SKILL.md) → Script (*.py)
```

The router selects an agent for domain knowledge and a skill for the procedure. Scripts handle repeatable work. Hooks inject context, record telemetry, and enforce checks at lifecycle events.

## Directory Structure

```
agents/              Domain experts. One .md per agent, optional references/ subdirectory
  INDEX.json         Generated routing index (don't hand-edit)

skills/              Workflow methodologies. One directory per skill, each with SKILL.md
  INDEX.json         Generated skill index

hooks/               Event-driven Python scripts. Fire on lifecycle events
  lib/               Shared utilities (hook_utils.py, learning_db_v2.py, route_events.py)
  tests/             Hook-specific tests

scripts/             Deterministic CLI tools. Python scripts for mechanical operations
  tests/             Script-specific tests

commands/            Slash command definitions

adr/                 Architecture Decision Records (gitignored, local working documents)
```

Two details matter. Generate, rather than hand-edit, `agents/INDEX.json` and `skills/INDEX.json` with `scripts/generate-agent-index.py` and `scripts/generate-skill-index.py`. Hooks import shared code from `hooks/lib/`, never from each other.

### Private Skills

Keep non-public skills in `~/private-skills/`, using the same category structure:

```
~/private-skills/
└── content/
    └── my-custom-skill/
        ├── SKILL.md
        └── references/
```

Initialize it as a separate repository if you want version control:

```bash
mkdir -p ~/private-skills
cd ~/private-skills
git init
git add -A && git commit -m "initial private skills"
```

At session start, the sync hook deploys each category child containing `SKILL.md` to `~/.claude/skills/`; deleting that source directory removes the deployed copy on the next sync. Private and public skills follow the same conventions.

`hooks/pretool-private-name-leak-gate.py` blocks commits, pushes, and PR text that name a private component. It also blocks brand terms (a first name segment shared by two or more private components) and any term listed in `~/private-skills/.private-terms` (one per line, `#` comments), even when the term already appears on `main`. To check the whole tracked tree for the same terms, run `python3 scripts/private-term-audit.py`. It prints matching paths with the term redacted and exits 1 on any hit. Both read `~/private-skills`, or `~/pgh/private-skills` when that is where the repo lives, and no-op on machines with neither, such as CI. The gate allows a match when every repo the text can reach is a private GitHub repo: the remote a `git push` targets, every remote for `git commit` and `gh pr`, or the `gh pr --repo` value. It asks `gh api repos/OWNER/REPO` only after a match, and treats no remote, a non-GitHub URL, or a `gh` error as public. `private-term-audit.py` still reports every hit.

## Creating Components

Tell `/do` the component type, domain, and purpose. The creator handles structure, registration, and routing integration.

### Agents

```
/do create an agent for [your domain]
```

### Skills

```
/do create a skill for [your workflow]
```

### Hooks

```
/do create a hook for [your purpose]
```

## Key Architecture Points

Each component type has a distinct role:

- **Agents** (`agents/*.md`) know *what* to do. Domain expertise, patterns, failure modes.
- **Skills** (`skills/*/*/SKILL.md`) know *how* to structure work. Phases, gates, methodology.
- **Hooks** (`hooks/*.py`) respond to *events*. JSON in, JSON out, 50ms budget.
- **Scripts** (`scripts/*.py`) perform *deterministic* operations. Indexing, validation, linting.

Use scripts for mechanical work and agents or skills for contextual judgment.

The `/do` router connects the components. After creating one, test it with a request that should select it:

```
/do [request that should trigger your new component]
```

## PR Workflow

The full cycle:

1. **Branch** from main (`feature/`, `fix/`, `refactor/` prefix)
2. **Implement** changes
3. **Review** using the risk-selected lane in `pr-workflow`
4. **Fix** confirmed findings and rerun affected checks
5. **Edit** the agent or skill file yourself when a finding should change behavior
6. **Commit** with one lowercase past-tense sentence (see Key Conventions)
7. **Push** to remote with tracking
8. **PR** creation via `gh pr create`
9. **CI** must pass
10. **Merge** after CI, required review, and authorization

The `pr-workflow` skill automates steps 3 through 9.

## Testing

Framework: pytest.

```bash
pytest -v                            # fast tier; the default markers skip slow, integration, and performance tests
pytest hooks/tests/ -v               # hook tests
pytest scripts/tests/ -v             # script tests
pytest hooks/tests/test_routing_decision_recorder.py -v   # single file
```

Test according to component type:

| Component | Approach |
|-----------|----------|
| Hooks | Feed JSON input, assert JSON output. Test happy path and silent path. Mock external deps. |
| Scripts | Test CLI interface. Deterministic: input X always produces output Y. |
| Agents/Skills | Use `skills/meta/toolkit/` methodology, validators, and review for quality assessment. |

Fixtures: `scripts/tests/fixtures/` for script test data. Hook tests inline their fixtures.

## Key Conventions

**Commit messages.** One lowercase past-tense sentence saying what changed and why, with no type prefix and no trailing period. The full rule is in [AGENTS.md](../AGENTS.md) (Writing style).

**Attribution.** No "Generated with Claude Code" or `Co-Authored-By` lines; the repo's `.claude/settings.json` sets `attribution` to empty strings. Trailer lines such as `Claude-Session: <url>` are allowed after a blank line.

**Branch safety.** Create feature branches for all work. The `pretool-branch-safety.py` hook enforces this by blocking commits to protected branches.

**Review before push.** In any repo that is not a non-fork `github.com/notque` repo, `pretool-review-before-push-gate.py` blocks `git push`, `git subtree push`, `gh pr create`, and `gh pr edit --base` until `/pr-review` has recorded the commit with `scripts/review-record.py mark`. Each fix commit needs its own review. Title, body, and label edits and `gh pr ready` pass. Not caught: git aliases (`git p`), nested `$( $(...) )` substitutions, and PR creation through `gh api`. Commands it cannot judge (an unresolvable `cd` or `GIT_DIR` target, `git $SUB push`) are denied. It fails closed on purpose: a notque repo that also has a mirror or colleague remote, or an origin that uses an ssh host alias, counts as not mine and needs a review.

**Wabi-sabi in docs.** Sentence fragments where they're clear. Varied length. No "delve", "robust", "streamline", or "empower"; the full list is `scripts/data/banned-patterns.json`. The `scripts/scan-ai-patterns.py` script catches these.

**INDEX.json is generated.** Run the generation scripts. They parse frontmatter and build the index. Hand-edits get overwritten. A script that reads an index calls `ensure_fresh_indexes` in `scripts/lib/index_freshness.py` first: it regenerates an index that is missing or older than its sources, so a local check matches CI.

**Agent descriptions stay at or under 300 bytes.** Claude Code loads every agent description into each session, so a long one costs tokens on every turn. `scripts/validate-skill-frontmatter.py` fails an `agents/*.md` description over 300 bytes or one that holds an `<example>` block.

**Hooks live in hooks/.** Write there. The sync hook deploys to `~/.claude/hooks/` on session start.

**Scripts are deterministic.** No LLM calls. No judgment. If it involves reasoning, it is an agent or skill.

**50ms hook budget.** Hooks fire on every tool call or prompt. Keep them fast. Profile with `scripts/benchmark-hooks.py` if uncertain.

**Multiple Claude Code accounts.** Run 10+ isolated accounts on one machine using `CLAUDE_CONFIG_DIR`. Each account gets its own config directory (`~/.claude-accounts/<name>/`) with separate credentials, session history, and settings. Shell aliases let you pick an account before Claude Code starts — no `/logout`/`/login` needed.

```bash
python3 scripts/manage-accounts.py add work --alias cwork
python3 scripts/manage-accounts.py add personal --alias cpersonal
python3 scripts/manage-accounts.py list
python3 scripts/manage-accounts.py check
```

The `add` command registers the account, creates the config dir, links its `skills/`, `agents/`, and `commands/` to `~/.claude` (where `./install.sh` installs everything once), and writes shell aliases that launch `claude --dangerously-skip-permissions --chrome --system-prompt="."`. Run `manage-accounts.py link` to repair older accounts.

Know what those flags do before you use the aliases. `--dangerously-skip-permissions` runs every tool call without a permission prompt, so you no longer approve file edits, shell commands, or network calls; only blocking hooks (and a sandbox, if you configured one) can stop one. `--chrome` connects the session to your Chrome browser. `--system-prompt="."` replaces Claude Code's built-in system prompt (see the README's Token-saving mode).

After `add`, log in once per account:

```bash
CLAUDE_CONFIG_DIR=~/.claude-accounts/work claude
# inside Claude Code: /login
```

Reload your shell and use aliases from any terminal: `cwork`, `cpersonal`. See `skills/meta/accounts/SKILL.md` for full reference.
