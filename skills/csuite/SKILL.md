---
name: csuite
description: "C-suite executive decision support: strategy, technology, growth, competitive intelligence, project evaluation."
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
routing:
  triggers:
    # Strategy/CEO
    - "should I"
    - "should we"
    - "evaluate opportunity"
    - "decision"
    - "trade-off"
    - "worth it"
    - "invest in"
    - "strategy"
    - "strategic"
    # Technology/CTO
    - "build or buy"
    - "build vs buy"
    - "vendor evaluation"
    - "adopt"
    - "SaaS vs"
    - "technology choice"
    - "tech stack"
    - "architecture decision"
    - "should we use"
    # Growth/CMO
    - "grow audience"
    - "content strategy"
    - "marketing"
    - "SEO strategy"
    - "growth"
    - "brand"
    - "positioning"
    - "community building"
    # Competitive
    - "competitor"
    - "competition"
    - "market landscape"
    - "competitive analysis"
    - "differentiation"
    # Evaluation
    - "feasibility"
    - "is it worth"
    - "effort estimate"
    - "ROI"
    - "priority"
    - "should we start"
    - "project evaluation"
    - "go no go"
    - "viability"
  pairs_with: []
  complexity: Medium
  category: decision-support
---

# C-Suite Decision Support

Umbrella skill for executive decision-making: CEO strategy, CTO technology choices, CMO growth planning, competitive intelligence, and project evaluation. Each domain loads its own reference files on demand -- detect mode, load references, execute framework.

**Scope**: Business decisions with meaningful consequences. Use decision-helper for technical micro-choices, domain agents for code, voice-writer for content, systematic-debugging for debugging.

---

## Mode Detection

Classify the request into exactly one mode before proceeding. If multi-mode, choose primary and note secondary.

| Mode | Signal Phrases | Role Lens |
|------|---------------|-----------|
| **STRATEGY** | Market entry, partnerships, resource allocation, opportunity, "should I/we", pivots, investment | CEO |
| **TECHNOLOGY** | Build vs buy, vendor, SaaS, tech stack, architecture, adopt | CTO |
| **GROWTH** | Content strategy, audience, SEO, marketing, brand, community, positioning, channel | CMO |
| **COMPETITIVE** | Competitor, competition, market landscape, differentiation, market share | Cross-role |
| **EVALUATION** | Feasibility, effort estimate, ROI, priority, go/no-go, viability | Cross-role |

---

## Reference Loading Table

Load only the references required by the detected mode.

| Signal | Mode | Reference |
|--------|------|-----------|
| Market entry, partnerships, resource allocation, opportunity | STRATEGY | `references/strategic-frameworks.md`, `references/decision-matrices.md` |
| Build vs buy, vendor, SaaS, tech stack, architecture | TECHNOLOGY | `references/tco-framework.md`, `references/vendor-evaluation.md` |
| Content, audience, SEO, marketing, brand, community | GROWTH | `references/audience-segmentation.md`, `references/channel-evaluation.md` |
| Competitor, market landscape, positioning, differentiation | COMPETITIVE | `references/competitive-mapping.md`, `references/market-positioning.md` |
| Feasibility, effort, ROI, priority, go/no-go | EVALUATION | `references/feasibility-scoring.md`, `references/roi-frameworks.md` |

---

## Instructions

### Mode: STRATEGY (CEO)

**Framework**: FRAME -> ANALYZE -> DECIDE

**Phase 1: FRAME** -- Convert the question into a structured decision with clear stakes and timeline.

- Name the actual decision (users present symptoms; the real decision is broader)
- Identify irreversibility -- reversible decisions deserve less analysis
- Set time horizon -- 3-month and 3-year decisions need different frameworks
- Classify: Expansion, Partnership, Allocation, Pivot, or Timing
- Get the user to state: options (2-4), default path risk, deadline, what makes it hard

**Gate**: Decision framed as one sentence. Options listed (2-4). Type classified.

**Phase 2: ANALYZE** -- Evaluate each option with evidence.

For each option: Upside (best realistic + expected), Downside (worst realistic + recovery + irreversible losses), Requirements (resources, assumptions, dependencies), Opportunity Cost (what you cannot do).

Separate facts from assumptions. Quantify where possible. Load reference files for scoring matrices.

**Gate**: All options analyzed. Facts and assumptions labeled. Opportunity costs explicit.

**Phase 3: DECIDE** -- Synthesize into a clear recommendation.

