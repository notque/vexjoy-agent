---
name: review
description: "Review a file, diff, PR, or bounded repository scope for evidence-backed correctness and maintainability findings."
user-invocable: true
allowed-tools: [Read, Write, Bash, Grep, Glob, Edit, Task, Agent]
routing:
  force_route: true
  not_for: "security-only audits (use security), linting (use code-quality), git push/commit/PR lifecycle (use pr-workflow)"
  triggers: [review code, code review, code review methodology, structured review, code audit, comprehensive review, parallel review, multi-reviewer, full repo review, codebase audit, repo health, review this PR, review my PR, PR review, diff review]
  category: code-review
  pairs_with: [security, testing]
---

# Review

Default to one systematic reviewer. Use parallel security/business-logic/architecture perspectives only when requested or when the scope is genuinely cross-cutting. A repository audit is a bounded inventory and prioritized backlog, never an implicit fix authorization.

Read repository instructions, the complete diff or named files, and enough surrounding code to understand changed behavior. When contracts change, find callers, implementations, registries, serializers, and tests. Trace untrusted inputs to their source rather than inferring trust from a variable name.

Run relevant project checks. A missing tool, skipped test, stale result, or incomplete scope is a limitation, not a pass. Before reporting a candidate finding, reproduce its input/state sequence, inspect existing guards, cite the consequence, and verify that the proposed fix addresses it. Drop unreachable, pre-existing-out-of-scope, speculative, and duplicate claims.

Severity follows demonstrated impact:

- `BLOCKING`: exploitable security, correctness, data-loss, reliability, or compatibility defect that should prevent merge.
- `SHOULD FIX`: material test, performance, design, or maintainability issue with a concrete future cost.
- `SUGGESTION`: optional improvement with no material defect.

Any BLOCKING finding yields REQUEST-CHANGES. SHOULD FIX without BLOCKING yields FIX. Suggestions-only or clean yields APPROVE only when coverage is complete; otherwise NEEDS-DISCUSSION.

Report reviewed revision/scope, checks actually run, findings ordered by severity with `file:line`, evidence, consequence, and targeted fix, followed by limitations and verdict. Empty severity sections add no value. Validate compatible reports when the repository helper exists:

```bash
python3 scripts/validate-review-output.py --type systematic /tmp/review-output.md
```

For parallel review, dispatch all perspectives read-only, state missing coverage, and deduplicate by evidence rather than vote count. For a repository-wide request, enumerate all source scopes explicitly and split by directory when needed; never substitute `git diff` for the requested inventory.
