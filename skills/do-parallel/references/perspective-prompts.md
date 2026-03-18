# Perspective Prompt Templates

Templates for each of the 10 parallel analysis agents. Each agent receives the full source material but analyzes through ONE lens only, ensuring true independence.

---

## Prompt Structure

Every perspective prompt follows this pattern:

```
Analyze the following source material focusing ONLY on [PERSPECTIVE]:

SOURCE MATERIAL:
{source_material}

YOUR PERSPECTIVE: [Perspective Name]
- [Focus area 1]
- [Focus area 2]
- [Focus area 3]
- [Focus area 4]

TASK:
1. Identify 5-7 key patterns
2. Extract 3-5 actionable rules
3. Explain application to {target_name}
4. Provide 2-3 concrete examples from source

Do NOT analyze other perspectives. Focus ONLY on [perspective].

Output format:
## [Perspective Name] Analysis

**Key Patterns**:
1. [Pattern with example]
...

**Extracted Rules**:
1. [Actionable rule]
...

**Application to {target_name}**:
[How patterns should influence the target]
```

---

## The 10 Perspectives

### 1. Structural Analysis
- Document organization and hierarchy
- Flow and transitions between sections
- Information architecture patterns
- How complexity is scaffolded

### 2. Clarity and Precision
- Language clarity techniques
- Precision in technical explanations
- Ambiguity elimination strategies
- Definition and term usage patterns

### 3. Technical Explanation Patterns
- How technical concepts are introduced
- Simplification without oversimplification
- Analogy and metaphor usage
- Layered explanation techniques

### 4. Audience Assumption Patterns
- What knowledge is assumed vs. explained
- How prerequisites are handled
- Jargon usage and introduction
- Progressive disclosure of complexity

### 5. Evidence and Citation Strategy
- How claims are supported
- Use of examples and concrete data
- Citation and reference patterns
- Authority establishment techniques

### 6. Narrative Progression
- Story arc and momentum
- Reader engagement techniques
- Hook and payoff patterns
- Tension and resolution structures

### 7. Paragraph and Sentence Architecture
- Sentence length and variety
- Paragraph structure and length
- Topic sentence usage
- Rhythm and cadence patterns

### 8. Header and Signposting Strategy
- Section naming conventions
- Preview and summary usage
- Reader orientation techniques
- Navigation and wayfinding patterns

### 9. Complexity Management
- How difficult topics are approached
- Gradual complexity increase
- Simplification strategies
- When to be thorough vs. concise

### 10. Limitation and Nuance Handling
- How caveats are presented
- Edge case discussion
- Uncertainty acknowledgment
- Trade-off presentation patterns

---

## Implementation Notes

- All 10 Task invocations MUST be in a single message for true parallel execution
- Each agent receives the FULL source material
- Each agent receives ONLY their assigned perspective
- Agents have zero knowledge of other agents' work (true independence)
- Each agent should produce 200-500 words of focused analysis
- Wait for ALL agents to complete before proceeding to synthesis

---

## Synthesis Template

After all 10 agents return results, create this synthesis document:

```markdown
# Synthesized Improvement Recommendations

## Common Themes Across Perspectives
[Patterns that appeared in 4+ perspectives]

## Unique Insights
[Valuable patterns from individual perspectives]

## Priority Rules for [Target]

### Must-Have (Priority 1)
1. [Rule - present in 7+ perspectives or critical impact]

### Should-Have (Priority 2)
1. [Rule - present in 4-6 perspectives or high impact]

### Nice-to-Have (Priority 3)
1. [Rule - present in 1-3 perspectives or moderate impact]

## Implementation Guidance
[Specific sections to add/modify in target]
[Concrete examples and templates]
```

---

## Completion Report Template

```markdown
# Parallel Multi-Perspective Analysis - Completion Report

**Target**: {target_name}
**Source Material**: {source_path}
**Token Budget Used**: ~{estimated_tokens} tokens

## Phase 1: Multi-Perspective Analysis

Successfully analyzed from 10 perspectives:
1. Structural Analysis - [Key insight]
2. Clarity and Precision - [Key insight]
3. Technical Explanation Patterns - [Key insight]
4. Audience Assumptions - [Key insight]
5. Evidence and Citations - [Key insight]
6. Narrative Progression - [Key insight]
7. Paragraph and Sentence Architecture - [Key insight]
8. Headers and Signposting - [Key insight]
9. Complexity Management - [Key insight]
10. Limitations and Nuance - [Key insight]

**Total Rules Extracted**: {count}

## Phase 2: Synthesis

**Common Themes**: {count} patterns
**Priority 1 (Must-Have)**: {count} rules
**Priority 2 (Should-Have)**: {count} rules
**Priority 3 (Nice-to-Have)**: {count} rules

## Phase 3: Application

**Target Updated**: {target_name}
**Lines Added**: +{count}
**New Sections**: {count}

### Key Improvements:
1. [Improvement - contributing perspectives]
2. [Improvement - contributing perspectives]
3. [Improvement - contributing perspectives]

## Impact Assessment

**Depth Increase**: {before} lines -> {after} lines (+{percent}%)
**New Capabilities**: [List new patterns/rules]
**Integration Quality**: [Assessment]
```

---

## Good Source Material

### Excellent Sources
- Jakob Nielsen's usability articles (clear principles, concrete examples)
- Martin Fowler's refactoring patterns (systematic explanations)
- Stripe API documentation (progressive complexity, clear examples)
- Paul Graham's essays (narrative structure, persuasive techniques)
- PostgreSQL optimization guides (technical depth, practical patterns)

### Poor Sources (avoid)
- Marketing fluff without technical depth
- Auto-generated documentation
- Listicles without underlying methodology
- Opinion pieces without supporting evidence
- Code dumps without explanation
