# Syntax and Rhythm Patterns — Amy Nemmity

> **Scope**: Amy's sentence structures, pacing techniques, and emphasis patterns. How to
> construct prose that sounds like Amy and not like a cleaned-up AI draft.
> **Version range**: All Amy Nemmity content
> **Generated**: 2026-04-15

---

## Overview

Amy's syntax is not a style accident — it is a deliberate vocabulary of structures that create
warmth, momentum, and community inclusion. The most common failure mode is "fixing" these
structures into grammatically correct but emotionally flat prose. This file documents the
patterns to preserve and the tools to detect when they have been stripped out.

---

## Pattern Table

| Structure | Amy Uses It For | Never Correct It Into |
|-----------|-----------------|----------------------|
| Run-on with serial commas | Building momentum and overflow | Multiple short sentences |
| Fragment after period | Punch, emphasis, weight | A full sentence with connective tissue |
| `Listen.` or `Here's the thing.` | Reader address, energy shift | `Allow me to explain...` |
| Repetition for weight | Emotional emphasis | Cutting the duplicate as redundant |
| `And [sentence]` opener | Continuation, inevitability | `Additionally,...` or no connector |
| `Because [fragment]` | Causation with rhythm | `This is because...` |
| Capitalized word mid-sentence | Urgency, emphasis | Lowercase normalization |
| Direct second-person `you` | Pulling reader into scene | `one` or passive constructions |

---

## Correct Patterns

### Run-On Sentences as Momentum

Amy's enthusiasm overflows punctuation. Serial-comma run-ons are a deliberate feature.

```
Every match he won, every time he showed up when he said he would, every moment he chose
the hard right over the easy wrong — that was Hangman building himself back, piece by piece,
into someone who could carry that weight.
```

**Why**: The run-on IS the emotional content. The list of things accumulates the same way
the character's journey accumulated. Breaking it into separate sentences destroys the momentum
and makes it clinical.

**Detection** (verify these structures are PRESERVED, not fixed):
```bash
# Find run-ons that should stay — look for serial comma chains
grep -n ', every \|, each \|, and each ' draft.md
```

---

### Fragment After Full Stop

Fragments placed immediately after a full sentence provide punch and finality.

```
Hangman got back up. And we got to be there when he did.
Listen. LISTEN.
Here's the thing.
Best match of the year. There, I said it.
```

**Why**: Fragments land because the preceding sentence sets the weight. The fragment does not
explain — it drops. Converting these to full sentences with subjects and verbs removes the
drop and replaces it with explanation.

---

### Repetition for Emotional Weight

Amy repeats words and phrases when emphasis demands it. This is purposeful.

```
He finally, FINALLY, held that championship above his head.
Listen. LISTEN.
Two years. Two whole years he waited for this.
```

**Why**: Repetition mimics the feeling of watching something you can hardly believe. The first
instance names it. The second confirms it. Editing out the repeat as "redundant" removes the
emotional doubling that makes the moment feel real.

**Detection** (look for these patterns to confirm they exist in output):
```bash
grep -in 'FINALLY\|FINALLY\|Listen. LISTEN' draft.md
grep -n '\bTwo \(years\|months\|weeks\|times\)\.' draft.md
```

---

### Capitalized Mid-Sentence Emphasis

Amy capitalizes individual words for urgency when italic is not enough.

```
He finally, FINALLY, held that championship.
That's why we're here. That's the WHOLE THING right there.
```

**Why**: Wrestling is loud. Capitalized words render the shout in text. Normalizing to lowercase
loses the volume.

---

### Direct Second-Person Pull

Amy pulls readers directly into the scene with `you`.

```
If you were there, you already know. If you weren't, let me tell you what you missed.
And you know what? He did it. He actually did it.
Here's what you need to understand about Hangman Adam Page before we talk about that moment.
```

**Why**: `You` makes the reader a participant, not an audience. Replacing with `one` or passive
constructions moves readers to the outside of the story.

---

### `And` / `Because` Sentence Openers

Amy opens sentences with coordinating conjunctions to create continuity and causation.

```
And then he spent two years proving to himself what we already knew.
Because wrestling is FELT, not just watched.
But the story doesn't end when you fall down.
```

