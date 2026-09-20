---
name: domain
description: "SAPCC review/audit, OpenSearch detection, WordPress live validation, and enterprise-search operating knowledge."
user-invocable: true
allowed-tools:
  - Agent
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
  - mcp__plugin_playwright_playwright__browser_navigate
  - mcp__plugin_playwright_playwright__browser_wait_for
  - mcp__plugin_playwright_playwright__browser_snapshot
  - mcp__plugin_playwright_playwright__browser_evaluate
  - mcp__plugin_playwright_playwright__browser_network_requests
  - mcp__plugin_playwright_playwright__browser_console_messages
  - mcp__plugin_playwright_playwright__browser_resize
  - mcp__plugin_playwright_playwright__browser_take_screenshot
  - mcp__chrome-devtools__navigate_page
  - mcp__chrome-devtools__take_screenshot
  - mcp__chrome-devtools__take_snapshot
  - mcp__chrome-devtools__list_console_messages
  - mcp__chrome-devtools__list_network_requests
  - mcp__chrome-devtools__lighthouse_audit
  - mcp__chrome-devtools__resize_page
routing:
  not_for: "general code review (use review), general security (use security)"
  triggers: [sapcc review, sapcc audit, sapcc compliance, siem detection, sigma rule, mitre att&ck mapping, opensearch detection, soc escalation, validate wordpress post, enterprise search, search relevance, BM25, query understanding, search quality, vector search, hybrid search]
  force_route: false
  pairs_with: [golang-general-engineer, opensearch-elasticsearch-engineer, programming]
  category: domain
---

# Domain operations

Choose one mode. Load only its named references.

## SAPCC review and audit

Confirm SAPCC from `go.mod` and map non-vendor Go packages first.

- **Review** is ten parallel, cross-package specialists grouped by rule domain. Load `references/sapcc-review-agent-dispatch-prompts.md`.
- **Audit** uses 5–8 generalists grouped by package (roughly 5–15 files each). Load `references/sapcc-audit-phase-2-dispatch-agents.md`.

Dispatch the whole fan-out together. Deduplicate by location, keeping the higher severity. Audit is read-only unless fixes were requested. A review reports the ten-domain scorecard; an audit reports MUST-FIX/SHOULD-FIX/NIT counts by package. Patterns seen in 4+ SAPCC repositories gain one severity level; one-repository patterns lose one.

## OpenSearch Security Analytics

Load:

- `references/opensearch-detection-engineering.md` for rule/API and field conventions;
- `references/opensearch-detection-safety-patterns.md` before changing indices or detectors;
- `references/opensearch-incident-escalation.md` for the local escalation contract.

The references define five hard gates: mapped fields, complete MITRE mapping, detection-owned alias bootstrap, static chained-query indices, and complete SLA-bound escalation. Author SIGMA first and dry-run against labeled traffic before enforcement; local FP target is ≤10%.

## WordPress live validation

Use Playwright MCP by default; use Chrome DevTools when the user requests their browser or Lighthouse. This is read-only: never click, type, or modify the site. Browser evidence—not inference—is authoritative.

Load `references/wordpress-phase-checks.md`, `references/wordpress-validation-checks.md`, and, only for invocation details, `references/wordpress-playwright-tools.md`.

Run every check and viewport defined by the references. Broken/wrong content, failed images, and visible draft placeholders are blockers. If no browser backend exists, report SKIPPED; never infer a result.

## Enterprise search

Always identify platform/version and problem class before loading one reference:

| Problem | Reference |
|---|---|
| ranking, BM25, boosts, LTR | `search-relevance-tuning.md` |
| intent, entities, synonyms, expansion | `search-query-understanding.md` |
| mappings, analyzers, reindex, ILM | `search-index-management.md` |
| judgments, nDCG/MRR, experiments | `search-search-quality.md` |
| latency, shards, cache, breakers | `search-performance-optimization.md` |

Also load `search-llm-search-failure-modes.md`. Annotate every DSL snippet with platform/version; OpenSearch diverges from Elasticsearch after 7.10, and Solr `edismax` is not Elasticsearch `multi_match`.
