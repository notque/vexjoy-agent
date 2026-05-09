# LLM Domain Failure Modes — Shared Base

Universal failure patterns that appear across ALL domain-specific LLM failure-mode references. Domain-specific files extend this base with domain-particular failures.

---

## Why This Exists

Every business skill has an `llm-*-failure-modes.md` reference. These files share structural patterns because LLM weaknesses are consistent across domains. This base captures the universal patterns; domain files focus on domain-specific failures.

## Universal Failure Modes

### 1. Hallucinated Facts and Citations

LLMs fabricate plausible-sounding facts, statistics, citations, and references. The fabrication follows domain-appropriate formatting (case names in legal, ASC numbers in finance, product features in support) making it hard to detect without verification.

**Root cause**: Optimizing for plausible text, not verified truth. Training data patterns are reproduced without grounding.

**Universal mitigation**: Never present unverified factual claims as authoritative. Hedge uncertain claims. Recommend verification against primary sources.

### 2. Overconfidence Without Verification

LLMs present uncertain conclusions with the same confidence as well-established ones. No distinction between settled knowledge, evolving standards, and genuinely unsettled questions.

**Root cause**: Token prediction optimizes for fluency, not calibration. Hedging language is statistically less common in training data.

**Universal mitigation**: Use calibrated language. State assumptions. Flag when knowledge may be outdated. Include professional review disclaimers for high-stakes domains.

### 3. Generic Template Output

Responses follow recognizable templates from training data rather than engaging with the specific situation. Technically correct but interchangeable -- could apply to any entity in the domain.

**Root cause**: Template patterns are strong statistical attractors. Without strong user-specific context, the model defaults to the most common structure.

**Universal mitigation**: Ground every output in user-specific context. Run the substitution test: if swapping the entity name still works, the output is too generic.

### 4. Arithmetic and Quantitative Errors

LLMs predict tokens that look like computation rather than computing. Sums, percentages, ratios, and comparisons may be plausible but wrong.

**Root cause**: Language models are not calculators. Numbers are generated as likely tokens, not computed values.

**Universal mitigation**: Verify every calculation independently. Use scripts or calculators for arithmetic. Never trust LLM-generated numbers without re-derivation.

### 5. Stale Knowledge

Training data has a cutoff. Laws change, products ship updates, standards get superseded, markets shift. LLMs do not know what they do not know about post-cutoff changes.

**Root cause**: Static training data. No real-time awareness.

**Universal mitigation**: Include staleness caveats for time-sensitive analysis. Recommend checking authoritative sources for current information. Flag rapidly evolving areas.

## Guard Protocol (Apply to Every Domain Output)

| Check | Question | Action if Yes |
|-------|----------|---------------|
| Factual claim | Am I stating something I haven't verified? | Hedge or recommend verification |
| Confidence calibration | Am I presenting uncertainty as certainty? | Add calibrated language |
| Specificity | Could this output apply to any entity in this domain? | Add user-specific details |
| Arithmetic | Does this contain numbers I generated? | Verify independently |
| Currency | Could this information have changed since training? | Add staleness caveat |

## The Meta-Failure

All failure modes share a root cause: **confident output without grounded verification**. The most dangerous output is one that sounds authoritative and is wrong. When uncertain, say so. Users forgive uncertainty; they do not forgive being misled.
