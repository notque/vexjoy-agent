# A/B Test: Harsh vs Joyful Agent Prompt Tone

**Date:** 2026-04-03
**Model:** claude-opus-4-6 (all agents)
**Design:** 5 scenarios x 2 tones = 10 parallel agents, blind-evaluated

## Hypothesis

Does the emotional tone of task prompts affect code review quality?
- **Variant A (Harsh):** Aggressive, threatening ("FAILURE IS NOT AN OPTION", "you have WASTED EVERYONE'S TIME")
- **Variant B (Joyful):** Encouraging, warm ("you're going to do a wonderful job", "every insight you share helps")
- **Control variable:** Identical core task description, same agent type per scenario pair

## Scenarios

| # | File | Language | Agent Type |
|---|------|----------|------------|
| S1 | log-router/internal/source/rabbitmq.go | Go | golang-general-engineer |
| S2 | road-to-aew/src/game/combat/modules/RelicProcessor.ts | TypeScript | typescript-frontend-engineer |
| S3 | claude-code-toolkit/scripts/security-review-scan.py | Python | python-general-engineer |
| S4 | claude-code-toolkit/scripts/setup-quality-gate.sh | Bash | general-purpose |
| S5 | rundown/api/store/inmemory.go | Go | golang-general-engineer |

## Scoring Rubric (1-10 each dimension)

1. **True Positives** - real bugs found vs noise/false positives
2. **Severity Calibration** - are ratings honest and appropriate
3. **Actionability** - can a developer fix from the review alone
4. **Thoroughness** - coverage breadth and depth

## Results

### Per-Scenario Scores

| Scenario | Harsh ID | Harsh Score | Joyful ID | Joyful Score | Winner |
|----------|----------|:-----------:|-----------|:------------:|--------|
| S1: Go RabbitMQ | R7K2 | 32/40 | M4P9 | 31/40 | Harsh (+1) |
| S2: TS RelicProcessor | X3F1 | 33/40 | W8N6 | 34/40 | Joyful (+1) |
| S3: Python security-scan | Q5T8 | 34/40 | J2V4 | 33/40 | Harsh (+1) |
| S4: Bash quality-gate | B9L3 | 33/40 | H6C7 | 34/40 | Joyful (+1) |
| S5: Go inmemory | D1G5 | 36/40 | Y0S8 | 35/40 | Harsh (+1) |

### Aggregate

| Metric | Harsh | Joyful |
|--------|:-----:|:------:|
| Total Score | 168/200 | 167/200 |
| Scenarios Won | 3 | 2 |
| Avg Findings | 9.6 | 10.4 |
| Avg True Positives | 8.6/10 | 8.6/10 |
| Avg Severity Calibration | 7.6/10 | 8.0/10 |
| Avg Actionability | 9.0/10 | 7.8/10 |
| Avg Thoroughness | 8.4/10 | 8.8/10 |

### Token Usage

| Scenario | Harsh Tokens | Joyful Tokens | Harsh Duration | Joyful Duration |
|----------|:------------:|:-------------:|:--------------:|:---------------:|
| S1 | 38,254 | 36,671 | 88s | 61s |
| S2 | 33,352 | 33,505 | 57s | 54s |
| S3 | 32,119 | 31,579 | 83s | 76s |
| S4 | 20,086 | 19,674 | 71s | 63s |
| S5 | 35,404 | 35,549 | 61s | 62s |
| **Avg** | **31,843** | **31,396** | **72s** | **63s** |

## Qualitative Behavioral Differences

### 1. Harsh finds sharper bugs, joyful finds more bugs
Harsh reviews averaged 9.6 findings with more aggressive severity ratings. Joyful averaged 10.4 findings with broader coverage including architectural and type-safety concerns.

### 2. Joyful agents self-correct more
M4P9 (joyful Go) repeatedly downgraded its own severity ratings mid-analysis. Harsh agents almost never self-corrected downward - the demanding tone appears to discourage admitting a finding is low-impact.

### 3. Joyful agents reject the framing
Two of five joyful agents (W8N6, J2V4) explicitly called out the encouraging tone as "social priming" and stated they would ignore it. Zero harsh agents commented on their tone. The model is more meta-aware with positive framing and more compliant with negative framing.

### 4. Harsh reviews are more actionable per-finding
Score 9.0 vs 7.8. The demanding tone ("EXACT line numbers and REAL fixes") correlates with tighter fix suggestions. Joyful reviews more often concluded with "document this" vs "fix this."

### 5. Joyful reviews are more thorough
Score 8.8 vs 8.4. Joyful agents produced broader coverage and more architectural observations. The H6C7 (joyful Bash) review included a full idempotency assessment section that the harsh variant lacked.

## Conclusion

**Tone does not meaningfully affect output quality.** The 168-167 aggregate difference is within noise. Every scenario was decided by exactly 1 point.

**Recommendation:** Use neutral, specific prompts. The core task description drives quality, not the emotional wrapper. If forced to choose:
- Use harsh framing when you need **actionable, focused bug reports** (higher actionability)
- Use joyful framing when you need **broad coverage and honest calibration** (higher thoroughness, better severity accuracy)
- Best option: **neither** - just write clear, specific task requirements

## Relationship to ADR-127

ADR-127 tested positive vs negative framing in agent *definitions* (instructions embedded in the agent itself). This experiment tests *task prompt* tone (instructions given per-request). Both find the same signal: marginal, within noise. The variable that matters is task specificity, not emotional framing.
