---
summary: "Branch pointer for the local-only shadow routing-health loop."
read_when:
  - "working on feat/outcome-routing-loop"
---

# Outcome-Routing Shadow Loop — branch pointer

Branch: `feat/outcome-routing-loop` (LOCAL-ONLY: never push / PR / merge to main).

This branch builds a **shadow** routing-health loop: fix outcome signal fidelity
(three-way failure/neutral/success), add a per-dispatch event log, build the health
policy as a pure library, wire it gated (DEMOTE cannot fire on current data — by design;
TIE-BREAK can, on a low-confidence pick with an evidenced alternate), and
prove the mechanism on real (read-only) plus seeded synthetic data.

Why shadow, not live: the learning DB holds 276 successes / 0 failures ever. The
demote-at-floor rule matches 0 rows, so live re-ranking is inert. The finalizer boosts
everything that is not an unambiguous failure (including neutral next-prompts), and rows
are `(topic,key)` aggregates with no per-dispatch history — so faithful replay of past
routing is impossible. A prior A/B returned null (89.8% == 89.8%).

Working documents (local-only, gitignored — not in this commit):
- `research/forward-plan/implementation-spec.md` — the FROZEN spec (read first).
- `research/forward-plan/{2026-06-03-forward-plan,codex-plan,input-bundle}.md` — inputs.
- ADR `outcome-routing-shadow-loop` (local-only, `adr/` is gitignored) — the ADR
  (decision, alternatives, data-semantics appendix). Registered via `scripts/adr-query.py`.

`research/` and `adr/` are gitignored development artifacts; a safety hook blocks
force-adding them. They stay local by design — this tracked pointer keeps the branch
self-documenting without committing ignored content.
