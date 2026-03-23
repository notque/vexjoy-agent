# Phase 5 Evaluation Guide

Guide for generating evaluation Q&A pairs and running the evaluation harness against the compiled MCP server.

---

## Q&A Pair Requirements

Every evaluation question must satisfy all four criteria:

| Criterion | Why It Matters | How to Verify |
|-----------|----------------|---------------|
| **Read-only** | Evaluation must not modify the target service's state | Question only retrieves; it does not create, update, or delete |
| **Independently verifiable** | Answers must be checkable without running other tools first | The answer is derivable from a single tool call |
| **Stable** | The same question must produce the same answer across multiple runs | Answer does not depend on time, random data, or mutable state |
| **Specific** | Vague questions produce vague answers that are hard to score | Question names a specific entity or uses a specific identifier |

### What Makes a Good Q&A Pair

Good: "What is the description of the issue with number 42 in the octocat/hello-world repository?"
- Read-only: yes (GET operation)
- Verifiable: yes (single tool call: `github_get_issue`)
- Stable: yes (issue descriptions don't change)
- Specific: yes (named repository, named issue number)

Bad: "What are some recent issues?"
- Read-only: yes
- Verifiable: no (depends on what "recent" means today)
- Stable: no (changes as new issues are created)
- Specific: no (ambiguous)

---

## Q&A Generation Heuristic

**2 Q&A pairs per major entity type** from `analysis.md` → Entities section.

For each entity type:
1. One question that fetches a specific instance (get by ID)
2. One question that lists instances with a filter (list with state, type, or label)

If the analysis identified only a few entity types and 2×N < 10, add:
- One question per available filter parameter
- One question about metadata (e.g., "How many open issues are there?")

---

## Q&A Pair Format

Each pair is a JSON object:

```json
{
  "question": "What is the title of issue number 1 in the github/github repository?",
  "expected_answer_contains": "Hello World",
  "tool_hints": ["github_get_issue"],
  "category": "get_single",
  "entity_type": "issue"
}
```

Fields:
- `question` (string): The question to send to Claude
- `expected_answer_contains` (string): A substring that must appear in the correct answer. Use a distinctive substring, not the full response.
- `tool_hints` (array of strings): Which tool(s) are expected to be called. Used for tool call count analysis.
- `category` (string): `get_single` | `list_filtered` | `search` | `metadata`
- `entity_type` (string): The entity type being queried (from analysis.md Entities section)

---

## Evaluation Harness Design

The harness runs each Q&A pair against the live server over stdio transport.

### Step 1: Launch Server

```bash
# TypeScript
node {absolute-path-to-dist/index.js}

# Python
python3 {absolute-path-to-src/main.py}
```

Launch as a subprocess with stdio pipes. Set environment variables (API keys) from the server's README.

### Step 2: MCP Handshake

Send the MCP initialize request:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": { "sampling": {} },
    "clientInfo": { "name": "eval-harness", "version": "0.1.0" }
  }
}
```

Wait for the `initialize` response, then send `notifications/initialized`.

### Step 3: For Each Q&A Pair

Use the MCP `sampling/createMessage` method to send the question to the server, or invoke the relevant tool directly using `tools/call`.

**Direct tool invocation approach** (more reliable for evaluation):
1. Send `tools/list` to discover available tools
2. Based on `tool_hints`, send `tools/call` with appropriate parameters derived from the question
3. Capture the response content

**Claude-mediated approach** (tests full tool selection):
1. Send a `sampling/createMessage` request with the question text
2. Let Claude select and call the appropriate tool
3. Capture the final response

The direct invocation approach is preferred for mechanical evaluation because it removes the model selection step as a variable.

### Step 4: Score Response

Compare the response content to `expected_answer_contains`:

| Result | Score | Condition |
|--------|-------|-----------|
| Exact match | 1.0 | Response contains `expected_answer_contains` exactly |
| Partial match | 0.5 | Response contains key terms from `expected_answer_contains` but not the full string |
| Wrong | 0.0 | Response does not contain expected content |
| Error | 0.0 | Tool call returned an error or server crashed |
| Timeout | 0.0 | No response within 30 seconds |

### Step 5: Collect Metrics

Per question:
- Score (0.0, 0.5, or 1.0)
- Tool(s) actually called (from MCP protocol messages)
- Time from question to response (milliseconds)
- Whether the response was an error

### Step 6: Shut Down Server

Send `exit` notification or kill the subprocess after all questions complete.

---

## Evaluation Report Format

Write to `mcp-design/{repo-slug}/evaluation-report.md`:

```markdown
# Evaluation Report: {Server Name}

**Date**: {ISO date}
**Server**: {server-name}
**Target repo**: {repo URL or path}
**Total questions**: 10
**Accuracy**: {N}/10 ({percentage}%)

## Result: {PASS | FAIL — REGENERATION TRIGGERED | FAIL — PIPELINE HALTED}

---

## Per-Question Results

| # | Question | Expected Contains | Score | Tools Called | Time (ms) |
|---|----------|------------------|-------|--------------|-----------|
| 1 | {question text truncated to 60 chars} | {expected snippet} | {score} | {tool_name} | {ms} |
| 2 | ... | ... | ... | ... | ... |

---

## Tool Call Summary

| Tool | Times Called | Avg Time (ms) |
|------|-------------|---------------|
| {tool_name} | {N} | {ms} |

---

## Failures Analysis

{For each question that scored 0 or 0.5: explain what went wrong}

### Question {N}: {Question text}
- Expected: {expected_answer_contains}
- Got: {actual response excerpt}
- Likely cause: {tool description mismatch | wrong parameter schema | missing data | timeout}

---

## Recommendations

{If accuracy < 7/10: specific suggestions for which tools to fix and how}
```

---

## Accuracy Gate

| Accuracy | Action |
|----------|--------|
| **≥ 7/10** | Proceed to Phase 6 (REGISTER) |
| **< 7/10 (first attempt)** | Trigger one Phase 3 regeneration with failure analysis. Re-run Phase 4 and Phase 5. |
| **< 7/10 (second attempt)** | Halt. Surface the evaluation report. Tell the user which tools are failing and why. Do NOT attempt a third regeneration. |

### Regeneration Guidance

When triggering a Phase 3 regeneration due to evaluation failure, provide the GENERATE phase with:

1. The evaluation report (which questions failed)
2. The failure analysis (what the model returned vs what was expected)
3. Targeted guidance: "The `{tool_name}` tool is returning {X} but should return {Y}. Fix the tool description, response format, or implementation."

The regeneration should be **targeted** — fix the failing tools, not rewrite everything.

---

## Common Evaluation Failure Patterns

| Pattern | Likely Cause | Fix Direction |
|---------|-------------|---------------|
| All questions fail with "Error" | Server crashes on startup | Check auth env vars; fix startup validation |
| Tool calls succeed but answers are wrong format | Tool returns raw JSON; question expects prose | Fix tool to format response for readability |
| Expected substring not found (substring is accurate) | Tool returns partial data | Fix tool to include complete entity fields |
| Timeouts on every question | Server hangs waiting for API | Check network access; add timeout to client |
| Wrong tool called | Tool description is ambiguous | Rewrite tool description to be more specific |
