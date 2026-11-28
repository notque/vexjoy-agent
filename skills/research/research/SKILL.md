---
name: research
description: "Research: structured investigation, deep multi-agent research, fact-checking, document-to-Markdown conversion, explanation traces."
user-invocable: true
argument-hint: "<research topic, document to convert, or claim to verify>"
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
  not_for: "code review (use review), security audit (use security)"
  triggers:
    - "research-pipeline"
    - "research"
    - "deep research"
    - "multi-agent research"
    - "broad survey"
    - "exhaustive comparison"
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
    - "research topic"
    - "multi-source analysis"
    - "investigate question"
    - "synthesize sources"
    - "comprehensive analysis"
    - "research subtask"
    - "delegated research"
    - "convert to markdown"
    - "markitdown"
    - "extract text from PDF"
    - "PDF to markdown"
    - "docx to markdown"
    - "pptx to markdown"
    - "xlsx to markdown"
  category: research
  pairs_with:
    - review
    - writing
---

# Research Skill

Four modes. Select by request signal:

| Signal | Mode |
|--------|------|
| Formal research, deep research, multi-agent research, broad survey, exhaustive comparison, investigation, sourced report, gather evidence | Research Pipeline |
| Fact check, verify claims, check facts, is this accurate, verify quote | Fact-Check |
| Why did you, explain routing, show trace, decision log, why that agent | Explanation Traces |
| Convert to Markdown, markitdown, extract text from PDF/Office/HTML/data/media/ZIP | Document-to-Markdown Conversion |

Default: Research Pipeline.

**Final report.** When the final report synthesizes two or more dispatched agents' findings, run one self-review pass on the draft before delivery: `skills/shared-patterns/report-self-review.md` (separate dispatch, `model: opus`). It applies to Mode A and Mode B.

---

## Mode A: Research Pipeline

Load `references/deep-research-protocol.md` and the coordinator guides in `references/research-coordinator/` (`query-classification.md`, `delegation-patterns.md`, `templates/`), then follow CLASSIFY -> PLAN -> EXECUTE -> SYNTHESIZE. Use `references/deep-research-protocol.md` for orient/budget sizing (0-2 narrow, 3-5 broad, capped at 2-3 on slow or high-thinking models), 8-12 step worker budgets, concurrent `research`/`browser` routing, straggler stall cancellation, one-pass follow-up limits, and concise artifact-first reporting. The coordinator runs in this thread and writes the report itself. Each research stream is a fresh `general-purpose` worker whose prompt starts: "Read ~/.claude/skills/research/references/research-subagent-executor/source-quality-assessment.md and follow it along with ~/.claude/skills/research/references/deep-research-protocol.md." Dispatch independent streams in one message; 20 workers maximum. Save the report to the session Artifact Directory Path when available, or `research/{topic}/report.md`, with every factual claim cited.

**Gate**: Every worker returned or its gap is stated in an **Unresolved** section; the report cites source and passage for each claim.

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

## Mode D: Document-to-Markdown Conversion

Load `references/markdown-converter.md` to convert PDF, Office (`.docx`, `.pptx`, `.xlsx`, `.xls`), HTML, CSV, JSON, XML, image, audio, ZIP, or EPub files into structured Markdown with `uvx 'markitdown[all]'` (or `pipx run 'markitdown[all]'` when `uvx` is absent). If a scanned PDF returns empty or garbled text, render pages to PNG with `pdftoppm` and convert the images so OCR runs. For video transcripts, route to `video-editing`.

---

## Deep References

| Signal | Reference | Content |
|--------|-----------|---------|
| Research pipeline: classify, plan, dispatch, synthesize | `references/research-coordinator/` | Query classification, worker delegation patterns, checklists, examples, and report templates |
| Deep research budgets, parallel tool routing, stall control, artifact output | `references/deep-research-protocol.md` | Orient/budget caps, 8-12 step worker limits, browser routing, straggler cancellation, 2-sentence summary + Unresolved format |
| Document-to-Markdown conversion (`markitdown`, PDF/Office/OCR) | `references/markdown-converter.md` | `uvx`/`pipx` CLI usage, supported formats, flags, scanned-PDF OCR fallback |
| Running one delegated research stream (worker) | `references/research-subagent-executor/` | Source quality assessment (`source-quality-assessment.md`) for delegated research workers |
| Event field schema, health states, join rules | `references/trace-schema.md` | DECISION/OUTCOME field semantics |
| Diagnosing thin trace data, consumer mistakes | `references/preferred-patterns.md` | Failure mode catalog for log reading |
| Parse/read errors, missing log, unmatched outcomes | `references/error-handling.md` | Error-fix mappings for trace reading |
