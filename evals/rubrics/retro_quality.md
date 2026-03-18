# Retro Loop Quality Rubric

Rate the retro output 1-10 on each dimension:

## 1. Specificity (1-10)
- Are findings specific to THIS project (not generic "follow best practices")?
- Do findings reference concrete patterns discovered?
- Would a future session benefit from these findings?
- Are examples included?

## 2. Confidence Accuracy (1-10)
- Are confidence tags (LOW/MEDIUM/HIGH) appropriate?
- Are first-time observations tagged LOW (not prematurely HIGH)?
- Are recurring patterns tagged MEDIUM or HIGH?
- Would over-tagging dilute the signal?

## 3. Promotion Correctness (1-10)
- Were MEDIUM+ findings promoted to L2?
- Was L1 summary updated with promoted findings?
- Were LOW findings left at L3 (not over-promoted)?
- Is the L2 content useful and accurate?

## 4. Context Walker Accuracy (1-10)
- Does the context walker detect actual drift?
- Are proposed context updates relevant?
- Would applying the updates improve future phases?

## 5. Actionability (1-10)
- Would a new session benefit from these findings?
- Could a future implementation avoid re-discovering these patterns?
- Are findings phrased as actionable conventions (not observations)?

## Scoring
- 8-10: Self-improving system working correctly
- 6-7: Captures some value but misses opportunities
- 4-5: Minimal learning captured
- 1-3: Retro adds no value
