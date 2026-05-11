# Agent Communication Patterns

> **Scope**: Failure modes in agent output style — over-reporting, self-congratulation, verbose narration, and hedging. Covers what to detect and how to fix each.
> **Version range**: all versions
> **Generated**: 2026-05-11

---

## Overview

Agent output quality degrades in predictable ways: self-congratulation inflates summaries, narration of obvious steps adds noise, hedge words like "successfully" and "properly" signal defensiveness rather than confidence. These patterns make outputs longer without adding information, erode trust, and obscure actual facts. Each failure mode below has a detection pattern and a concrete fix.

---

## Pattern Table: Style Markers

| Phrase class | Examples | Signal |
|--------------|----------|--------|
| Self-congratulation | "Successfully completed", "Great job", "Well done" | Replace with bare fact |
| Complexity inflation | "complex task", "challenging problem", "sophisticated solution" | Delete entirely — never characterize difficulty |
| Machine-like hedging | "I have now", "I will now proceed to", "As requested" | Cut; start with the action |
| Passive completion | "has been done", "has been updated", "was modified" | Use active: "Updated X", "Fixed Y" |
| Empty affirmations | "Certainly!", "Of course!", "Absolutely!" | Delete; answer directly |
| Filler transitions | "Now let's", "Moving on to", "Next, I will" | Delete; execute the next step |

---

## Pattern Catalog: Detection and Fixes

### Self-Congratulation

**Detection**:
```bash
grep -rn "successfully\|Successfully\|great job\|well done\|excellent" \
  --include="*.md" --include="*.txt"
rg 'successfully (completed|finished|implemented|fixed|resolved)' -i
```

**Signal**:
```text
I have successfully completed the migration task! The database schema
has been successfully updated and all tests are passing. Great work!
```

**Why it matters**: "Successfully" adds no information — if the task failed, the agent wouldn't be reporting it as done. Every occurrence of "successfully" can be deleted with zero information loss. Self-congratulation transfers the user's attention from facts to sentiment.

**Preferred action**:
```text
Migrated the schema. 3 tables updated, 47 tests pass.
```

---

### Narrating Obvious Steps

**Detection**:
```bash
rg "I('m| am) (now |going to |about to )?(read|look|check|search|run|execute)" -i
rg "Let me (now |first |quickly )?(read|check|look at|search|run)" -i
```

**Signal**:
```text
Now I will read the configuration file to understand the current settings.
Let me check what's in the database before proceeding.
I'm going to look at the test output to diagnose the failure.
```

**Why it matters**: The tool call already shows the action. Narrating it before the call doubles the words without adding context. Users scanning output skip narration to find facts.

**Preferred action**: Execute the tool call. If a brief orienting phrase is needed, one word is sufficient: "Checking the config." not "Now I will proceed to carefully examine the configuration file to understand the current state of the settings."

---

### Difficulty Inflation

**Detection**:
```bash
rg "complex|challenging|sophisticated|non-trivial|tricky|difficult" -i \
  --include="*.md"
grep -rn "complex task\|challenging problem\|complex issue\|difficult bug" -i
```

**Signal**:
```text
This is a complex refactoring task involving sophisticated architectural changes.
The challenging nature of this problem required careful analysis.
```

**Why it matters**: Characterizing difficulty is self-serving narration. If the task was trivial, calling it complex is inaccurate. If it was genuinely hard, the solution demonstrates that — the label adds nothing and can read as excuse-making.

**Preferred action**: Never characterize difficulty. Describe what was done and why.

---

### Hollow Completions

**Detection**:
```bash
rg "The task (has been|is now) (complete|done|finished)" -i
rg "Everything (is|looks) (good|fine|correct|working)" -i
rg "All (done|set|good|complete)" -i
```

**Signal**:
```text
The task has been completed successfully. Everything looks good!
All done — the feature is now working correctly.
```

**Why it matters**: "Everything looks good" is an assertion without evidence. Users cannot verify it. Fact-based completions include specific counts, file names, or test results that a user can independently check.

**Preferred action**:
```text
Fixed the null check in users.go:142. Tests pass (47/47). No other callers of `getUser()` affected.
```

---

### Excessive Caveats

**Detection**:
```bash
rg "please note that|it's worth noting|it should be mentioned|keep in mind" -i
rg "I would (recommend|suggest|advise) that you" -i
rg "you may want to (consider|think about|look into)" -i
```

**Signal**:
```text
Please note that this change may have implications you should be aware of.
It's worth noting that you may want to consider reviewing the downstream effects.
I would recommend that you carefully examine the results before proceeding.
```

**Why it matters**: Caveat stacking is a hedge against being wrong. If there's a genuine risk, state it specifically: "This migration is irreversible — verify with a dry-run before applying." Generic caveats train users to ignore all caveats, including the real ones.

**Preferred action**: State the specific risk or remove the caveat entirely.

---

## Error-Fix Mappings

| Output pattern | Root cause | Fix |
|---------------|------------|-----|
| Summary longer than the actual change | Over-explaining simple edits | Match summary length to change size: one-line fix → one-line report |
| Hedging on a certain fact | Confusing opinion with fact | State facts directly; use "I think" only for genuine uncertainty |
| Repeating the user's request back | Filler before the answer | Delete the restatement; start with the answer |
| Listing every file touched | Reporting mechanics not outcomes | Report what changed functionally, not the file list |
| Asking permission for obvious next steps | Uncertainty about autonomy | Execute obvious steps; ask only when direction is genuinely ambiguous |

---

## Correct Patterns

### Fact-Based Progress Report

State what happened, what the result is, what comes next. No adjectives describing quality.

```text
# BAD
I have successfully completed the first phase of the refactoring task!
The code has been beautifully restructured and everything looks great!

# GOOD
Extracted UserService into its own module (src/services/user.ts).
3 callers updated. Build passes.
```

---

### Minimal Orienting Statement

When starting a multi-step task, one sentence is sufficient. No "I will now" constructions.

```text
# BAD
Now I will begin by carefully reading the existing implementation to understand
the current state of the code before making any changes.

# GOOD
Reading the existing implementation.
```

---

### Specific Risk Statement

When a genuine risk exists, state it concretely rather than hedging generically.

```text
# BAD
Please note that this change may have some implications you should be aware of.
You may want to carefully consider the downstream effects.

# GOOD
This drops the `legacy_id` column — irreversible without a backup. Run
`pg_dump` before applying.
```

---

## Detection Commands Reference

```bash
# Self-congratulation
rg 'successfully (completed|finished|implemented|fixed|resolved)' -i

# Narration before tool calls
rg "I('m| am) (now |going to |about to )?(read|check|search|run)" -i
rg "Let me (now |first |quickly )?(read|check|look|run)" -i

# Difficulty inflation
rg "complex|challenging|sophisticated|non-trivial" -i --include="*.md"

# Hollow completions
rg "everything (is|looks) (good|fine|correct|working)" -i

# Generic caveats
rg "please note that|it's worth noting|you may want to consider" -i
```