- Reversibility test: one-way doors need high confidence; two-way doors can act faster with a checkpoint
- Produce: Recommendation (one sentence), Confidence (High/Medium/Low), Why this option (2-3 reasons), What must be true (invalidating assumptions), First move (48-hour action), Revisit trigger
- State what would change the recommendation

**Gate**: Recommendation stated. First action identified. Revisit trigger set.

---

### Mode: TECHNOLOGY (CTO)

**Framework**: SCOPE -> EVALUATE -> RECOMMEND

**Phase 1: SCOPE** -- Define the capability needed, stripped of solution bias.

- Start with the need, not the product ("reliable async delivery" not "Kafka")
- Quantify hard requirements (latency, throughput, compliance)
- Identify the real driver (sometimes "convince management" or "hire someone")
- List options: build from scratch, build on OSS, buy SaaS, buy + customize, do nothing

**Gate**: Capability defined without solution bias. Options enumerated. Hard requirements quantified.

**Phase 2: EVALUATE** -- Score on dimensions that matter for technology decisions.

- TCO at Year 3, not sticker price ("free" OSS needing a full-time engineer is expensive)
- Score on: Fit (5), TCO (4), Operational burden (4), Team capability (3), Lock-in risk (3), Time to value (3), Flexibility (2)
- Apply build-vs-buy heuristic: core competency, requirements stability, team capacity, timeline, scale, compliance

Load `references/tco-framework.md` and `references/vendor-evaluation.md`.

**Gate**: TCO estimated. Dimensions scored. Build-vs-buy heuristic applied.

**Phase 3: RECOMMEND** -- Clear recommendation with reasoning.

- Present weighted scoring matrix
- State: Decision, Confidence, Why, Watch-for risks, Migration path, First step
- Define exit criteria: when to reconsider for each option type

**Gate**: Recommendation stated. Exit criteria defined. First step identified.

---

### Mode: GROWTH (CMO)

**Framework**: ASSESS -> STRATEGIZE -> PLAN

**Phase 1: ASSESS** -- Understand current state before recommending.

- Audit: publications, content volume, existing audience, active channels, performance data
- Identify binding constraint: Discovery, Content, Conversion, Retention, or Capacity
- Creator capacity is the binding constraint -- recommend what one person can sustain

**Gate**: Current state audited. Binding constraint identified.

**Phase 2: STRATEGIZE** -- Design approach matching capacity and constraint.

- Solve the constraint, not everything
- Prefer compound strategies (SEO, evergreen, community) over one-shot campaigns
- Maximum 3 active channels with format, cadence, success metric, effort estimate

Load `references/audience-segmentation.md` and `references/channel-evaluation.md`.

**Gate**: Strategy selected. Maximum 3 channels. Effort estimated against capacity.

**Phase 3: PLAN** -- Convert strategy into a 90-day executable plan.

- One primary metric, 2-3 secondary
- 30-day phases: Foundation (1-30), Execution (31-60), Evaluate (61-90)
- Explicit abandon criteria, pivot triggers, double-down conditions

**Gate**: 90-day plan with checkpoints. Primary metric defined. Abandon criteria explicit.

---

### Mode: COMPETITIVE

**Framework**: MAP -> ANALYZE -> POSITION

**Phase 1: MAP** -- Build a structured picture of the competitive landscape.

- Define arena: what you compete on, who you serve, where you compete
- Tier competitors: Direct (full analysis), Adjacent (positioning only), Aspirational (strategy extraction), Emerging (watch list)
- Map the landscape before zooming in

**Gate**: Arena defined. Competitors identified and tiered. At least 2 direct competitors mapped.

**Phase 2: ANALYZE** -- Extract actionable intelligence from behavior, not surface impressions.

- Focus on what they DO, not what they SAY (pricing, launches, cadence reveal strategy)
- Analyze for gaps, not imitation
- For each direct competitor: product/content analysis, audience analysis, strategy signals

Load `references/competitive-mapping.md` and `references/market-positioning.md`.

**Gate**: Direct competitors analyzed. Gaps and weaknesses identified.

**Phase 3: POSITION** -- Convert intelligence into defensible differentiation.

- Build positioning map on two dimensions where you can differentiate
- Define: positioning statement, defensible advantages, vulnerable advantages, strategic gaps to exploit
- Monitoring cadence: monthly (direct), quarterly (full landscape), trigger-based (major moves)

**Gate**: Positioning map built. Differentiation strategy defined. Monitoring cadence set.

