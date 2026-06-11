# CLI Design Checklist

Condensed from the Command Line Interface Guidelines (https://clig.dev/, CC BY-SA). Rebuilt for this toolkit: Linux-only, spec-focused. Apply each section while filling the spec skeleton in SKILL.md.

## Philosophy

- Human-first: optimize default output for humans; keep scripts working via stable modes (`--json`, `--plain`, exit codes).
- Composability: assume your output becomes someone else's input. Respect stdio, exit codes, signals.
- Consistency: reuse standard flag names and conventions; break a convention only deliberately and document why.
- Say just enough: make progress visible, keep success output brief.
- Conversation: design for trial-and-error loops — previews, dry runs, recoverable errors, suggested next commands.

## Basics

- Use a real argument-parsing library (built-in or reputable), because hand-rolled parsers drift from conventions.
- Exit `0` on success, non-zero on failure; map the few failure modes callers branch on.
- Primary output to stdout; messages, logs, and errors to stderr.

## Help

- Support `-h` and `--help`; help ignores other args.
- On missing required args: concise usage + 1–2 examples + pointer to `--help`.
- Subcommand CLIs: support `mycmd help sub` and `mycmd sub --help`.
- Lead help with examples; list common flags first.

## Output

- Detect TTY: human formatting when interactive, plain when piped.
- Offer `--plain` (stable line-based) and/or `--json` for parsing.
- On state change, say what changed and the new state.
- `-q/--quiet` trims success output when scripts want silence.
- Color: use sparingly; disable when stdout is not a TTY, `NO_COLOR` is set, `TERM=dumb`, or `--no-color` given.
- Animations and progress bars only when stdout is a TTY.

## Errors

- Catch expected errors and rewrite for humans; reserve stack traces for `--debug`, because traces scare users and bury the fix.
- Keep signal-to-noise high; group repeated errors; put the most important line last.
- On unexpected crash: point to debug log location and bug-report path.

## Arguments and flags

- Prefer flags over positional args; positionals only for one obvious repeated item (`rm a b c`).
- Every flag has a long form; reserve one-letter forms for the most common.
- Standard names:

| Flag | Meaning |
|---|---|
| `-h, --help` | help |
| `--version` | version to stdout |
| `-q, --quiet` | less output |
| `-v, --verbose` | more output (`-v` means verbose, version stays long-form) |
| `-d, --debug` | debug output |
| `-f, --force` | skip confirmation |
| `-n, --dry-run` | preview only |
| `--json` | structured output |
| `-o, --output <file>` | output path |
| `--no-input` | disable prompts |

- Support `-` for stdin/stdout where input/output is a file.
- Secrets travel via `--secret-file` or stdin, because flag values leak through `ps` and shell history.
- Defaults serve most users without aliases.

## Interactivity

- Prompt only when stdin is a TTY.
- `--no-input`: prompts off; missing required input fails with an actionable message.
- Password prompts disable echo.
- Destructive ops: interactive confirmation; non-interactive requires `--force`.

## Subcommands

- Use subcommands when complexity demands; share global flags, config, and help.
- Pick noun-verb or verb-noun and stay consistent.
- Keep pairs sharply distinct (`update` vs `upgrade`); reject ambiguous abbreviations, because accepted abbreviations become contracts.

## Robustness

- Validate early; fail fast with a clear message.
- Print something within 100ms, especially before network I/O.
- Timeouts on network calls, configurable.
- Make reruns safe: idempotent where possible, crash-only recovery where feasible.
- Ctrl-C exits fast with bounded cleanup; a second Ctrl-C may force, and says so.

## Configuration and environment

- Per-invocation: flags. Per-user: env or XDG config file. Per-project: checked-in config file.
- Precedence (high → low): flags > env > project config > user config > system config.
- Env var names: uppercase, digits, underscores. Respect `NO_COLOR`, `DEBUG`, `EDITOR`, `PAGER`, `TERM`, `TMPDIR`, `HOME`.
- Modify other programs' config only with consent; prefer adding new files over editing existing ones.

## Future-proofing

- Args, flags, subcommands, config, env vars, and output modes are contracts. Keep changes additive; deprecate loudly and early with a migration path.
- Let human output evolve; keep `--plain`/`--json` stable for scripts.

## Naming and distribution

- Name: short, lowercase, memorable, easy to type, low collision risk.
- Prefer a single binary or a self-contained script; make uninstall easy.
- Telemetry only with explicit opt-in consent, stating what, why, and retention.
