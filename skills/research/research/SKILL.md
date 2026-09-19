---
name: research
description: "Research: structured investigation, fact-checking, explanation traces."
user-invocable: true
argument-hint: "<research topic or claim to verify>"
agent: research-coordinator-engineer
context: fork
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
  - Agent
  - Write
  - WebFetch
  - WebSearch
routing:
  force_route: true
  not_for: "code review (use review), security audit (use security)"
  triggers:
    - "research-pipeline"
    - "research"
    - "formal research"
    - "research with artifacts"
    - "systematic investigation"
    - "research report"
    - "gather evidence"
    - "fact check"
    - "fact-check"
    - "verify claims"
    - "check facts"
    - "verify this quote"
    - "is this accurate"
    - "is this true"
    - "check this claim"
    - "verify this"
    - "are these numbers right"
    - "why did you"
    - "explain routing"
    - "show trace"
    - "decision log"
    - "why that agent"
    - "explain decision"
    - "show decisions"
    - "trace log"
  category: research
  pairs_with:
    - review
    - writing
---

# Research Skill

Three modes. Select by request signal:

| Signal | Mode |
|--------|------|
| Formal research, investigation, sourced report, gather evidence | Research Pipeline |
| Fact check, verify claims, check facts, is this accurate, verify quote | Fact-Check |
| Why did you, explain routing, show trace, decision log, why that agent | Explanation Traces |

Default: Research Pipeline.

---

## Mode A: Research Pipeline


---

## Mode B: Fact-Check

Verify every factual claim in a draft before publish. Burden of proof sits on the claim, not the checker. Works standalone or as a pre-publish gate. Non-blocking: the report warns; the caller decides whether to publish.

### Phase 1: EXTRACT

List every checkable claim: statistics, prices, dates, quotes, attributions, titles, event facts, rankings, causal assertions. Opinions and speculation stay out.

For each claim, record: ID, verbatim text, type (stat/quote/attribution/event/title/price/causal), location. Extract quotes verbatim for exact-words comparison.

**Gate**: Every checkable assertion has a claim ID. Sweep the document twice.

### Phase 2: VERIFY

Work claim by claim.

1. **Check provided sources first.** Search caller-supplied documents before external sources. Record exact passages.
2. **Read laterally.** Judge a source by what other sources say about it, not by its own presentation.
3. **Climb the source tier.** Follow citations upward: primary (study, filing, transcript) > direct secondary (interviews, primary reading) > derived (aggregators, rewrites). A broken citation chain caps the claim at Unverifiable.
4. **Triangulate contested claims.** Two independent sources (separate origins, not wire rewrites). One source suffices for routine facts from a primary document.
5. **Verify quotes on three axes.** All must hold: exact words match, attributed speaker confirmed, original context supports the meaning used.
6. **Check staleness.** Time-sensitive claims expire. Prices/rates: 1 day-1 week. Counts: 1-3 months. Titles/roles: 3-6 months. Event status: until event date. Surveys: 6-12 months. Science: 1-3 years. Laws: 6-12 months. Records/superlatives: re-check every use. Stable history: none.

**Gate**: Every claim has an evidence record.

### Phase 3: ADJUDICATE

Assign each claim one label:

| Label | Assign when |
|-------|-------------|
| **Verified** | Evidence supports; current within staleness window; sufficient source tier |
| **Disputed** | Evidence contradicts; newer source supersedes; quote fails any axis |
| **Unverifiable** | Sources engage the claim but settle nothing |
| **Missing-source** | No available source addresses it |

Rules: contradiction beats support. Partial verification gets the weakest label. Stale figure superseded by newer = Disputed; merely old with no newer figure = Unverifiable.

**Gate**: Every claim carries one label and a one-line justification.

### Phase 4: REPORT

```
# Fact-Check Report: [document]
## Summary
Claims: N | Verified: n | Disputed: n | Unverifiable: n | Missing-source: n
Unchecked: n (reason)
## Per-Claim Findings
### C1 -- [label]
Claim: [text] | Evidence: [source + passage] | Reasoning: [why this label]
## Warnings
[Every Disputed/Missing-source claim with correction]
## Publish Recommendation
[Hold / fix-then-publish / clear]
```

Every time-sensitive Verified claim carries its as-of date.

**Gate**: Report covers every claim ID. Warnings lists every Disputed and Missing-source finding.

---

## Mode C: Explanation Traces

Read the per-dispatch route event log and present routing decisions as a human-readable timeline. Answer "why did I get routed here?" from recorded events only -- never from reconstruction or rationalization.

**Log path**: `${CLAUDE_LEARNING_DIR:-$HOME/.claude/learning}/route-events.jsonl` (append-only JSONL).

### Phase 1: LOCATE

```bash
LOG="${CLAUDE_LEARNING_DIR:-$HOME/.claude/learning}/route-events.jsonl"
wc -l "$LOG"
```

If absent or empty, report the path and the producing hook (`hooks/routing-decision-recorder.py`). Do not reconstruct from memory.

### Phase 2: PARSE

Parse each JSON line. Two event types: DECISION (one per /do-routed dispatch) and OUTCOME (one per finalized dispatch). See `references/trace-schema.md` for full field semantics.

Filter to the user's query:

| User signal | Filter |
|-------------|--------|
| Names an agent or skill | DECISION/OUTCOME events matching that name |
| "Why routed here" / latest | Most recent DECISION, current session first |
| Outcome question | OUTCOME events, joined to decisions |
| No specific target | Chronological timeline, most recent session |

Join OUTCOME to DECISION on same `session` AND `key == "{agent}:{skill}"`. File adjacency is unreliable.

### Phase 3: PRESENT

Sort by `ts`. For each decision, show: time, agent+skill, complexity, request snippet, health at decision (three states: numeric, no-weight-row, legacy), alternates, outcome.

Lead with the answer to the user's specific question, then offer surrounding context. Flag gaps honestly: pre-instrumentation entries, unmatched outcomes.

`request_snippet` is private session data: show to the session's user, keep out of PR bodies, issues, exports.

---

## Deep References

| Signal | Reference | Content |
|--------|-----------|---------|
| Event field schema, health states, join rules | `references/trace-schema.md` | DECISION/OUTCOME field semantics |
| Diagnosing thin trace data, consumer mistakes | `references/preferred-patterns.md` | Failure mode catalog for log reading |
| Parse/read errors, missing log, unmatched outcomes | `references/error-handling.md` | Error-fix mappings for trace reading |
