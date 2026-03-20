# Competitive Analysis: obra/superpowers vs claude-code-toolkit

**Date:** 2026-03-19
**Method:** 8 parallel research agents read every file in obra/superpowers (165 files), cross-referenced against full inventory of claude-code-toolkit (230 components)

---

## Executive Summary

obra/superpowers and claude-code-toolkit are architecturally different systems solving overlapping problems. Superpowers is a **lean, skill-centric toolkit** (11 skills, 1 agent, 1 hook) designed to work across 5 platforms. Our toolkit is a **deep, agent-centric system** (58 agents, 114 skills, 28 hooks) optimized for Claude Code with extensive domain coverage.

**Bottom line:** Superpowers has **6 genuinely valuable ideas** we lack. We have **massively deeper capabilities** they lack. The gap is philosophical, not feature-count.

---

## Scale Comparison

| Metric | superpowers | claude-code-toolkit |
|--------|-------------|---------------------|
| Skills | 11 | 114 |
| Agents | 1 | 58 |
| Hooks | 1 (SessionStart only) | 28 (all 7 event types) |
| Scripts | ~10 (shell) | 30 (Python) |
| Platforms | 5 (Claude, Cursor, Codex, OpenCode, Gemini) | 1 (Claude Code) |
| Domain agents | 0 | 22 (Go, Python, TS, K8s, DB, etc.) |
| Review agents | 0 (1 reviewer prompt template) | 26 specialized reviewers |
| Quality gates | 0 | 3 (Go, Python, universal) |
| Voice system | 0 | 4 skills + 2 scripts |
| Learning system | 0 | SQLite FTS5 + 6 hooks |
| Pipeline framework | 0 | 12 pipeline skills |
| Feature lifecycle | 0 | 5-phase system |
| Content/publishing | 0 | 14 skills + 4 WordPress scripts |

---

## What Superpowers Has That We Lack (Genuine Value)

### 1. Visual Brainstorming with Browser Companion
**Value: HIGH**

A zero-dependency WebSocket server that opens a browser window alongside the terminal. The AI writes HTML fragments (mockups, A/B comparisons, clickable option cards), users click choices in the browser, and selections feed back to the AI via a `.events` JSONL file.

- Solves a real problem: visual design decisions described in text are inferior to rendered options
- Per-question decision framework: text questions stay in terminal, visual questions go to browser
- Zero dependencies (hand-rolled RFC 6455 WebSocket in ~300 lines of Node.js)
- Auto-cleanup via idle timeout + parent PID monitoring
- Fully cross-platform including Windows (MSYS2 detection)

**Our gap:** We have no visual output channel. All design decisions happen in text. For UI work, this is a real limitation.

**Adoption difficulty:** Medium. Requires a Node.js server, file-watching, and browser integration — but the zero-dep approach makes it portable.

### 2. Skill Triggering Tests via Session Transcript Forensics
**Value: HIGH**

They test whether skills activate correctly by:
- Running Claude in headless mode with natural language prompts
- Parsing `.jsonl` session transcripts for tool invocations
- Checking that the Skill tool was invoked (not that Claude said it would)
- Detecting **premature action** (Claude starts implementing before loading the skill)
- Testing across model tiers (Haiku vs Opus) to measure degradation
- Using adversarial prompt variations (9+ styles per skill)

**Our gap:** We have `evals/tasks/` with 4 task sets, but no automated test harness that runs Claude headlessly, parses session logs, or detects premature action. Our skill-eval skill exists but is manual.

**Adoption difficulty:** Medium. Requires headless Claude invocation infrastructure and session log parsing.

### 3. Persuasion-Informed Skill Design
**Value: MEDIUM-HIGH**

Their `writing-skills` meta-skill applies Cialdini's persuasion research to skill authoring, citing a 2025 paper (Meincke et al.) showing persuasion techniques doubled LLM compliance from 33% to 72%. They map specific principles:
- **Authority**: Iron Laws in code blocks, absolute language
- **Commitment**: Early acknowledgment gates
- **Scarcity**: "You have ONE chance" framing
- **Social proof**: "From 24 failure memories..." data citations
- **Avoid**: Liking (creates sycophancy), Reciprocity (feels manipulative)

