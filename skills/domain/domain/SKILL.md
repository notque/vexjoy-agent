---
name: domain
description: "Domain-specific: SAP Commerce, OpenSearch detection, WordPress validation, enterprise search."
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
  triggers:
    - sapcc review
    - sapcc audit
    - sapcc compliance
    - sapcc standards
    - siem detection
    - sigma rule
    - mitre att&ck mapping
    - detection engineering
    - opensearch detection
    - anomaly detection rule
    - soc escalation
    - validate wordpress post
    - check live post
    - wordpress post validation
    - enterprise search
    - search relevance
    - search ranking
    - BM25
    - query understanding
    - search quality
    - OpenSearch
    - Elasticsearch
    - vector search
    - hybrid search
    - search tuning
  force_route: false
  pairs_with:
    - golang-general-engineer
    - opensearch-elasticsearch-engineer
    - programming
  category: domain
---

# Domain-Specific Skills

Five domains: SAP Commerce Go review, SAP Commerce compliance audit, OpenSearch
SIEM detection engineering, WordPress live validation, and enterprise search.
Classify the request into one domain, then follow its section.

## Mode Detection

| Domain | Signal | Agent |
|--------|--------|-------|
| **SAPCC Review** | sapcc review, 10-specialist review, lead review | `golang-general-engineer` |
| **SAPCC Audit** | sapcc audit, sapcc compliance, full repo audit | `golang-general-engineer` |
| **OpenSearch Detection** | SIEM, SIGMA, MITRE, detection engineering, SOC | (this session) |
| **WordPress Validation** | validate wordpress post, check live post, post rendering | (this session) |
| **Enterprise Search** | search relevance, ranking, BM25, query understanding | `opensearch-elasticsearch-engineer` |

---

## SAPCC Review

10-agent domain-specialist review. Each agent masters one rule domain and scans
every package. Differs from SAPCC Audit: audit segments by *package*
(generalist), review segments by *rule domain* (specialist, cross-package).

### Phase 1: DISCOVER

Verify sapcc project and map the repo.

```bash
head -5 go.mod && grep -c "sapcc" go.mod
find . -name "*.go" -not -path "*/vendor/*" | wc -l
find . -name "*.go" -not -path "*/vendor/*" | sed 's|/[^/]*$||' | sort | uniq -c | sort -rn
```

Check key imports: `go-bits`, `go-api-declarations`, `gophercloud`, `gorilla/mux`, `database/sql`.

**Gate**: Repo mapped. If no sapcc imports, warn but continue.

### Phase 2: DISPATCH

Load `references/sapcc-review-agent-dispatch-prompts.md` for the 10 agent specs.

Dispatch all 10 in ONE message via Agent tool. Each agent gets: path to
sapcc-code-patterns.md, assigned sections, domain-specific reference, all .go
files to scan, finding output format.

**Gate**: All 10 dispatched in single message.

### Phase 3: AGGREGATE

Run `git status --short` to capture modified and untracked files. Collect all
findings. Deduplicate by `file:line` (keep higher severity). Apply severity
boosts:

| Pattern Strength | Boost |
|-----------------|-------|
| NON-NEGOTIABLE (4+ repos) | +1 level |
| Strong Signal (2-3 repos) | No change |
| Context-Specific (1 repo) | -1 level |

Mark quick wins (single-line, no behavioral change, low test risk). Write
`sapcc-review-report.md` with: verdict, scorecard (10 domains x severity),
quick wins, findings by severity, positives, systemic recommendations.

### Phase 4: FIX (only with `--fix`)

Create worktree `sapcc-review-fixes`. Apply quick wins first. After each group:
`go build ./... && go vet ./... && make check 2>/dev/null || go test ./...`.
If fix breaks tests, revert and note. Commit as
`fix: apply sapcc-review findings (N fixes across M files)`.

---

## SAPCC Audit

Full-repo compliance scan. Segments by package (generalist per package).

### Phase 1: DISCOVER

Verify sapcc project (`grep "sapcc" go.mod`). Map packages:
`find . -name "*.go" -not -path "./vendor/*" | sed 's|/[^/]*$||' | sort -u`.
Count files per package. Plan 5-8 agents, 5-15 files each.

**Gate**: Packages mapped, agents planned.

### Phase 2: DISPATCH

Load `references/sapcc-audit-phase-2-dispatch-agents.md` for the dispatch prompt
(11 review areas: over-engineering, dead code, error messages, constructors,
interface contracts, copy-paste, HTTP handlers, database patterns, type patterns,
logging, mixed approaches). Dispatch all in one message via Task tool with
`subagent_type=golang-general-engineer`.

### Phase 3: COMPILE REPORT

