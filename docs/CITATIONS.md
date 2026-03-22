# Citations

Patterns, repos, and sources that influenced the toolkit's design. Not attribution for code (the code is original) but acknowledgment of ideas that shaped decisions.

## Repos

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

## Principles

### Claude Code Documentation
https://docs.anthropic.com/en/docs/claude-code

Official documentation for hooks, settings.json schema, slash commands, and MCP server configuration. The event-driven hook architecture (PostToolUse, UserPromptSubmit, SessionStart) is the foundation for error learning, retro knowledge injection, and auto-plan detection.

### Conventional Commits
https://www.conventionalcommits.org

Commit message format used throughout: `feat:`, `fix:`, `refactor:`, `docs:`. Enables automated changelog generation and semantic versioning.