**Our gap:** We use anti-rationalization tables and Iron Laws intuitively but don't have a formal framework grounded in persuasion research for skill design.

**Adoption difficulty:** Low. This is a design principle, not infrastructure.

### 4. TDD Applied to Skill Documentation
**Value: MEDIUM-HIGH**

Skills themselves are tested using the RED-GREEN-REFACTOR cycle:
1. **RED:** Run a pressure test scenario (e.g., emergency production fix + time pressure + sunk cost) — agent fails to follow the skill
2. **GREEN:** Write/revise the skill — agent now follows it
3. **REFACTOR:** Identify remaining rationalization loopholes and close them

Pressure tests combine multiple psychological pressures (time + authority + exhaustion) to simulate real scenarios. They also have a "meta-diagnostic" technique: after an agent makes the wrong choice, ask it *how the skill could have been written to prevent that*, yielding three categories (ignored rules, documentation gap, organization problem).

**Our gap:** We have `testing-agents-with-subagents` skill and `skill-eval` but they don't include pressure testing with combined psychological pressures or the meta-diagnostic technique.

**Adoption difficulty:** Low-Medium. Could enhance our existing skill-eval and testing-agents-with-subagents skills.

### 5. Two-Stage Review (ADR Compliance + Code Quality)
**Value: MEDIUM**

Their subagent-driven-development separates review into two distinct stages:
1. **ADR compliance**: Did you build what was asked? Nothing more, nothing less?
2. **Code quality**: Is what you built well-constructed?

The ADR compliance reviewer uses adversarial framing: "The implementer finished suspiciously quickly. Their report may be incomplete, inaccurate, or optimistic. You MUST verify everything independently."

**Our gap:** We have 27 review agents but they focus on different dimensions (security, performance, type design, etc.), not the ADR-compliance-vs-quality distinction. Our `comprehensive-review` dispatches 11 foundation agents including `reviewer-adr-compliance` which now fills this gap.