Deduplicate by `file:line`. Write `sapcc-audit-report.md` with: verdict,
must-fix/should-fix/nit counts, per-package summary table. Display verdict,
must-fix count, and top 5 findings inline.

Finding format: `[MUST-FIX/SHOULD-FIX/NIT]: summary` with file:line, current
code, correct code, and rationale.

**Audit only**: reads and reports. Does not modify code unless `--fix`.

---

## OpenSearch Detection Engineering

SIEM detection authoring and validation on OpenSearch Security Analytics: SIGMA
rules, query DSL translation, MITRE ATT&CK mapping, anomaly detection,
correlation, and SOC incident escalation.

### Hardcoded Behaviors

- **MITRE ATT&CK on every detection.** Include technique ID (e.g., T1110.003)
  + tactic name + kill chain phase. Tactic alone is insufficient.
- **Field-existence check before rule creation.** Run `GET {index}/_mapping`;
  confirm every rule field exists. Absent fields cause silent failure.
- **Concrete API commands.** Provide `PUT _mapping`, `POST _aliases`, not
  abstract advice.
- **Escalation validation.** Verify all 9 fields before escalation: ticket ID,
  alert link, MITRE mapping, timeline, investigation actions, impact analysis,
  evidence artifacts, containment recommendation, 5 Ws.
- **Severity tier = binding SLA.** Not advisory targets.
- **Detection-owned index.** When bootstrapping field aliases, recommend a
  dedicated index separate from the ingestion datastream.

### Hard Gates

| Pattern | Fix |
|---------|-----|
| Rule field absent from index mapping | `GET {index}/_mapping`; confirm or add field |
| MITRE mapping missing technique ID or tactic | Specify both T####.### and tactic |
| Escalation missing any of 9 fields | Complete all fields per checklist |
| Chained findings monitor on high-frequency schedule | Use static query indices |
| Field alias bootstrap on shared datastream | Create detection-owned index |

### Workflow

1. **Scope**: Identify attack scenario, data source, severity tier. Map to MITRE
   ATT&CK. Confirm log source is ingested.
2. **Validate fields**: `GET {index}/_mapping` for each rule field. Check
   cardinality for `terms` aggregations.
3. **Author**: Write SIGMA rule (vendor-neutral), translate to OpenSearch DSL.
   Load `references/opensearch-detection-engineering.md` for translation
   patterns. Apply FP suppression (CIDR, service-account prefixes, time windows).
4. **Safety check**: Check for index flood, alias bootstrap risk. Load
   `references/opensearch-detection-safety-patterns.md` for the full checklist.
5. **Document**: 6-section use case (General Info, Context, Outcomes, Detection
   Logic, Continuous Improvement, Analyst Support). Load
   `references/opensearch-incident-escalation.md` for template and KPIs.
6. **Calibrate**: Dry-run 5 business days, label TPs/FPs, adjust until FP
   rate <= 10%.
7. **Escalation** (when alert fires): Build 9-field package, apply SLA, hand off
   per RACI.

### Verification STOP Blocks

After authoring: "Have I verified every field via `GET {index}/_mapping`?"
After escalation: "Does the package include all 9 fields?"
After chained monitor: "Does this create a new query index per run?"
After MITRE mapping: "Did I include both technique ID and tactic?"

---

## WordPress Live Validation

Loads a published WordPress post in a headless browser and verifies rendering
matches what was uploaded. The browser is the source of truth.

**Browser backend**: Playwright MCP (default). Chrome DevTools MCP when the user
says "check in my browser" or wants Lighthouse/performance profiling.

### Constraints

- **Read-only.** Never click, type, or modify the WordPress site.
- **Evidence-based.** Every result references a DOM value, network response, or
  screenshot. No "looks fine."
- **Non-blocking.** Failed validation produces a report; does not revert uploads.
- **Severity**: BLOCKER (broken content), WARNING (degraded but functional),
  INFO (informational).
- Requires Playwright MCP or Chrome DevTools MCP. If neither available, skip.

### Phase 1: NAVIGATE

Load `references/wordpress-phase-checks.md` for the 4-step procedure. Navigate
to URL, wait for content area (try selectors: `article` -> `.entry-content` ->
`.post-content` -> `main`), remove cookie banners.

**Gate**: HTTP 200, content selector found. If 4xx/5xx or no selector: screenshot,
FAIL, STOP.

### Phase 2: VALIDATE

Load `references/wordpress-validation-checks.md` for severity rationale and edge
cases. Load `references/wordpress-playwright-tools.md` for tool signatures.

Run all 7 checks:

| Check | Severity |
|-------|----------|
| Title match | BLOCKER |
| H2 structure | WARNING |
| Image loading | BLOCKER |
| JS console errors | WARNING |
| OG tags | WARNING |
| Meta description | WARNING |
| Placeholder/draft text | BLOCKER |

