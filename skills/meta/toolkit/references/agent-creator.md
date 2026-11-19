# Agent Creator

Repo agents are retired (plan 009). A request to create an agent in this repo produces a skill reference: `skills/<category>/<skill>/references/<slug>.md`, with depth in `references/<slug>/`. When no skill fits the domain, create a new skill (Create Skill mode) and put the reference under it. Work runs in the main thread; when dispatch pays, a fresh `general-purpose` worker gets a prompt that starts: "Read ~/.claude/skills/<skill>/references/<slug>.md and follow it; load every file its Reference Loading Table matches."

A reference is a contract: it sets constraints, expertise, and phases, not application code.

An agent `.md` file is written only when the owner asks for a private overlay agent. See "Private overlay agent (owner request only)" at the end.

Phases: **DISCOVER → DESIGN → SCAFFOLD → REGISTER → VALIDATE**

---

## Phase 1 — DISCOVER

Check for domain overlap before creating anything.

```bash
grep -ril "<domain-keyword>" skills/*/*/SKILL.md skills/*/*/references/*.md | sort -u
ls skills/*/*/references/ | grep "<domain-prefix>"
```

Gate 1: If an existing skill reference covers the domain, extend it (or add a depth file under its `references/<slug>/`) instead of creating a new one. Proceed only when no reference covers the domain, or the user confirms after seeing the overlap.

Read `docs/PHILOSOPHY.md` before proceeding — the philosophy governs operator context structure, progressive disclosure, positive framing, and tool restrictions. Components that violate it will fail CI.

---

## Phase 2 — DESIGN

Decide the reference's home and loading contract before writing a single line.

| Decision | Question to answer |
|----------|--------------------|
| Owning skill | Which existing skill's domain does this extend? If none, which new skill (Create Skill mode)? |
| Role type | Reviewer/auditor, code modifier/engineer, or orchestrator method? |
| Worker tools | What a `general-purpose` worker that loads it may use: reviewers→Read/Glob/Grep; engineers→+Edit/Write/Bash; orchestrators→Read/Agent/Bash. State read-only rules in the reference body. |
| Complexity | Low (single-file, read-only), Medium (multi-file, routing), High (full sweeps, orchestration) |
| Signals | 3–6 specific phrases for the skill's Reference Loading Table — not generic verbs |
| Related references | 2–3 sibling references or skills commonly loaded with it; verify each exists on disk |
| Depth files | Domains needing depth — each goes in `references/<slug>/` loaded on demand |
| Signal craft | Intent verb + domain object, 2–3 adjacent terms, one false-positive boundary with redirect |
| Activation cases | 3 should-trigger / 2 should-not-trigger / 2 near-miss phrases drafted now, saved at scaffold time |

Load `references/agent-design-patterns.md` for operator context structure, hook design, routing design, authority/trust framing, and smells-to-rewrite guidance.

Load `references/agent-eval-design.md` when drafting the signals and activation cases — the case classes and worked example live there.

Gate 2: All nine decisions answered before writing reference content.

---

## Phase 3 — SCAFFOLD

**File layout:**

```
skills/<category>/<skill>/
├── SKILL.md                 # add one Reference Loading Table row for the new reference
└── references/
    ├── <slug>.md            # the reference — the contract a worker loads
    └── <slug>/
        └── *.md             # depth, loaded on demand
```

**Writing the reference body:**

1. Role statement: what work it covers and what domain it owns
2. Expertise list: concrete capabilities with specific sub-skills
3. Mandatory pre-action protocol: what to read before acting and why
4. Operator context block: hardcoded behaviors, default behaviors (ON), optional behaviors (OFF)
5. Capabilities and limitations table: CAN / CANNOT, naming the skill or reference that owns out-of-scope requests
6. Reference loading table: `| Signal | Load These Files | Why |` — required when a `references/<slug>/` directory exists
7. Workflow section: phase-by-phase with gates
8. Error handling: cause/solution pairs for common failures
9. Preferred patterns: what good looks like (positive framing)
10. Anti-rationalization table: common rationalizations with required action

**Owning skill row:** add `| <signals> | references/<slug>.md | <why> |` to the skill's Reference Loading Table. A reference no table names is never loaded.

**Positive framing (CI gate):** Every instruction tells the reader what to do. Run the check after writing:

```bash
python3 scripts/validate_positive_instruction_docs.py
```

Exit code 1 means violations. Rewrite flagged instructions in action form before proceeding.

**Progressive disclosure:** The reference stays navigable. Deep material goes in `references/<slug>/`, loaded on demand. If `--check-size` flags the file, extract content to the depth directory first.

Gate 3: Reference written, and the owning skill's loading table names it.

---

## Phase 4 — REGISTER

The router finds the skill, and the skill's loading table finds the reference. Regenerate the skill index when skill frontmatter changed (new skill, new triggers):

```bash
python3 scripts/generate-skill-index.py
```

Gate 4: A new skill appears in `skills/INDEX.json`; a new reference appears in its skill's Reference Loading Table.

---

## Phase 5 — VALIDATE

