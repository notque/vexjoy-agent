---
name: cli-design
description: "Design a CLI interface: args, flags, help, output, errors, exit codes, config."
user_invocable: false  # default -- router-dispatched, not user-typed
allowed-tools:
  - Read
  - Write
  - Grep
  - Glob
  - Bash
routing:
  triggers:
    - "design a CLI"
    - "CLI interface"
    - "command line tool design"
    - "CLI flags"
    - "CLI spec"
    - "argument parsing design"
    - "exit codes"
  category: engineering
  pairs_with:
    - test-driven-development
    - python-quality-gate
---

# CLI Design

Design a command-line tool's interface before implementation: human-first, script-friendly, Linux-only. Output is a compact spec the user or an agent can implement directly. Rubric source: clig.dev (rebuilt as `references/clig-checklist.md`).

## Workflow

### Phase 1: SCOPE

Lock the interface with the minimum questions. Proceed with the conventions in Phase 2 when the user is unsure.

- Command name and one-sentence purpose.
- Primary user: humans, scripts, or both.
- Input sources: args vs stdin; files vs URLs. Secrets travel via file or stdin, because flags leak through `ps` and shell history.
- Output contract: human text, `--json`, `--plain`, exit codes.
- Interactivity: prompts allowed? `--no-input` needed? confirmation for destructive ops?
- Config model: flags, env, config file; precedence.

**Gate:** name, purpose, and I/O contract are known. Proceed only when gate passes.

### Phase 2: DESIGN

Load [references/clig-checklist.md](references/clig-checklist.md) and apply it as the default rubric. For each section, pick the convention and record it in the spec. Diverge from a convention only deliberately, and document the divergence in the spec — interfaces are contracts, and surprising contracts break scripts.

### Phase 3: DELIVER

Produce the spec from this skeleton. Drop a section only when it genuinely has no content; fill every other section.

1. **Name**: `mycmd`
2. **One-liner**
3. **USAGE**: `mycmd [global flags] <subcommand> [args]`
4. **Subcommands**: what each does, idempotence, state changes
5. **Args/flags table**: name, type, default, required?, example
6. **I/O contract**: stdout carries primary data and machine output; stderr carries diagnostics, errors, progress
7. **Exit codes**: `0` success, `1` generic failure, `2` invalid usage; add command-specific codes only when callers will branch on them
8. **Safety**: `--dry-run`, confirmation rules, `--force`, `--no-input`
9. **Env/config**: env vars; config file path; precedence flags > env > project config > user config > system
10. **Examples**: 5–10 invocations covering common flows, including one piped/stdin example

**Gate:** every flag used in the examples appears in the flags table, and every failure mode shown maps to an exit code.

## Constraints

- Stay at spec altitude: when the request is "design the interface," deliver the spec and stop. Implementation is a separate task.
- Keep the spec language-agnostic. Recommend a parsing library only when asked.
- Target Linux. Skip Windows/macOS path, signal, and packaging concerns.

## Error handling

### Request mixes design and implementation
Cause: user says "design and build."
Solution: deliver the spec first, get confirmation, then implement against it.

### Spec balloons past one page
Cause: subcommand sprawl or speculative flags.
Solution: cut flags that lack a named user need; defaults should serve most users without aliases.
