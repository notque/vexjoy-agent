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

templates/           Scaffolding templates for new components

adr/                 Architecture Decision Records (gitignored, local working documents)
```

Three details matter. Generate, rather than hand-edit, `agents/INDEX.json` and `skills/INDEX.json` with `scripts/generate-agent-index.py` and `scripts/generate-skill-index.py`. Hooks import shared code from `hooks/lib/`, never from each other. Skill evaluation uses `skills/meta/toolkit/` for methodology and `scripts/skill_eval/` for runners.

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

`hooks/pretool-private-name-leak-gate.py` blocks commits, pushes, and PR text that name a private component. It also blocks brand terms (a first name segment shared by two or more private components) and any term listed in `~/private-skills/.private-terms` (one per line, `#` comments), even when the term already appears on `main`. To check the whole tracked tree for the same terms, run `python3 scripts/private-term-audit.py`. It prints matching paths with the term redacted and exits 1 on any hit. Both no-op on machines without `~/private-skills`, such as CI.

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
5. **Record** any dead end in `docs/what-didnt-work.md` with its evidence location
6. **Edit** the agent or skill file yourself when a finding should change behavior
7. **Commit** in conventional format
8. **Push** to remote with tracking
9. **PR** creation via `gh pr create`
10. **CI** must pass
11. **Merge** after CI, required review, and authorization

The `pr-workflow` skill automates steps 3 through 10.

## Testing

Framework: pytest.

```bash
pytest -v                            # all tests
pytest hooks/tests/ -v               # hook tests
pytest scripts/tests/ -v             # script tests
pytest hooks/tests/test_routing_decision_recorder.py -v   # single file
```

Test according to component type:

| Component | Approach |
|-----------|----------|
| Hooks | Feed JSON input, assert JSON output. Test happy path and silent path. Mock external deps. |
| Scripts | Test CLI interface. Deterministic: input X always produces output Y. |
| Agents/Skills | Use `skills/meta/toolkit/` methodology and `scripts/skill_eval/` runner for quality assessment. |

Fixtures: `scripts/tests/fixtures/` for script test data. Hook tests inline their fixtures.

## Key Conventions

**Conventional commits.** Use `type(scope): description`; types are feat, fix, refactor, docs, test, and chore. Focus on what and why.

**No AI attribution.** Omit "Generated with Claude Code" and co-author lines from all commits.

**Branch safety.** Create feature branches for all work. The `pretool-branch-safety.py` hook enforces this by blocking commits to protected branches.

**Wabi-sabi in docs.** Sentence fragments where they're clear. Varied length. No "delve", "leverage", "comprehensive", "robust", "streamline", "empower." The `scripts/scan-ai-patterns.py` script catches these.

**INDEX.json is generated.** Run the generation scripts. They parse frontmatter and build the index. Hand-edits get overwritten.

**Hooks live in hooks/.** Write there. The sync hook deploys to `~/.claude/hooks/` on session start.

**Scripts are deterministic.** No LLM calls. No judgment. If it involves reasoning, it is an agent or skill.

**50ms hook budget.** Hooks fire on every tool call or prompt. Keep them fast. Profile with `scripts/benchmark-hooks.py` if uncertain.