Run all validation checks before declaring the reference shippable.

```bash
# Loading-table signals, reference sizes, Skill-tool call and dispatch names
python3 scripts/validate-references.py --check-placeholders
python3 scripts/validate-references.py --check-size
python3 scripts/validate-references.py --check-skill-calls

# Positive framing gate (scans all tracked .md files)
python3 scripts/validate_positive_instruction_docs.py
```

Gate 5: All scripts exit 0. No phantom related-reference entries. No positive-framing violations.

**Manual review** (the scripts cannot check these):

- **Signal craft**: read the loading-table signals aloud. Do they state intent, name 2–3 adjacent terms, mark one false-positive boundary? See `references/agent-creator/agent-frontmatter-template.md` Description Craft.
- **Activation cases checked**: mental-pass 3 should-trigger / 2 should-not-trigger / 2 near-miss phrases against the skill's triggers and the loading-table signals. See `references/agent-eval-design.md`.

---

## Error Handling

### Signal conflict with an existing reference
Cause: Two references claim the same loading signal in one skill, or two skills claim the same trigger.
Solution: Run the duplicate detection script in `references/toolkit-governance/routing-table-patterns.md`. Make this reference's signals more specific.

### Reference never loads
Cause: The owning skill's Reference Loading Table has no row for it, or the row's signals miss the user's phrasing.
Solution: Add or sharpen the row. Re-run the activation cases.

### Reference loading table missing from validation
Cause: The reference has a `references/<slug>/` directory but no `| Signal | Load These Files | Why |` table.
Solution: Add a reference loading table with at least one row. See `references/agent-design-patterns.md` for the required format.

### YAML parse error (new skill or overlay agent)
Cause: Unquoted colon in description, or bad indentation in routing block.
Solution: Wrap description in double quotes. Parse the frontmatter with `yaml.safe_load`; the traceback pinpoints the line.

---

## Preferred Patterns

### Role-matched worker tools
State in the reference which tools its worker uses — reviewers read only, engineers write, orchestrators dispatch. Claude Code does not enforce a reference's tool list, so the body carries the read-only rule.

### Signals that match natural speech
Write loading signals as phrases a first-time user would naturally say, not internal system identifiers. "fix a bug in Go" routes better than "golang-debugging-invocation".

### Reference loading table as required section
Every reference with a depth directory includes a loading table mapping signals to files. References without this table load depth eagerly, violating the progressive disclosure principle from `docs/PHILOSOPHY.md`.

### Expertise list over motivational framing
List concrete capabilities: version-specific idiom tables, failure mode catalogs, concrete commands. Skip "you are an expert in X" — it adds no information the model will act on.

---

## Private overlay agent (owner request only)

Use this path only when the owner asks for an agent file. Overlay agents never ship in the repo index.

1. **Discover.** `ls private-agents/` and `python3 -c "import json; print(list(json.load(open('agents/INDEX.local.json'))['agents']))"` to check overlap.
2. **Design.** Answer the Phase 2 decisions, with `allowed-tools` in frontmatter and `pairs_with` naming skills that exist on disk.
3. **Scaffold.** Load `references/agent-creator/agent-frontmatter-template.md` for the complete template. Layout:

   ```
   private-agents/
   ├── {agent-name}.md          # operator file — the system prompt contract
   └── {agent-name}/
       ├── references/
       │   └── *.md             # deep context, loaded on demand
       └── SPEC.md              # optional: contract for complex/high-impact agents
   ```

   If the file exceeds 600 lines, extract content to `references/` first.
4. **Register.** `python3 scripts/generate-agent-index.py --include-private` writes `agents/INDEX.local.json`. Gate: the index contains the new agent; the router cannot discover unregistered agents.
5. **Validate.**

   ```bash
   python3 scripts/validate-references.py --agent {agent-name} --agents-dir private-agents
   python3 scripts/validate_positive_instruction_docs.py
   python3 -c "import yaml; yaml.safe_load(open('private-agents/{agent-name}.md').read().split('---')[1]); print('YAML OK')"
   ```

   Verify each `pairs_with` entry exists on disk, and that the agent is not at `agents/{name}.md` in a tracked path. If the agent does not appear in routing after regeneration, confirm `routing.triggers` is a non-empty list.

---

## Reference Loading Table

| Signal | Load These Files | Why |
|--------|-----------------|-----|
| operator context structure, reference loading table format, phase/gate pattern, hook design, routing design, authority/trust framing, smells to rewrite | `references/agent-design-patterns.md` | Vexjoy-specific architecture patterns, instruction hierarchy, and rewrite catalog for vague framing |
| overlay agent frontmatter fields, YAML template, complexity tiers, INDEX.local.json registration, description craft | `references/agent-frontmatter-template.md` | Complete annotated template with all required fields, valid values, and description-writing guide |
| activation eval, output eval, should-trigger / should-not-trigger / near-miss, routing failure, signal tuning | `references/agent-eval-design.md` | How to design activation and output evals at scaffold time so the right reference gets loaded and produces correct work |
