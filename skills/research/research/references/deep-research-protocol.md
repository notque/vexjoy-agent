# Deep research protocol

Companion protocol to `references/research-coordinator/` for broad, multi-source, or open-ended web investigations. Use it to size subagent budgets, route full-page reads, stop stalled tracks, and format concise reports.

## Orient and budget

1. If the user's scope is ambiguous, ask one targeted clarifying question before dispatching workers. If the request is clear, start without delay.
2. When the subject area is unfamiliar, run one quick search first to map key terms, primary sources, and major actors before decomposing the work.
3. Size the dispatch to the request shape and model speed:

| Request shape | Subagent budget | Execution approach |
|---------------|-----------------|--------------------|
| Narrow or single-fact lookup | 0 to 2 | Answer directly or dispatch 1 to 2 focused lookups |
| Broad topic, survey, or comparison | 3 to 5 non-overlapping sub-questions | Dispatch concurrent workers with distinct angles |
| Broad topic on slow or high-thinking models | Cap at 2 to 3 sub-questions | Widen each track's scope to keep end-to-end latency bounded |

## Parallel gather and tool routing

Give each worker a distinct angle, time frame, source scope, and a hard cap of **8 to 12 web searches or tool steps**.

| Track need | Tool route | Notes |
|------------|------------|-------|
| Public web docs, papers, filings, releases | Concurrent `research` subagents | Dispatch independent tracks in one parallel turn |
| Live dashboards, JS-rendered pages, authenticated portals | `browser` subagent or browser tools | Use when `WebFetch` returns incomplete markup or login walls |
| Runtime without subagent tools | Direct sequential execution in main thread | Apply the same 8 to 12 step cap per track |

Worker prompt checklist:
- **Angle:** The exact sub-question and what stays out of scope.
- **Time frame:** Relevant date window or cutoff (for example, 2024 to 2026).
- **Source scope:** Preferred primary sources (official docs, filings, repos, benchmarks).
- **Step budget:** Explicit 8 to 12 search or tool-call ceiling and early-exit instruction.

## Primary evidence and budget exit

1. Verify material claims against primary sources (official specifications, filings, source repositories, raw benchmarks, transcripts) instead of relying on search snippets or secondary summaries.
2. Capture exact quotes, figures, dates, or raw command outputs for key numbers so synthesis can cite them verbatim.
3. When a worker reaches its 8 to 12 step cap before resolving every question, stop searching immediately and return all partial verified findings alongside an explicit list of remaining gaps. Do not loop past the budget.

## Straggler stall control and verification

1. Read worker results as they arrive instead of waiting passively for the slowest track.
2. If most subagents finish and one track stalls, cancel the stalled worker, record the missing angle as an open gap, and proceed to synthesis.
3. After reviewing initial results, run at most **one** targeted follow-up pass, and only when unresolved gaps would change the conclusion.
4. Spawn one fresh verification subagent only for high-stakes or data-heavy reports to spot-check key figures, quotes, and URLs against primary sources. Skip verification passes for routine surveys.

## Report format and delivery

Structure every report for rapid scanning:

1. **Top-line summary:** Lead with a 2-sentence answer to the core question.
2. **Findings by axis:** Group evidence by sub-question or comparison dimension. Attach inline clickable citations (`[Source Title](https://...)`) to every factual claim and number.
3. **Unresolved:** Include a brief **Unresolved** section whenever primary sources conflict, authoritative data is missing, or a canceled track left a gap. State the exact conflict or missing evidence.

Choose the output destination by environment:

- **Session with an Artifact Directory Path:** Write the full report to the session Artifact Directory Path. Keep chat output to a short pointer linking the artifact plus the key findings and open decisions.
- **Headless or CLI run without an artifact directory:** Reply directly with the formatted report, or write to `research/{topic}/report.md` when operating inside a repository research workspace.

## Attribution

Adapted from Google DemoLab's `deep-research` skill (`https://github.com/google-gemini/demolab`), licensed under Apache-2.0.
