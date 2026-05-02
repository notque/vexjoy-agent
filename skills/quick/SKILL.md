---
name: quick
description: "Tracked lightweight execution with composable rigor flags: --trivial, --discuss, --research, --full. Covers zero-ceremony inline fixes (≤3 edits) through contained multi-file changes."
user-invocable: true
argument-hint: "[--trivial] [--discuss] [--research] [--full] <task>"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
  - Skill
  - Task
routing:
  force_route: true
  triggers:
    - quick task
    - small change
    - ad hoc task
    - add a flag
    - small refactor
    - targeted fix
    - quick fix
    - typo fix
    - fix typo
    - fix the typo
    - one-line change
    - trivial fix
    - rename variable
    - rename this variable
    - update value
    - fix import
  pairs_with: []
  complexity: Simple
  category: process
---

# /quick - Tracked Lightweight Execution

Quick covers the lightweight tier from zero-ceremony inline fixes (≤3 edits, `--trivial`) through contained multi-file changes. Full-ceremony Simple+ tasks (task_plan.md, agent routing, quality gates) belong in `/do`. Design principle: **composable rigor** -- base mode is minimal (plan + execute), users add process via flags.

**Flags** (all OFF by default):

| Flag | Effect |
|------|--------|
| `--trivial` | Zero-ceremony inline mode for ≤3 file edits: no plan display, no branch, direct commit. Escalates automatically if >3 edits needed. For typo fixes, one-line constants, renames, import fixes. |
| `--discuss` | Pre-planning discussion phase to resolve ambiguities (breadth-first -- surfaces all gray areas at once) |
| `--interview` | Depth-first decision-tree interview before editing. One question at a time with recommendation. Use when decisions are interdependent and answer A constrains B. |
| `--research` | Research phase before planning to build context on unfamiliar code |
| `--full` | Plan verification + full quality gates (tests, lint, diff review) |
| `--no-branch` | Skip feature branch creation, work on current branch |
| `--no-commit` | Skip commit step (for batching multiple quick tasks) |

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| example-driven tasks | `examples.md` | Loads detailed guidance from `examples.md`. |
| tasks related to this reference | `templates.md` | Loads detailed guidance from `templates.md`. |

## Instructions

### Phase --trivial: INLINE EXECUTION (only with --trivial flag)

When `--trivial` is passed (or the router recognises a clearly one-line mechanical change), execute inline without plan display, feature branch, or subagents.

**Step 1: Read CLAUDE.md**

Read repository CLAUDE.md before any edit.

**Step 2: Scope check**

| Question | If Yes |
|----------|--------|
| Needs reading docs, investigating behavior, or understanding unfamiliar code? | Redirect to `/quick --research` |
| Touches more than 3 files? | Redirect to standard `/quick` |
| Adds imports from new packages or modifies dependency files? | Redirect to standard `/quick` |
| Ambiguous or underspecified? | Ask one clarifying question; if still ambiguous, use `/quick --discuss` |

If redirecting: `This task exceeds --trivial scope ([reason]). Continuing as /quick.` Proceed to Phase 0.

**Step 3: Locate target files and execute**

Read target file(s). Make edits. Track edit count. At 3 edits, if more needed, stop: "Scope exceeded during --trivial execution (3+ edits needed). Preserving work done. Continuing as /quick." Hand off to standard phases with context.

**Step 4: Check branch**

If on main/master, create branch: `git checkout -b quick/<brief-description>`.

**Step 5: Stage and commit**

Stage specific files with `git add <specific-files>`. Commit using format from `references/templates.md` (conventional commit, usually `fix:`, `chore:`, or `refactor:`).

**Step 6: Display summary**

Use the `--trivial` summary banner format from `references/templates.md`.

**GATE**: Edit count is 1-3, commit succeeded. STOP -- do not proceed to Phase 0.

---

### Phase 0: SETUP

**Step 1: Read CLAUDE.md**

Read and follow the repository's CLAUDE.md before anything else.

**Step 2: Parse flags**

Extract `--discuss`, `--interview`, `--research`, `--full`, `--no-branch`, `--no-commit`. Everything remaining is the task description.

**Step 3: Scope check**

If the task involves multiple components, architectural changes, or needs parallel execution, redirect to `/do` -- quick tasks are single-threaded by design.

### Phase 1: DISCUSS (only with --discuss flag)

Activates when `--discuss` is passed or request signals uncertainty ("not sure", "maybe", "could be", "what do you think").

