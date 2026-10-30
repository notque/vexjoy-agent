# VexJoy Agent -- Claude Code

Read `AGENTS.md` first. It holds the shared rules (communication standard, Jev
loop, trust boundary, writing style, merge gate, project conventions). This
file adds Claude Code-specific dispatch.

## Claude Code dispatch

The main thread is an orchestrator. It classifies requests, dispatches agents
via the Agent tool, and evaluates results. Dispatch an agent for all work. The
main thread orchestrates, agents execute.
