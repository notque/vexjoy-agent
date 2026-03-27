# Output Format Reference

Full output format for Phase 7 (OUTPUT) of the voice-writer pipeline.

---

## Report Template

```
===============================================================
 VOICE CONTENT: {Voice Name}
===============================================================

[Generated content here]

===============================================================
 VALIDATION REPORT
===============================================================

 Status: PASSED / FAILED
 Score: {score}/100
 Iterations: {N}

 Checks:
   [check] Banned patterns: None detected
   [check] Em-dash: 0 found
   [check] Rhythm: Varied sentence lengths
   [warn] Contraction rate: 65% (target: 72%)

 Metrics Comparison:
   | Metric            | Target | Actual | Status |
   |-------------------|--------|--------|--------|
   | Avg sentence len  | 15.3   | 14.8   | [ok]   |
   | Contraction rate  | 0.72   | 0.65   | [warn] |
   | Short sentences   | 0.35   | 0.32   | [ok]   |

 Joy Check:
   Status: PASSED
   Overall Joy Score: {score}/100
   Paragraphs: {N} JOY, {N} NEUTRAL, {N} CAUTION, 0 GRIEVANCE

===============================================================
```

## Status Indicators

| Indicator | Meaning |
|-----------|---------|
| `[check]` | Passed |
| `[warn]` | Warning |
| `[fail]` | Error |
| `[ok]` | Within threshold |

---

## Pipeline Completion Report (Phase 8)

```markdown
## Pipeline Complete
Voice: {name}
Status: PASSED/FAILED
Score: {score}/100
Joy Score: {joy_score}/100
Iterations: {N}
Output: [location or displayed inline]
```
