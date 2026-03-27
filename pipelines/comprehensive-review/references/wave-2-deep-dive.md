# Wave 2: Deep-Dive Agents (10 agents)

These agents receive Wave 0+1 aggregated findings as input. They perform targeted deep-dives informed by per-package analysis (Wave 0) and cross-cutting analysis (Wave 1).

**ALL 10 agents MUST be dispatched in ONE message for true parallel execution.**

Use `model: sonnet` for all Wave 2 agents. The orchestrator runs on Opus; dispatched agents run on Sonnet.

## Agent Roster

| # | Agent | Focus Area | Wave 1 Context Used |
|---|-------|------------|---------------------|
| 11 | `reviewer-performance` | Performance | Architecture findings → focus on hot paths |
| 12 | `reviewer-concurrency` | Concurrency | Silent-failure + architecture findings → concurrent paths |
| 13 | `reviewer-api-contract` | API Contracts | Business-logic + type-design findings → contract-sensitive code |
| 14 | `reviewer-dependency-audit` | Dependencies | Docs-validator findings → dependency documentation gaps |
| 15 | `reviewer-error-messages` | Error Messages | Silent-failure + code-quality findings → error paths |
| 16 | `reviewer-dead-code` | Dead Code | Code-quality + docs-validator findings → abandoned artifacts |
| 17 | `reviewer-naming-consistency` | Naming | Code-quality + language-specialist findings → convention baselines |
| 18 | `reviewer-observability` | Observability | Silent-failure findings → observability gaps at failure points |
| 19 | `reviewer-config-safety` | Config Safety | Security + docs-validator findings → config security gaps |
| 20 | `reviewer-migration-safety` | Migration Safety | API-contract + business-logic findings → migration-sensitive changes |

## Standard Agent Prompt Template

Each Wave 2 agent prompt includes the standard review scope PLUS the Wave 0+1 context:

```
REVIEW SCOPE:
- Files to review: [list of changed files]
- Change context: [what was changed and why, if known]
- Repository: [current directory]

WAVE 0+1 CONTEXT (use this to focus your analysis):
[Insert $WAVE01_SUMMARY — loaded from $REVIEW_DIR/wave01-summary.md]

MCP TOOL DISCOVERY (do this FIRST, before any file reads):
- Use ToolSearch to check for available MCP tools that can enhance your analysis:
  a. Run ToolSearch("gopls") — if Go files are in scope, this loads type-aware
     analysis tools (go_file_context, go_diagnostics, go_symbol_references, etc.)
  b. Run ToolSearch("context7") — loads library documentation lookup tools for
     verifying dependency usage and API correctness
- If gopls tools are available AND this is a Go repository:
  * Use go_file_context after reading any .go file to understand intra-package dependencies
  * Use go_symbol_references before flagging unused or misused symbols
  * Use go_diagnostics on files you flag to confirm real vs false-positive issues
- If Context7 tools are available:
  * Use resolve-library-id + query-docs to verify library API usage in flagged code

INSTRUCTIONS:
1. Read the CLAUDE.md file(s) in this repository first
2. Run MCP TOOL DISCOVERY steps above
3. Review the Wave 0 per-package context for package-level issues already found
4. Review the Wave 1 cross-cutting context for foundation issues already found
5. Use Wave 0+1 findings to FOCUS your deep-dive analysis:
   - Prioritize packages flagged as NEEDS_ATTENTION or CRITICAL by Wave 0
   - Prioritize files and paths flagged by Wave 1
   - Look for issues in YOUR domain that neither Wave 0 nor Wave 1 would catch
   - Cross-reference your findings with both waves to add depth
6. Do NOT simply repeat Wave 0 or Wave 1 findings — add NEW insights
7. Use MCP tools (gopls, Context7) during analysis where they add precision
8. Use structured output format with severity classification
9. Include file:line references for every finding

OUTPUT FORMAT:
Return findings as:
### [CRITICAL|HIGH|MEDIUM|LOW]: [One-line summary]
**File**: `path/to/file:LINE`
**Issue**: [Description]
**Impact**: [Why this matters]
**Fix**: [Concrete code fix]
**Wave 0+1 Cross-Ref**: [Which earlier finding this relates to, if any]
---
```

## Agent-Specific Context Instructions

| Agent | Extra Context Instructions |
|-------|--------------------------|
| `reviewer-performance` | Use Wave 0 per-package findings to identify packages with complexity issues. Use Wave 1 architecture findings to identify hot paths. Focus on algorithmic complexity, N+1 queries, allocation waste. **MCP**: For Go, use gopls `go_symbol_references` to trace hot path call chains |
| `reviewer-concurrency` | Use Wave 0 per-package findings for concurrent patterns within packages. Use Wave 1 silent-failure + architecture findings for cross-package concurrent paths. Focus on races, goroutine leaks, deadlocks. **MCP**: For Go, use gopls `go_diagnostics` to detect race condition warnings |
| `reviewer-api-contract` | Use Wave 0 per-package findings to understand internal API surfaces. Use Wave 1 business-logic + type-design findings for contract-sensitive endpoints. Focus on breaking changes, status codes. **MCP**: Use Context7 to verify API contract claims against library docs |
| `reviewer-dependency-audit` | Use Wave 1 docs-validator findings to cross-reference documented vs actual dependencies. Run govulncheck/npm audit/pip-audit. Focus on CVEs, licenses, deprecated packages. **MCP**: Use Context7 `resolve-library-id` + `query-docs` to verify dependency API usage. For Go, use gopls `go_vulncheck` for vulnerability scanning |
| `reviewer-error-messages` | Use Wave 0 per-package error handling patterns. Use Wave 1 silent-failure + code-quality findings. Focus on error message quality, actionability, consistency. |
| `reviewer-dead-code` | Use Wave 0 per-package findings to identify unused internal APIs between files. Use Wave 1 code-quality + docs-validator findings. Focus on unreachable code, unused exports. |
| `reviewer-naming-consistency` | Use Wave 0 per-package naming patterns to detect intra-package drift. Use Wave 1 code-quality + language-specialist findings. Focus on cross-package naming consistency. |
| `reviewer-observability` | Use Wave 0 per-package findings for packages missing instrumentation. Use Wave 1 silent-failure findings for error paths missing observability. Focus on RED metrics gaps. |
| `reviewer-config-safety` | Use Wave 0 per-package findings for hardcoded values within packages. Use Wave 1 security + docs-validator findings. Focus on secrets, missing env var validation. |
| `reviewer-migration-safety` | Use Wave 1 api-contract + business-logic findings to identify migration-sensitive changes. Focus on reversible migrations, deprecation paths, rollback safety. |