**Adoption difficulty:** Low. Already implemented as `reviewer-adr-compliance` (Wave 1 Agent #11).

### 6. Multi-Platform Skill Portability
**Value: MEDIUM (strategic, not immediate)**

Skills written once with Claude Code tool names, plus per-platform mapping tables:
- Gemini CLI: `Read` → `read_file`, `Write` → `write_file`, etc.
- Codex: `Task` → `spawn_agent`/`wait`/`close_agent`
- Graceful degradation: Gemini (no subagents) falls back from SDD to sequential execution

**Our gap:** We're Claude-Code-only. If a user wanted to use our skills with another platform, they'd need to rewrite tool references.

**Adoption difficulty:** High for full multi-platform. Low for just adding tool-mapping reference docs.

---

## What Superpowers Does Differently (Not Necessarily Better)

### A. No Router — Skills Self-Chain
Superpowers has no `/do` command. Instead, the `using-superpowers` skill tells the agent to check if any skill applies (even at 1% probability) and invoke it. Skills know what comes next and invoke successors.

**Our approach is better because:** Explicit routing prevents misrouting, enables force-route triggers for critical patterns, and the routing-gap-recorder catches misses. Self-chaining relies entirely on LLM judgment, which is the thing most likely to fail.

### B. Single Hook (SessionStart Only)
One hook injects one document (`using-superpowers/SKILL.md`) wrapped in `<EXTREMELY_IMPORTANT>` tags. Everything cascades from there.

**Our approach is better because:** Our 28 hooks across 7 event types enable reactive behavior (error learning, review capture, confidence decay, usage tracking) that a single bootstrap hook cannot provide. The learning system alone justifies the hook complexity.

### C. No Domain Agents
Superpowers has zero domain-specific agents. All work is done by the base model following skill instructions.

**Our approach is better because:** Domain agents carry specialized knowledge (Go idioms, K8s operations, PostgreSQL optimization) that skill instructions alone cannot encode at sufficient depth. The 22 domain agents and 26 review agents represent genuine expertise, not just process.

### D. Skill Descriptions Must Not Summarize Process
They discovered that when a YAML description summarizes the workflow, Claude follows the summary instead of the full skill body. Their fix: descriptions contain only triggering conditions.

**Relevant to us:** Our skill descriptions often contain process summaries. This finding from their real-world testing is worth validating against our own behavior.

---

## What We Have That Superpowers Completely Lacks

| Capability | Our System | Their Equivalent |
|------------|-----------|-----------------|
| **26 specialized review agents** | Deep expertise per dimension | 1 review prompt template |
| **Learning system** (SQLite FTS5 + 6 hooks) | Persistent cross-session knowledge | Nothing |
| **28 hooks across 7 events** | Reactive automation | 1 SessionStart hook |
| **22 domain agents** | Go, Python, TS, K8s, DB expertise | Generic model only |
| **Pipeline framework** (12 skills) | Structured multi-phase workflows | Ad-hoc skill chaining |
| **Voice system** (4 skills + 2 scripts) | Deterministic voice validation | Nothing |
| **Feature lifecycle** (5 phases) | Design → Plan → Implement → Validate → Release | Manual skill invocation |
| **Content/publishing** (14 skills + 4 scripts) | Blog, WordPress, SEO, taxonomy | Nothing |
| **Quality gates** (Go, Python, universal) | Language-specific CI checks | Nothing |
| **Anti-rationalization framework** | Systematic injection by task type | Per-skill tables only |
| **MCP integrations** (gopls, Playwright) | Language server + browser automation | Nothing |
| **ADR system** (7 ADRs + compliance hooks) | Architecture decision tracking | Spec docs only |
| **Routing system** (INDEX.json + /do + force-routes) | Deterministic request classification | Self-routing via LLM |

---

## Recommendations

### Adopt (genuine value, fill real gaps)

1. **Skill triggering test harness** — Build automated tests that run Claude headlessly, parse session transcripts, and detect premature action. Adapt their `run-test.sh` pattern to our skill set.

2. **ADR compliance reviewer agent** — Added `reviewer-adr-compliance` as Wave 1 Agent #11 in comprehensive-review. Focus: "Did the implementation match the ADR? Nothing more, nothing less?" Includes adversarial framing. **DONE.**

3. **Persuasion-aware skill design guide** — Document the Cialdini-based framework as a reference for skill authors. Add to our `writing-skills` equivalent or AGENT_TEMPLATE_V2.

4. **Pressure testing for skills** — Enhance `testing-agents-with-subagents` with combined psychological pressure scenarios (time + authority + sunk cost) following their methodology.

### Consider (strategic value, higher effort)

5. **Visual brainstorming companion** — For UI-heavy work, a browser-based output channel is genuinely valuable. Could be implemented as a skill + Node.js server, gated behind `ui-design-engineer` routing.

6. **Validate description-summarization finding** — Test whether our skill descriptions that contain process summaries cause Claude to skip reading the full skill body. If confirmed, update skill authoring guidelines.

### Skip (not worth it for our context)

7. **Multi-platform support** — We're Claude-Code-only and our depth depends on Claude-specific features (hooks, MCP, subagents). Cross-platform portability would require abstracting away our most powerful capabilities.

8. **Self-chaining skills** — Our explicit routing is more reliable than LLM self-routing. The complexity is justified.

9. **Single-hook architecture** — Our 28 hooks provide learning, error detection, and reactive automation that a single bootstrap hook cannot.

---

## Philosophical Comparison

| Dimension | superpowers | claude-code-toolkit |
|-----------|-------------|---------------------|
| **Architecture** | Skill-centric (skills ARE the system) | Agent-centric (agents carry expertise) |
| **Routing** | LLM self-routes via skill checking | Deterministic router classifies and dispatches |
| **Depth** | Shallow but wide (5 platforms) | Deep on one platform (Claude Code) |
| **Complexity** | ~15 meaningful files | ~230 components |
| **Testing** | Automated headless + transcript forensics | Manual skill-eval + evals task sets |
| **Learning** | None (stateless across sessions) | SQLite FTS5 with confidence decay |
| **Review** | 1 template, 2-stage (spec + quality) | 26 agents, 3-wave auto-discovery |
| **Philosophy** | "Teach the model to fish" (skills = instructions) | "Route to the expert" (agents = specialists) |

Both share: anti-rationalization tables, Iron Laws, verification-before-completion, TDD methodology, subagent isolation, YAGNI enforcement.

---

*Research conducted by 8 parallel agents analyzing all 165 files in obra/superpowers against 230 components in claude-code-toolkit.*
