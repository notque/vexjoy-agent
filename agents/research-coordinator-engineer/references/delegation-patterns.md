# Delegation Patterns Reference

> **Scope**: Subagent instruction templates and parallel execution strategy for research-coordinator-engineer. Covers instruction structure, parallel deployment mechanics, and scope boundary enforcement.
> **Version range**: Claude Code SDK (Task tool / Agent tool)
> **Generated**: 2026-04-13 — verify Task tool parameter names against current SDK

---

## Overview

Delegation quality is the single largest variable in research output quality. Vague instructions produce vague results — the coordinator owns the quality of its instructions, not the subagent. Every instruction must specify a deliverable format, explicit scope boundaries (IN and OUT), and source guidance. Parallel deployment via a single message is mandatory for independent research streams.

---

## Pattern Table

| Pattern | Use When | Subagent Count | Instruction Length |
|---------|----------|---------------|-------------------|
| Standard parallel dispatch | Medium complexity, 3+ independent streams | 3 | 100-200 words each |
| Deep-dive single stream | Narrow topic needing full depth | 1–2 | 200-300 words |
| Broad coverage dispatch | Comparison or enumeration query | 1 per item, max 7 | 80-150 words each |
| Fallback sequential | Dependencies between streams | 1 at a time | Full detail each |

---

## Correct Patterns

### Standard Parallel Dispatch (3 Concurrent)

Deploy all independent subagents in a single message. The Task tool calls must appear together — sequential dispatch wastes time equal to N×latency instead of 1×latency.

```python
# Deploy all 3 in one message — NOT in separate messages
Task(
    subject="Research GPU availability 2025-2030",
    content="""Research compute availability for AI in 2025-2030:
    - Focus on GPU/TPU availability from major cloud providers (AWS, GCP, Azure)
    - Include chip production forecasts from TSMC, Samsung, Intel Foundry
    - Analyze supply chain constraints: ASML EUV equipment, packaging bottlenecks
    SCOPE: Only compute chips and cloud capacity. NOT general semiconductor market.
    DELIVERABLE: 350-500 word summary with at least 3 specific statistics.
    SOURCES: Cloud provider capacity reports, semiconductor analyst reports (2024-2025)."""
)

Task(
    subject="Research energy requirements for AI data centers",
    content="""Research energy/power requirements for large-scale AI training and inference:
    - Power consumption per GPU cluster for current frontier models
    - Grid capacity constraints in major data center regions
    - Cooling technology advances (liquid cooling, direct-to-chip)
    SCOPE: Energy for AI compute only. NOT general data center energy trends.
    DELIVERABLE: 350-500 word summary with at least 3 specific statistics.
    SOURCES: IEA reports, data center operator publications, academic papers (2024-2025)."""
)

Task(
    subject="Research regulatory environment for AI infrastructure",
    content="""Research regulatory constraints affecting AI infrastructure buildout:
    - Permitting timelines for large data centers (US, EU)
    - Environmental review requirements for power consumption
    - Export controls affecting chip availability (BIS regulations)
    SCOPE: Regulations directly affecting infrastructure build. NOT AI product regulation.
    DELIVERABLE: 350-500 word summary with specific jurisdictions and timelines.
    SOURCES: Federal Register, EU legislation, news coverage of regulatory cases (2024-2025)."""
)
```

**Why**: Single-message dispatch lets all three subagents execute concurrently. Sequential dispatch serializes them — the second waits for the first, tripling total wall time.

---

### Instruction Required Components

Every subagent instruction must include all five components. Missing any one degrades output quality.

```markdown
[1] SCOPE STATEMENT
Research GPU compute availability for AI workloads 2025-2030.
(What is IN scope — one sentence, specific)

[2] EXPLICIT OUT-OF-SCOPE
Do NOT cover general semiconductor market, consumer GPU pricing, or gaming hardware.
(What to ignore — prevents scope creep that makes synthesis harder)

[3] REQUIRED DATA POINTS
Include: cloud provider capacity figures, TSMC production volume forecasts, HBM3 supply.
(Forces subagent to seek concrete data, not just narrative)

[4] DELIVERABLE FORMAT
Deliverable: 350-500 word summary with minimum 3 statistics including source + date.
(Word count + format expectation + quality bar)

[5] SOURCE GUIDANCE
Sources: Cloud provider investor reports, IDC forecasts, semiconductor analyst reports.
Prefer: Primary sources over aggregators. Prioritize 2024-2025 over older.
(Directs where to look, prevents citation of low-quality sources)
```

---

### Adaptive Instruction After Initial Findings (Bayesian Update)

When Wave 1 subagents reveal unexpected gaps or conflicts, Wave 2 instructions must address them explicitly.

```markdown
# Wave 1 finding: GPU supply data is well-covered but energy data is sparse
# Wave 2 instruction adjusted to fill gap:

Research AI data center energy consumption with focus on ACTUAL METERED DATA:
- Find published case studies from hyperscalers with metered power figures
- Specifically seek: Google sustainability reports, Microsoft datacenter PUE data
- Avoid: Estimates and projections — only measured/reported figures
- Gap from Wave 1: Initial research found projections but no verified metered data
DELIVERABLE: List of 5+ specific measured data points with source, date, and URL.
```

