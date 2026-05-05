# Contributing

## Standards

| Criterion | Pass | Fail |
|-----------|------|------|
| **Specific** | Actionable steps, exit criteria | Vague advice ("be careful") |
| **Verifiable** | Evidence requirements | Trusts LLM confidence |
| **Battle-tested** | Real workflows, A/B tested | Hypothetical "should work" |
| **Minimal** | What guides the agent, nothing else | Verbose human explanations |
| **Dense** | Every word carries instruction | Prose where a table works |

## Component Types

| Component | Location | Format | Purpose |
|-----------|----------|--------|---------|
| Agent | `agents/{name}.md` | YAML frontmatter + markdown | Domain expertise |
| Skill | `skills/{name}/SKILL.md` | YAML frontmatter + phased instructions | Workflow methodology |
| Hook | `hooks/{name}.py` | Python script | Event-driven automation |
| Script | `scripts/{name}.py` | Python utility | Deterministic operations |

## Adding a Skill

1. Create `skills/{kebab-case-name}/SKILL.md`
2. Include YAML frontmatter: `name`, `description`, `category`, `pairs_with`
3. Structure with phased instructions and explicit gates
4. Add a Reference Loading Table if the skill needs conditional context
5. End with verification requirements (evidence, not confidence)
6. Optional: add `skills/{name}/references/` for deep domain content

**Skill anatomy:**

```
┌─────────────────────────────────────────────────┐
│  SKILL.md                                       │
│  ┌─ Frontmatter ─────────────────────────────┐  │
│  │ name, description, category, pairs_with    │  │
│  │ triggers, success-criteria                 │  │
│  └────────────────────────────────────────────┘  │
│  Reference Loading Table (conditional imports)   │
│  Phased Instructions (numbered, with gates)      │
│  Verification (evidence requirements)            │
└─────────────────────────────────────────────────┘
```

## Adding an Agent

1. Create `agents/{domain}-{role}-engineer.md`
2. Include YAML frontmatter: routing triggers, complexity, category, pairs_with, allowed-tools
3. Define operator context: always/default/optional behaviors
4. Add inline hooks if needed (PostToolUse reminders)
5. Create `agents/{name}/references/` for deep domain knowledge
6. Run `python3 scripts/generate-agent-index.py` to update INDEX.json

## Quality Gates

Before submitting:

- [ ] `ruff check . --config pyproject.toml` passes
- [ ] `ruff format --check . --config pyproject.toml` passes
- [ ] `python3 scripts/validate-references.py` passes (if adding references)
- [ ] New skills/agents appear in INDEX after running generators
- [ ] No secrets, credentials, or API keys in committed files

## Design Constraints

Read [PHILOSOPHY.md](docs/PHILOSOPHY.md) first.

- Deterministic? Write a script. Reserve LLM for judgment calls.
- Keep SKILL.md lean. Deep content lives in `references/`.
- Every skip-worthy step needs a counter-argument baked in.
- Spend tokens on more specialists in parallel, not longer prompts.

## PR Process

1. Create a feature branch (never commit to main directly)
2. Run quality gates locally
3. PR description: what changed and why (not how)
4. Conventional commit format: `feat:`, `fix:`, `chore:`, `docs:`
