# Linux CLI contract checklist

Toolkit defaults that constrain the spec:

- Primary data is stdout; diagnostics/progress are stderr. Machine output is stable; human output may evolve.
- Disable color/progress off-TTY, with `NO_COLOR`, or `TERM=dumb`.
- Use `-` for file-like stdin/stdout. Secrets use stdin or a protected file, never flags.
- Prompt only on a TTY. `--no-input` fails actionably; destructive noninteractive work requires explicit force.
- Config precedence is `flags > environment > project > user > system`; user config uses XDG paths.
- Reject ambiguous subcommand abbreviations: once accepted, they become contracts.
- Flag/subcommand/env/config/schema changes need deprecation and migration. Telemetry is explicit opt-in with collection and retention disclosed.