**Step 1: Identify ambiguities**

- What exactly should change? (if underspecified)
- Which approach among alternatives? (if multiple valid paths)
- What are the acceptance criteria? (if success unclear)

**Step 2: Present questions**

Use DISCUSS banner format from `references/templates.md`. Wait for response. Do not proceed until resolved.

**GATE**: All ambiguities resolved. Proceed to Phase 2 or Phase 3.

### Phase 1.5: INTERVIEW (only with --interview flag)

Depth-first sibling to `--discuss`. Use when decisions are interdependent and answering A changes valid options for B.

**Step 1: Load depth-first reference**

Load `planning/references/depth-first-interview.md` and follow its phases (PRIME -> ENUMERATE BRANCHES -> TRAVERSE -> COMPILE OUTPUT). Hard cap: 5 total questions, 3-level recursion per branch.

**Step 2: Treat `--interview` as explicit trigger**

Per the reference's Phase 0, `/quick --interview` is explicit invocation. Skip opt-out question -- go directly to ENUMERATE BRANCHES.

**Step 3: Compile output to inline context**

Keep the structured block (Resolved Decisions / Carried Forward / Scope Boundary / Mode Used) inline. Use it to inform Phase 3 PLAN. No separate `task_plan.md` for `/quick`.

**GATE**: Interview output emitted. Proceed to Phase 2 or Phase 3.

### Phase 2: RESEARCH (only with --research flag)

Activates when `--research` is passed or the task touches unfamiliar code.

**Step 1: Identify scope** -- which files and patterns need reading.

**Step 2: Read and analyze** -- Read source files, tests, configuration. Build mental model of current behavior, where the change fits, what might break.

**Step 3: Summarize findings** -- Brief (3-5 line) summary of what you learned and how it affects the plan.

**GATE**: Sufficient understanding to plan. Proceed to Phase 3.

### Phase 3: PLAN

**Step 1: Generate task ID**

Format: `YYMMDD-xxx` (xxx = Base36 sequential: 0-9, a-z).

```bash
date_prefix=$(date +%y%m%d)
```

Check STATE.md for today's highest sequence number and increment. If no tasks today, start at `001`. If STATE.md is corrupted, scan git log for `Quick task YYMMDD-` patterns. On branch name collision, increment and retry.

**Step 2: Create inline plan**

Always display the inline plan -- it catches misunderstandings before wrong edits. Use inline plan banner from `references/templates.md` instead of `task_plan.md`.

If estimated edits exceed 15, prompt user to consider `/do`. If task involves security, payments, or data migration, recommend `--full`.

**Step 3: Create feature branch** (unless --no-branch)

```bash
git checkout -b quick/<task-id>-<brief-kebab-description>
```

If already on a non-main feature branch and `--no-branch` set, stay on current branch.

**GATE**: Task ID assigned, plan displayed, branch created. Proceed to Phase 4.

### Phase 4: EXECUTE

**Step 1: Make edits** per plan. Track edit count.

**Step 2: Scope monitoring**

- At 10 edits: warning -- "10 edits reached. Quick tasks typically stay under 15."
- At 15 edits: suggest upgrade -- "15 edits reached. This may benefit from /do with full planning. Continue? [Y/n]"
- No hard cap -- user decides.

**Step 3: Verify changes** (base mode)

Run language-appropriate syntax check (e.g., `python3 -m py_compile`, `go build ./...`, `tsc --noEmit`). If `--full`, run full quality gate instead (Phase 5).

**GATE**: All planned edits complete. Sanity check passes.

### Phase 5: VERIFY (only with --full flag)

**Step 1**: Run tests for affected packages/modules only.

**Step 2**: Lint check on changed files.

**Step 3**: Review changes with `git diff`. Check for unintended changes, missing error handling, broken imports.

**GATE**: Tests pass, lint clean, diff reviewed. Proceed to Phase 6.

### Phase 6: COMMIT (skip with --no-commit)

Stage specific files with `git add <specific-files>`. Commit using format from `references/templates.md`. Include task ID in commit body.

**GATE**: Commit succeeded. Verify with `git log -1 --oneline`.

### Phase 7: LOG

**Step 1: Update STATE.md**

Use STATE.md schema from `references/templates.md` to create if absent, append one row per task. If escalated from `--trivial`, use tier `trivial->quick`.

**Step 2: Display summary**

Use completion banner format from `references/templates.md`.

## Reference Material

> See `references/examples.md` for worked examples per flag mode, task ID format, and error handling.