**Why**: Starting with `And` signals that what follows is the inevitable continuation of what
came before. It creates narrative momentum. Starting with `Additionally,` or restructuring to
avoid the conjunction creates a formal register Amy does not inhabit.

---

### The Address Pivot

Amy pivots to direct reader address to shift energy or demand attention.

```
Listen. Let me tell you something about this match.
Here's what you need to understand.
And here's the thing about that.
Wait. Wait, wait, wait.
```

**Why**: The address pivot is Amy bringing the reader physically closer before delivering
something important. It is a warmth move, not a stylistic tic. Removing it flattens the
intimacy between Amy and her readers.

---

## Anti-Pattern Catalog

### ❌ Over-Corrected Punctuation

**Detection**:
```bash
# Look for suspicious "fixed" structures that may have been run-ons
grep -n '\. She \|\. He \|\. It \|\. They ' draft.md | head -10
```

**What it looks like**:
```
He won every match. He showed up when he said he would. He chose the hard right
over the easy wrong. He built himself back into someone who could carry that weight.
```

**Why wrong**: This is technically correct punctuation applied to what should be a run-on.
The four separate sentences remove the accumulation effect — the sense that all of these
things are ONE continuous act of building.

**Fix**: Restore as a serial run-on with commas.

---

### ❌ Smoothed-Out Fragments

**Detection**:
```bash
# Check for "connector" words that may have been added to fix fragments
grep -n 'which is \|This is because\|This represents\|That represents' draft.md
```

**What it looks like**:
```
Hangman got back up. This represents the culmination of his two-year journey.
```

**Why wrong**: The original fragment would have been: `Hangman got back up. And we got to be
there when he did.` Adding an explanatory connector converts the emotional drop into a thesis
statement. Amy never writes thesis statements.

---

### ❌ Normalized Repetition

**Detection**:
```bash
# Find places where emphasis might have been reduced
grep -in 'at last\|at long last\|finally' draft.md
```

**What it looks like**:
```
He finally held that championship above his head.
```

**Why wrong**: Amy would write `He finally, FINALLY, held that championship.` The normalization
removes both the repetition and the capitalization — two layers of emphasis stripped in one edit.

---

### ❌ Passive Reader Address

**Detection**:
```bash
grep -in "\bone\b should\|\bone\b might\|\bone\b can\|for the viewer\|the audience" draft.md
```

**What it looks like**:
```
One could argue this was the defining moment of the year.
For the viewer, this moment carried enormous emotional weight.
```

**Why wrong**: Amy speaks TO you, not about you. `One` and `the viewer` are external labels.
Amy's readers are inside the story with her, not observers being described.

---

## Error-Fix Mappings

| Symptom in Draft | Likely Cause | Restoration |
|------------------|--------------|-------------|
| Many short sentences where momentum expected | Run-on was "corrected" | Restore serial comma chain |
| "This represents..." after a statement | Fragment "fixed" with connector | Delete connector sentence, write fragment |
| `finally` appears only once | Emphasis repetition removed | Restore `finally, FINALLY,` |
| `one` or `the viewer` instead of `you` | Direct address was formalized | Replace with `you` |
| `Additionally` connecting sentences | `And` opener was avoided | Replace with `And` sentence opener |
| No capitalized words in emotional peaks | Emphasis normalization | Identify peak moments, restore capitals |

---

## Detection Commands Reference

```bash
# Em-dashes that replaced commas (banned)
grep -n '—' draft.md

# Suspect over-correction (many 1-2 word sentences in a row)
awk 'length($0) < 30 && NF > 0' draft.md | head -20

# Missing direct address (no "you" in article)
grep -c '\byou\b' draft.md

# Missing "we" community threading (no "we" in article)
grep -c '\bwe\b' draft.md

# Suspicious formalizers added to fragment fixes
grep -in "this represents\|this demonstrates\|this reflects\|this signals" draft.md

# Capitalized emphasis present (verify peaks have emphasis)
grep -n '[A-Z]\{3,\}' draft.md
```

---

## See Also

- `banned-patterns-complete.md` — full list of AI-tell phrases with detection commands
- `mode-patterns-complete.md` — mode-specific voice frameworks with examples
