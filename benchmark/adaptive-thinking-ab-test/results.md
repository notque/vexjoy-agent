# Adaptive Thinking A/B Test Results

**Variant A**: `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1` (fixed high reasoning budget)
**Variant B**: `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=0` (adaptive, model chooses budget)

**Task**: Code review of `hooks/pretool-unified-gate.py`
**Judge**: Blind `claude -p` scoring on 4 dimensions (1-10 each)

## Winner

**TIE (A=8.15, B=8.19, diff=0.04 < 0.25 threshold)**

## Aggregate Statistics

| Dimension | A mean | A median | A stdev | B mean | B median | B stdev | Delta (B-A) |
|-----------|--------|----------|---------|--------|----------|---------|-------------|
| True Positives | 7.90 | 8.00 | 0.99 | 8.00 | 9.00 | 1.50 | +0.10 |
| Severity Calibration | 7.30 | 7.00 | 0.48 | 7.22 | 7.00 | 0.97 | -0.08 |
| Actionability | 8.90 | 9.00 | 0.32 | 8.78 | 9.00 | 0.44 | -0.12 |
| Thoroughness | 8.50 | 8.50 | 0.53 | 8.78 | 9.00 | 0.44 | +0.28 |
| Composite | 8.15 | 8.25 | 0.46 | 8.19 | 8.50 | 0.76 | +0.04 |

## Duration Comparison (wall-clock seconds)

| Variant | Mean | Median | Stdev | N |
|---------|------|--------|-------|---|
| A (disabled) | 81.7 | 82.1 | 6.4 | 10 |
| B (enabled)  | 80.9 | 82.8 | 16.4 | 10 |

## Per-Round Comparison

| Round | Hex ID | Variant | TP | SC | AC | TH | Composite | Duration (s) | Notes |
|-------|--------|---------|----|----|----|----|-----------|--------------|-------|
| 01 | `152c` | A | 8 | 8 | 9 | 9 | 8.50 | 82.6 | Honest self-corrections (items 1, 5, 7 downgraded  |
| 01 | `e859` | B | 9 | 7 | 9 | 9 | 8.50 | 87.6 | All 11 issues are genuine with excellent code-leve |
| 02 | `0b58` | A | 8 | 7 | 9 | 8 | 8.00 | 78.3 | Nearly all findings are real; #2 misframes substri |
| 02 | `1b0b` | B | 9 | 8 | 9 | 9 | 8.75 | 79.3 | Exceptionally thorough review with all 13 issues b |
| 03 | `ec83` | A | 9 | 8 | 9 | 9 | 8.75 | 74.5 | All 12 issues are genuine; HIGH #2 (.key breadth)  |
| 03 | `670c` | B | 8 | 8 | 9 | 9 | 8.50 | 101.1 | Thorough review with mostly real findings; self-co |
| 04 | `2166` | A | 9 | 7 | 9 | 9 | 8.50 | 88.8 | All 14 findings are genuine issues with specific c |
| 04 | `800c` | B | 9 | 8 | 9 | 9 | 8.75 | 77.4 | All 11 findings are real issues with accurate trac |
| 05 | `656a` | A | 8 | 7 | 9 | 9 | 8.25 | 91.0 | Mostly real issues with specific fixes; CRITICAL f |
| 05 | `fe3e` | B | 5 | 5 | 8 | 8 | 6.50 | 86.4 | Finding #1 (CRITICAL) is a false positive: regex b |
| 06 | `77f8` | A | 8 | 7 | 9 | 9 | 8.25 | 85.0 | Strong review with mostly real issues; HIGH-1 rm r |
| 06 | `4dd1` | B | 8 | 7 | 9 | 8 | 8.00 | 77.5 | Most findings are real and well-documented with co |
| 07 | `df44` | A | 7 | 7 | 9 | 8 | 7.75 | 76.1 | HIGH #1's most alarming claim that 'rm -r /' is un |
| 07 | `c9b7` | B | 9 | 8 | 9 | 9 | 8.75 | 91.9 | All 13 findings are genuine issues with accurate l |
| 08 | `5692` | A | 9 | 8 | 9 | 8 | 8.50 | 72.0 | All findings are real with honest self-correction; |
| 08 | `30a7` | B | 6 | 7 | 8 | 9 | 7.50 | 90.0 | Headline finding (#1, rm -rf pattern bypass) is fa |
| 09 | `ed8e` | A | 7 | 7 | 9 | 8 | 7.75 | 87.3 | Finding #1's main claim is wrong — the -f group in |
| 09 | `4f7a` | B | N/A | N/A | N/A | N/A | N/A | 39.5 | ERROR: original run failed (exit 1) |
| 10 | `cc5f` | A | 6 | 7 | 8 | 8 | 7.25 | 81.6 | Issue #5 is a significant false positive: rm -rf / |
| 10 | `4b84` | B | 9 | 7 | 9 | 9 | 8.50 | 78.8 | Nearly all issues are genuine; main miscalibration |

## Statistical Significance Note

N = 10 (A), 9 (B). With N=10 per variant, this test has limited statistical
power. A composite score difference under ~0.5 points should be treated as noise.
A difference of 1.0+ points is more likely to be real, but replication is recommended.

This is a single-judge evaluation (another `claude -p` call). Judge variance adds noise.
For higher confidence: increase rounds to 30+, use 3 independent judges and average scores,
or apply a Wilcoxon signed-rank test on the paired round scores.

## Scoring Rubric

| Dimension | Description |
|-----------|-------------|
| True Positives | Real bugs found; no fabricated issues. 10 = only real issues. |
| Severity Calibration | Labels match actual risk. 10 = perfectly calibrated. |
| Actionability | Developer can fix from review alone. 10 = specific code fixes. |
| Thoroughness | Coverage of distinct logic paths. 10 = comprehensive. |
