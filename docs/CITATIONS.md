# Citations

Patterns, repos, and sources that shaped the toolkit. This includes external influences and original innovations developed through trial and error. Keeping provenance clear helps future sessions understand why things work the way they do.

## Repos

### BugRoger/beastmode
https://github.com/BugRoger/beastmode

Referenced as prior art for the retro knowledge system. Our implementation has diverged significantly from this approach.

**Patterns noted:**
- Original inspiration for session-level learning and knowledge accumulation concepts
- Our implementation (SQLite + FTS5, confidence scoring, graduation pipeline) bears little resemblance to the current state of beastmode

### caliber-ai-org/ai-setup
https://github.com/caliber-ai-org/ai-setup

TypeScript CLI that fingerprints projects and generates AI configs for Claude, Cursor, Codex, and GitHub Copilot. Studied for its deterministic scoring system, learning ROI tracking, and multi-platform writer abstraction.

**Patterns adopted:**
- Deterministic component scoring without LLM calls (ADR-031). Their 6-dimension scoring rubric for config quality proved that mechanical validation catches a class of errors LLM evaluation misses entirely.
- Learning staleness detection (ADR-033). Flagging learnings with zero activations over N sessions as prune candidates.
- PID-based lockfile with staleness detection (ADR-035). Their concurrent access pattern for preventing data corruption in shared files.
- Score regression guard concept (ADR-034). Comparing quality before and after changes, auto-reverting if score drops.

**Patterns noted but not adopted:**
- Token budget scoring (penalizing configs over 2000 tokens). Conflicts with our high-context agent philosophy.
- Multi-platform config generation (Claude + Cursor + Codex writers). We're Claude Code focused.
- Session event JSONL format for learning capture. Our SQLite + FTS5 approach serves better for search and graduation.

## Blog Posts

### vexjoy.com
https://vexjoy.com

The toolkit author's blog. Posts that crystallized design decisions:

- **Everything That Can Be Deterministic, Should Be** - The four-layer architecture (Router, Agent, Skill, Script) and the division of labor between LLMs and programs.
- **The /do Router** - Specialist selection over generalism. Why keyword-matching routing produces more consistent results than generalist improvisation.
- **The Handyman Principle** - Context as a scarce resource. Why specialized agents beat one giant system prompt.
- **I Was Excited to See Someone Else Build a /do Router** - Convergent evolution in AI tooling and the case for open sharing.

## Original Innovations

Patterns developed through trial and error in this toolkit, not derived from external sources.

### The /do Router and Specialist Selection
Keyword-matching routing to domain-specific agents. The insight that "which agent has the right mental scaffolding" matters more than "which agent is smartest." Developed over months of observing inconsistent results from generalist prompts.

### Anti-Rationalization as Infrastructure
Auto-injected anti-rationalization tables that make it structurally difficult to skip verification. Not a policy doc that gets ignored. Infrastructure that fires on every code modification, review, and security task. Born from repeated incidents where "should work" turned out to be wrong.

### Learning Graduation Pipeline
Record at 0.7 confidence, boost on validation, graduate into agent/skill markdown, ship together. The insight that review findings should be immediately embedded as permanent behavior changes, not passively recorded for "multiple observations." Developed after noticing that deferred learnings never got acted on.

### Three-Wave Comprehensive Review
20+ specialized reviewer agents in 3 cascading waves: per-package deep review (Wave 0), cross-cutting foundation (Wave 1, 11 agents), context-aware deep-dive (Wave 2, 10 agents). Each wave's findings enrich the next. Evolved from single-agent reviews that kept missing cross-cutting concerns.

### Pipeline-First Architecture
The principle that any task with 3+ phases should be a pipeline with gates, artifacts, and parallelization. Emerged from observing that ad-hoc execution skips steps under time pressure but pipelines with explicit phase gates don't.

### Two-Tier Evaluation (Deterministic + LLM)
Deterministic scoring (file existence, frontmatter validity, path checking) as a fast, free first pass, with LLM evaluation for nuanced quality. Neither replaces the other. Adopted after analyzing how mechanical failures wasted LLM evaluation tokens.

### Retro Knowledge Injection
SQLite + FTS5 database of operational learnings, auto-injected into relevant agent prompts via hook. Benchmarked at +5.3 avg score improvement, 67% win rate. The cross-session memory that makes each session smarter than the last.

### The Handyman Principle
"Context is a scarce resource, not a dumpster." Specialized agents loaded only when their triggers match, rather than one giant system prompt. Named and articulated through blog writing that forced clarity on why large prompts degrade performance.

### Manifest + Undo for Upgrades
SHA-256 snapshot before modification, backup storage, score regression detection, and rollback capability. Created after an upgrade broke agent references and required manual git archaeology to recover.

## Principles

### Claude Code Documentation
https://docs.anthropic.com/en/docs/claude-code

Official documentation for hooks, settings.json schema, slash commands, and MCP server configuration. The event-driven hook architecture (PostToolUse, UserPromptSubmit, SessionStart) is the foundation for error learning, retro knowledge injection, and auto-plan detection.

### Conventional Commits
https://www.conventionalcommits.org

Commit message format used throughout: `feat:`, `fix:`, `refactor:`, `docs:`. Enables automated changelog generation and semantic versioning.
