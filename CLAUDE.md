# VexJoy Agent -- Claude Code

Read `AGENTS.md` first. It holds the shared rules (communication standard, Jev
loop, trust boundary, writing style, merge gate, project conventions). This
file adds Claude Code-specific dispatch.

@AGENTS.md

## Claude Code dispatch

The main thread is an orchestrator. It classifies requests, picks and loads the
skill, and evaluates results. It runs Trivial and Simple work itself, since a
dispatched agent cold-reloads about 20k tokens of instructions and re-reads files the
main thread already holds. Dispatch an agent via the Agent tool only when it
pays: parallel fan-out over independent parts, long lanes (about 5+ files, or
work that would bloat main context), worktree isolation, read-only Haiku
gathering, and Medium or Complex work. Rules: `skills/meta/do/SKILL.md`.
