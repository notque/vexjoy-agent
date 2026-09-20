---
name: research
description: "Produce sourced investigations, claim-level fact checks, or faithful explanations of recorded routing events."
user-invocable: true
argument-hint: "<research topic or claim to verify>"
agent: research-coordinator-engineer
context: fork
allowed-tools: [Read, Bash, Glob, Grep, Agent, Write, WebFetch, WebSearch]
routing:
  force_route: true
  not_for: "code review (use review), security audit (use security)"
  triggers: [research-pipeline, research, formal research, research with artifacts, systematic investigation, research report, gather evidence, fact check, fact-check, verify claims, check facts, verify this quote, is this accurate, is this true, check this claim, verify this, are these numbers right, why did you, explain routing, show trace, decision log, why that agent, explain decision, show decisions, trace log]
  category: research
  pairs_with: [review, writing]
---

# Research

Choose investigation, fact-check, or explanation trace from the request.

## Investigation

Define the question, decision it informs, date boundary, and evidence needed. Search supplied/local material first, then primary sources and direct records; use secondary sources for context or discovery. Maintain a claim ledger linking each material statement to source URL/path, exact supporting passage or data field, publication/event date, and limitations. Distinguish independent origins from syndication. Seek disconfirming evidence and reconcile conflicts explicitly. Deliver the answer first, then findings, uncertainty, and citations. Never cite a search snippet as evidence or imply that an inaccessible source was read.

## Fact-check

Extract every checkable statistic, date, price, quote, attribution, title, event, ranking, and causal claim verbatim. For each claim, record supplied-source evidence before external evidence and climb citations toward the primary record. One primary source can settle a routine fact; contested claims need two independent origins.

Quotes pass only when exact words, speaker, and original context all match. Time-sensitive claims include an as-of date. Label each claim:

- `Verified`: current evidence directly supports the whole claim.
- `Disputed`: contradictory or superseding evidence, or any failed quote axis.
- `Unverifiable`: relevant sources do not settle it, including stale evidence without a replacement.
- `Missing-source`: no available source addresses it.

Contradiction beats support; a partially supported compound claim takes its weakest label. Report every claim ID and evidence; list every Disputed and Missing-source claim in publish warnings.

## Explanation traces

Use only `${CLAUDE_LEARNING_DIR:-$HOME/.claude/learning}/route-events.jsonl`; when absent, name the path and producing hook rather than reconstructing events. Read `references/trace-schema.md` for event and privacy rules. Filter to the requested session/component, join outcomes to decisions on both session and `{agent}:{skill}`, sort by `ts`, and distinguish numeric health, instrumented no-row, and legacy/missing instrumentation. `request_snippet` may be shown to the session user but stays out of PRs, issues, and exports.
