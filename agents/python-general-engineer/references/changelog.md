## Changelog

### v2.1.0 (2026-03-21)
- Graduated 10 retro patterns from LLM classify runtime review into hard gate patterns and preferred patterns
- Added: broad `except OSError: pass`, unguarded `int()` on JSON, `# type: ignore[return-value]`
- Added: input validation on CLI handlers, LLM prompt data surfacing, category definitions
- Source: PR feature/llm-classify-runtime wave review (13 findings across 5 reviewers)

### v2.0.0 (2026-02-13)
- Migrated to v2.0 structure with Anthropic best practices
- Added Error Handling, Preferred Patterns, Anti-Rationalization, Blocker Criteria sections
- Created references/ directory for progressive disclosure
- Maintained all routing metadata, hooks, and color
- Updated to standard Operator Context structure
- Moved detailed patterns to references for token efficiency

### v1.0.0 (2025-12-07)
- Initial implementation with modern Python patterns (3.11+)