Execute each check via browser tools. Do not reason about outcomes -- run the
command and report observed results.

**Gate**: All 7 checks executed with severity and evidence.

### Phase 3: RESPONSIVE CHECK

Test three viewports: mobile (375x812), tablet (768x1024), desktop (1440x900).
Per viewport: resize, screenshot, check overflow, check container visibility.
See `references/wordpress-phase-checks.md` for JS snippets.

### Phase 4: REPORT

Output structured report:

```
LIVE VALIDATION: {url}
CONTENT INTEGRITY: [PASS/FAIL/WARN] per check with evidence
SEO / SOCIAL: OG tags, meta description with values
RESPONSIVE: per viewport with overflow status and screenshot path
RESULT: {PASS | FAIL - N blockers, M warnings}
```

### Error Handling

| Error | Response |
|-------|----------|
| Playwright MCP unavailable | Skip report, do not retry |
| 4xx/5xx | Screenshot, report HTTP status, STOP at Phase 1 |
| Content selector not found | Screenshot + DOM snapshot; attempt OG checks without selector |
| Image network timeout | Report; if all fail, note possible CDN issue |
| Cookie banner blocks content | Phase 1 attempts DOM removal; DOM checks still work |

---

## Enterprise Search

Search infrastructure: relevance tuning, query understanding, index management,
quality measurement, performance optimization. Always specify target platform
and version.

### Sub-mode Detection

| Mode | Signal | Load |
|------|--------|------|
| RELEVANCE | BM25, boost, LTR, ranking | `references/search-relevance-tuning.md` |
| QUERY | intent, entity extraction, expansion, synonyms | `references/search-query-understanding.md` |
| INDEX | schema, mapping, analyzer, reindex, ILM | `references/search-index-management.md` |
| QUALITY | nDCG, MRR, judgments, A/B test | `references/search-search-quality.md` |
| PERFORMANCE | slow query, shard, cache, circuit breaker | `references/search-performance-optimization.md` |
| ARCHITECTURE | hybrid search, vector search, platform selection | Load per sub-topic |

Always load `references/search-llm-search-failure-modes.md` as a guardrail.

### Shared Workflow Pattern

1. **Diagnose** the problem class before acting.
2. **Baseline** current metrics. No tuning without measurement.
3. **Change one variable** at a time.
4. **Validate** against baseline. Accept only statistically significant
   improvements.

### Platform Conventions

| Platform | Query Language | Config |
|----------|---------------|--------|
| Elasticsearch 8.x | Query DSL (JSON) | elasticsearch.yml |
| OpenSearch 2.x | Query DSL (JSON) | opensearch.yml |
| Solr 9.x | SolrQL / JSON Request API | solrconfig.xml |
| Vespa | YQL | services.xml |
| Typesense | REST params | CLI / JSON |

Cross-platform traps: OpenSearch diverges from ES 7.10 on security/ML/alerting.
ES `_field_caps` changed between 7.x and 8.x. Solr `edismax` != ES `multi_match`.

### Output Rules

- All query DSL in fenced blocks with platform + version annotation.
- Every recommendation: what to change, why, expected effect, how to measure.
- Configuration snippets must be copy-pasteable with comments.

---

## Deep References

Load on demand when a phase needs detailed lookup data.

| Context | Reference |
|--------|-----------|
| SAPCC Review Phase 2: 10 agent specs | `references/sapcc-review-agent-dispatch-prompts.md` |
| SAPCC Audit Phase 2: dispatch prompt | `references/sapcc-audit-phase-2-dispatch-agents.md` |
| SIGMA authoring, DSL translation, MITRE catalog | `references/opensearch-detection-engineering.md` |
| Detector failures, alias conflicts, index flood | `references/opensearch-detection-safety-patterns.md` |
| Escalation checklist, severity SLAs, KPIs | `references/opensearch-incident-escalation.md` |
| WordPress check specs, severities, edge cases | `references/wordpress-validation-checks.md` |
| WordPress Playwright tool signatures | `references/wordpress-playwright-tools.md` |
| WordPress phase procedures with JS snippets | `references/wordpress-phase-checks.md` |
| Search relevance tuning, BM25, LTR, boosts | `references/search-relevance-tuning.md` |
| Query understanding, intent, expansion | `references/search-query-understanding.md` |
| Index management, schema, analyzers, ILM | `references/search-index-management.md` |
| Search quality metrics, evaluation methodology | `references/search-search-quality.md` |
| Search performance, caching, sharding | `references/search-performance-optimization.md` |
| LLM failure modes in search engineering | `references/search-llm-search-failure-modes.md` |