**Why**: Bayesian adaptation prevents Wave 2 from duplicating Wave 1 findings and directs effort to actual gaps.

---

## Anti-Pattern Catalog

### ❌ Vague Scope Without Boundaries

**Detection**:
```bash
# Check instruction files for scope boundary markers
grep -rL "Do NOT\|OUT OF SCOPE\|Not in scope\|Exclude" research/*/instructions/ 2>/dev/null
# Check for dangerously short instructions (under 50 words)
awk 'NF>0{count+=NF} END{if(count<50) print FILENAME": too short ("count" words)"}' research/*/instructions/*.md 2>/dev/null
```

**What it looks like**:
```markdown
Subagent 1: "Research AI trends in 2025."
```

**Why wrong**: No scope = no boundary = subagent expands to cover everything tangentially related to AI. The coordinator receives a 1000-word survey that overlaps with what the other two subagents produced. Synthesis degrades to picking the best paragraph from each, not integrating distinct findings.

**Fix**:
```markdown
Subagent 1: "Research AI model training compute trends for frontier models (GPT-4 class and above)
in 2024-2025. Focus on: training run sizes in FLOP, hardware configurations, cost estimates.
Do NOT cover inference, edge AI, or models below 10B parameters.
DELIVERABLE: 300-400 words with at least 2 specific training run statistics."
```

---

### ❌ Sequential Dispatch of Independent Streams

**Detection**:
```bash
# In research plans or transcripts, look for "wait for" or "after X completes"
grep -i "wait for\|after.*completes\|once.*done\|then deploy" research/*/plan.md
# Look for single Task calls in plan when query is medium+ complexity
grep -c "Task\|TaskCreate\|subagent" research/*/plan.md
```

**What it looks like**:
```markdown
# Plan:
1. Deploy subagent to research GPU supply
2. WAIT for result
3. Deploy subagent to research energy requirements
4. WAIT for result
5. Deploy subagent to research regulation
```

**Why wrong**: These three topics are independent — none requires the GPU supply finding to start the energy research. Sequential deployment triples latency for no reason. On a 60-second subagent, sequential = 180 seconds; parallel = 60 seconds.

**Fix**: Move all three Task calls into a single message. Only use sequential deployment when Stream B genuinely requires Stream A's output as an input.

---

### ❌ Missing Deliverable Format Specification

**Detection**:
```bash
# Check if instructions specify word count or format
grep -rL "word\|paragraph\|bullet\|table\|summary" research/*/instructions/ 2>/dev/null
```

**What it looks like**:
```markdown
"Research the regulatory landscape for AI development and provide your findings."
```

**Why wrong**: Subagent may return a 50-word paragraph or a 1500-word essay. Lead agent cannot predict what arrives, making synthesis planning impossible. It also removes the quality bar — "provide your findings" accepts any output as correct.

**Fix**: Add explicit format: "DELIVERABLE: 300-500 word structured summary with: (1) current status, (2) key restrictions, (3) timeline outlook. No citations in body."

---

## Error-Fix Mappings

| Error Symptom | Root Cause | Fix |
|---------------|------------|-----|
| Subagents return overlapping content | No scope differentiation or no OUT-OF-SCOPE clauses | Add explicit OUT-OF-SCOPE to every instruction |
| One subagent returns 100 words, another 1000 | No word count specification | Add word count range to every instruction |
| Subagent drifts to adjacent topic | Scope statement positive-only (no exclusions) | Add "Do NOT cover X" clause |
| Synthesis takes longer than research | Findings in incompatible formats | Standardize deliverable format across parallel instructions |
| Wave 2 duplicates Wave 1 findings | No Bayesian update in Wave 2 instructions | Reference Wave 1 gaps explicitly in Wave 2 scope |
| Subagent count exceeds 20 | Over-scoped query without restructuring | Merge adjacent topics into single subagent or reduce scope |

---

## Subagent Count Decision Tree

```
Query complexity?
├── Simple (single data point) → 1 subagent, tight instructions
├── Medium (3-5 independent streams) → 3 concurrent subagents
├── Complex (6-10 independent streams) → 5-7 concurrent, group by theme
└── Very complex (>10 streams needed) → STOP: restructure query or reduce scope first
                                         Hard limit: 20 subagents total
```

---

## Detection Commands Reference

```bash
# Find instructions missing OUT-OF-SCOPE clauses
grep -rL "Do NOT\|OUT OF SCOPE\|Exclude" research/*/instructions/ 2>/dev/null

# Find instructions under 50 words (likely too vague)
find research/ -name "*.md" -path "*/instructions/*" -exec \
  awk 'NF{w+=NF} END{if(w<50)print FILENAME": "w" words"}' {} \; 2>/dev/null

# Detect sequential dispatch plans
grep -in "wait for\|step [0-9]\+: deploy" research/*/plan.md 2>/dev/null

# Verify all parallel streams have matching deliverable specs
grep -h "DELIVERABLE\|word\|format" research/*/instructions/*.md 2>/dev/null | sort | uniq -c
```

---

## See Also

- `query-classification.md` — Determines subagent count and instruction style before this step
- `error-catalog.md` — Common delegation failures and their resolution