---

### Mode: EVALUATION

**Framework**: SCOPE -> EVALUATE -> VERDICT

**Phase 1: SCOPE** -- Define the project and success criteria.

- Define done before estimating effort
- Separate vision from MVP -- evaluate the minimum viable version
- Name the binding constraint (time, money, skills, attention)
- Define success criteria, problem solved, who benefits, why now

**Gate**: Project defined with measurable success criteria. MVP scope identified. Binding constraint named.

**Phase 2: EVALUATE** -- Assess feasibility, estimate effort, calculate ROI.

- Feasibility: Technical, Resource, Market (each High/Medium/Low confidence)
- Effort in ranges, not points ("2-5 weeks, most likely 3")
- Include hidden costs: learning curve, integration, testing, documentation (add 20-40%)
- ROI: direct value, indirect value, strategic value vs. build cost, ongoing cost, opportunity cost

Load `references/feasibility-scoring.md` and `references/roi-frameworks.md`.

**Gate**: Feasibility assessed. Effort estimated in ranges. ROI calculated with confidence.

**Phase 3: VERDICT** -- Clear go/no-go recommendation.

- Verdict: GO, GO WITH CONDITIONS, DEFER, or NO-GO
- Include: summary, key factors, conditions (if conditional), what would change verdict, next step
- For multiple projects: rank using RICE scoring (Reach * Impact * Confidence / Effort)

**Gate**: Verdict stated with confidence. Conditions specified. Next step identified.

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| Too many options | 5+ options creating paralysis | Eliminate obviously inferior options first. Get to 2-4 before full framework. |
| Not enough information | Cannot answer framing questions | Identify 2-3 critical unknowns. Recommend time-boxed research sprint. |
| Analysis paralysis | Keeps adding criteria or second-guessing | Apply reversibility test. If reversible, recommend best option with checkpoint. |
| Emotional attachment | User already decided, wants validation | Name the pattern. Ask: stress-test the choice, or genuinely evaluate? |
| Comparing apples to oranges | Options at different abstraction levels | Normalize to capability level. Compare what each gives for the specific need. |
| Vendor lock-in fear | Over-weights lock-in, under-weights time-to-value | Quantify actual switching cost vs. concrete speed benefit. |
| Build bias (NIH) | Team wants to build because it is more interesting | Core competency test: "If this disappeared, would customers notice?" |
| Vanity metrics | Optimizes followers/likes instead of outcomes | Redirect to "one metric that matters" -- what action should the audience take? |
| Scope creep during evaluation | Keeps adding features | Freeze scope at Phase 1 end. Additional features evaluate as v2. |
| Optimism bias | Effort estimates too low | Reference class test. No similar project? Add 50% to pessimistic estimate. |

---

## References

| Reference | When to Load | Content |
|-----------|-------------|---------|
| `references/strategic-frameworks.md` | STRATEGY: market entry, competitive dynamics, SWOT, OKR | Porter's Five Forces, SWOT scoring, OKR alignment |
| `references/decision-matrices.md` | STRATEGY: structured scoring, comparison, pre-mortem | Weighted matrices, ICE/RICE scoring, pre-mortem templates |
| `references/tco-framework.md` | TECHNOLOGY: TCO modeling, cost projections, build vs buy | TCO templates, hidden cost checklists, migration models |
| `references/vendor-evaluation.md` | TECHNOLOGY: vendor comparison, RFP, integration complexity | Vendor scorecards, RFP criteria, red flags, contract checklist |
| `references/audience-segmentation.md` | GROWTH: audience analysis, ICP, persona development | ICP scoring, persona templates, segmentation frameworks |
| `references/channel-evaluation.md` | GROWTH: channel selection, CAC/LTV, content funnel | Channel scoring, CAC/LTV models, funnel mapping |
| `references/competitive-mapping.md` | COMPETITIVE: landscape mapping, feature comparison, profiling | Landscape templates, feature matrices, activity tracker |
| `references/market-positioning.md` | COMPETITIVE: positioning strategy, differentiation scoring | Positioning maps, differentiation scoring, win/loss frameworks |
| `references/feasibility-scoring.md` | EVALUATION: feasibility, risk, go/no-go | Three-dimension model, confidence calibration, decision tree |
| `references/roi-frameworks.md` | EVALUATION: effort estimation, ROI, project comparison | T-shirt sizing, three-point estimation, risk-adjusted NPV |
