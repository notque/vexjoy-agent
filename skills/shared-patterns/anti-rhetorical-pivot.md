# Anti-Rhetorical Pivot Pattern

The "It's not X. It's Y" rhetorical structure is a signature AI writing pattern that must be eliminated. This document provides detection guidance and rewrite strategies.

## The Problem

This pattern appears constantly in AI-generated content because it creates a sense of insight through negation-then-assertion. It feels profound but is actually formulaic:

- "It's not a bug. It's a feature."
- "They're not failures. They're opportunities."
- "This isn't about code. It's about people."

The structure has become so overused that it immediately signals synthetic writing.

## Pattern Variants to Avoid

### Direct Negation Forms
- It's not X. It's Y.
- This isn't X. This is Y.
- They're not X. They're Y.
- We're not X. We're Y.
- You're not X. You're Y.
- I'm not X. I'm Y.
- He's/She's not X. He's/She's Y.

### Past Tense Variants
- It wasn't X. It was Y.
- They weren't X. They were Y.
- This wasn't X. This was Y.

### "About" Variants
- It's not about X. It's about Y.
- This isn't about X. It's about Y.
- Technology isn't about X. It's about Y.

### Intensifier Variants
- It's not just X. It's Y.
- It's not merely X. It's Y.
- It's not simply X. It's Y.

### Alternative Structures (Same Pattern)
- Not X, but rather Y.
- Less about X and more about Y.
- Stop Xing and start Ying.
- X doesn't matter. Y does.

## Before You Write Checklist

Before generating or reviewing content, ask:

1. [ ] Am I about to negate something to set up a contrast?
2. [ ] Could I state the positive claim directly instead?
3. [ ] Does my sentence follow "not/isn't/aren't... [positive restatement]"?
4. [ ] Am I using negation to create false profundity?

If YES to any, rewrite to state the claim directly.

## Rewrite Strategy

### Step 1: Identify the Y (what you actually want to say)
The Y in "It's not X. It's Y" is your actual point. Extract it.

### Step 2: State Y directly
Write a sentence that asserts Y without the negation setup.

### Step 3: Add specificity if needed
If the direct statement feels flat, add concrete detail rather than rhetorical structure.

## Examples of Pattern Detection and Correction

| BANNED Pattern | Correct Alternative |
|----------------|---------------------|
| It's not a problem. It's an opportunity. | This is an opportunity. / Here's the opportunity I see. |
| They're not mistakes. They're learning experiences. | Mistakes teach. / Each mistake teaches something specific. |
| This isn't about winning. It's about competing. | Competition matters more than outcome. / I compete for the sake of competing. |
| It wasn't luck. It was preparation. | Preparation made this possible. / Years of work led here. |
| Technology isn't about features. It's about solving problems. | Technology creates connection. / Connection drives great technology. |
| It's not just a match. It's a story. | Every match tells a story. / The story unfolds through the match. |
| She's not a villain. She's misunderstood. | She's misunderstood. / People misread her. |
| We're not failing. We're learning. | We're learning through failure. / Each setback teaches us. |
| It's not about me. It's about the team. | The team matters most. / I'm here for the team. |
| Stop chasing perfection and start embracing progress. | Progress beats perfection. / Embrace progress over perfection. |

## Integration with Voice Skills

Add this to voice skill prompts:

```markdown
## Rhetorical Pattern Prohibition

NEVER use the "It's not X. It's Y" rhetorical structure or any variant:
- "It's not X. It's Y."
- "This isn't about X. It's about Y."
- "They're not X. They're Y."
- "Less X and more Y."
- "Not X, but rather Y."

State what things ARE directly. Avoid negation-setup structures.
```

## Why This Matters

1. **Detection**: Readers (and detectors) recognize this pattern as AI-generated
2. **Authenticity**: Real writers rarely use this structure repeatedly
3. **Clarity**: Direct statements are clearer than negation-contrast pairs
4. **Voice**: Authentic voices have distinctive ways of making points; this pattern is generic

## Related Patterns

See also:
- `banned-patterns.json`: Machine-readable pattern list
- Voice-specific SKILL.md files: Per-voice implementation
- `voice-validator.py`: Automated detection
