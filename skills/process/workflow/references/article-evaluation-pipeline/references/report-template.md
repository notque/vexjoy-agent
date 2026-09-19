# Article Evaluation Report Template

## Report Structure

Generate the evaluation report in this exact format:

```
===============================================================
 ARTICLE EVALUATION REPORT
===============================================================

 Source: [URL or file path]
 Voice: [voice-name]
 Date: [evaluation timestamp]

===============================================================
 VALIDATION SCORES
===============================================================

 Voice Match: [score]/100 [PASSED|FAILED]
 Banned Patterns: [score]/100 [CLEAN|VIOLATIONS]

 Summary:
   Errors: [count]
   Warnings: [count]
   Wabi-Sabi Markers: [count]

===============================================================
 WABI-SABI ANALYSIS
===============================================================

 AUTHENTIC IMPERFECTIONS FOUND:

   1. "[marker]" (line [N])
      -> [classification reason]
      -> DO NOT FIX

   2. [...]

===============================================================
 VOICE PATTERN ANALYSIS
===============================================================

 PATTERNS MATCHED:
   | Pattern | Found? | Example |
   |---------|--------|---------|
   | [pattern] | YES/WARN/NO | [example] |

 WARNINGS:
   [list of warnings with context]

===============================================================
 BANNED PATTERN CHECK
===============================================================

 [CLEAN or list of violations]

===============================================================
 VERDICT: [AUTHENTIC|NEEDS WORK|FAILED]
===============================================================

 [Summary and recommendations]

===============================================================
```

## Verdict Criteria

| Verdict | Conditions |
|---------|------------|
| AUTHENTIC | Voice >= 60, banned = 100, wabi-sabi markers present |
| NEEDS WORK | Voice >= 60, banned < 100 (minor violations) |
| FAILED | Voice < 60, or major banned pattern violations |

## Example: Authentic Article (Should Pass)

```
Voice Match: 79/100 (PASSED)
Banned Patterns: 100/100 (CLEAN)
Wabi-Sabi Markers: 3 found
  - "orchistrates" (typo, line 59) -> KEEP
  - "That's it." (fragment, line 43) -> KEEP
  - Run-on enthusiasm (line 12) -> KEEP

VERDICT: AUTHENTIC
```

## Example: AI-Generated Article (Should Fail)

```
Voice Match: 45/100 (FAILED)
Banned Patterns: 75/100 (VIOLATIONS)
  - Em-dash found (line 23)
  - "It's not X, it's Y" (line 45)
  - "truly remarkable" (line 67)
Wabi-Sabi Markers: 0 found
  -> Suspiciously perfect

VERDICT: FAILED - Exhibits AI patterns
```
