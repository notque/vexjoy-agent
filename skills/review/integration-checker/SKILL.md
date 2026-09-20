---
name: integration-checker
description: "Verify that changed components are reachable, receive real data, and agree on contracts."
user-invocable: false
command: /integration-checker
allowed-tools: [Read, Bash, Grep, Glob]
routing:
  triggers: [integration check, check integration, verify wiring, are components connected, check connections, integration-checker, wiring check]
  pairs_with: [workflow, review]
  complexity: Medium
  category: process
---

# Integration Checker

Read-only. Scope to the requested connection or changed implementation; trace affected producers and consumers outside the diff. Missing implementation artifacts or source are coverage gaps and prevent PASS.

For each public component, distinguish:

- `WIRED`: a consumer imports/registers it and executes it.
- `IMPORTED_NOT_USED`: present at the import boundary but never consumed.
- `ORPHANED`: no visible consumer after excluding documented public APIs, framework/plugin registration, generated code, test-only exports, reflection, and external consumers.

An import alone is not wiring. Follow WIRED paths from entry point through real inputs. Flag placeholder/empty data, dead parameters, mock returns, producer-consumer shape/type/nullability differences, mismatched event names, circular-import failures, and missing registration. Static matches in dynamic/reflection-heavy systems are uncertain; label confidence and use runtime evidence when available.

In feature-pipeline mode, map each requirement as WIRED, PARTIAL, or UNWIRED from entry point to implementation. Compute `100 * WIRED / (WIRED + IMPORTED_NOT_USED + ORPHANED)`, or N/A for a zero denominator.

PASS requires complete scoped coverage and no issue. WARN is limited to unused imports or low-confidence contract concerns. Orphaned components, broken flow, or high-confidence mismatches FAIL. Report `file:line` evidence and recheck affected connections after fixes.
