# Error Handling Reference — Content Engine

> **Scope**: Recovery procedures when Phase 4 scripts fail, sources are malformed, or gate checks fail repeatedly
> **Version range**: all versions
> **Generated**: 2026-04-16

---

## Overview

The content-engine pipeline has two failure modes: artifact-level errors (source too long, no ideas extracted, platform unspecified) and gate-level errors (hype phrases detected, verbatim cross-platform sentences found, scripts unavailable). Artifact errors block forward progress and require asking the user. Gate errors require targeted rewrites, not full pipeline restarts.

---

## Pattern Catalog

### ❌ Restarting the Full Pipeline on Gate Failure

**Detection**:
```bash
# Repeated Phase headers in session artifacts signal a full restart occurred
grep -c "## Atomic Ideas" content_ideas.md
```

**What it looks like**: Deleting `content_ideas.md` and `content_drafts.md` and starting over when Phase 4 flags a single hype phrase.

**Why wrong**: Gate failures are surgical — one phrase in one draft. Restarting discards clean work from passing sections. The gate exists to target the failure, not trigger a full rewrite.

**Fix**: Identify the flagged section, rewrite only that sentence, re-run the script. Preserve all sections that passed.

---

### ❌ Skipping Script Gate and Substituting LLM Self-Assessment

**Detection**:
```bash
# Check if drafts were ever run through the gate (status field should say READY)
grep "Status:" content_drafts.md
# "DRAFT — pending Phase 4 gate" means gate was never run
```

**What it looks like**: "I've reviewed the drafts carefully and they look clean. Proceeding to Phase 5."

**Why wrong**: Self-assessment misses hype phrases embedded in context and cannot reliably detect verbatim cross-platform sentences. The scripts use exact string matching; LLMs use paraphrase matching — these produce different results.

**Fix**: Always run both script checks before Phase 5. If scripts are unavailable, use the manual fallback procedures below — do not skip the check.

---

### ❌ Treating Platform-Not-Specified as a Proceed-with-All Signal

**Detection**:
```bash
# Generic platform headers in drafts suggest unprompted multi-platform production
grep -cE "^## (X|LinkedIn|TikTok|YouTube|Newsletter)" content_drafts.md
# If count > platforms user asked for, drafts were overproduced
```

**What it looks like**: User says "make some social posts" with no platform specified; skill produces drafts for X, LinkedIn, TikTok, and Newsletter simultaneously without asking.

**Why wrong**: Each platform requires distinct register, length, and hook style. Producing all platforms without platform-specific intent produces content that fits none of them natively. It also creates ambiguity downstream about which drafts to actually publish.

**Fix**: Stop at Phase 1 gate. Ask: "Which platforms — X, LinkedIn, TikTok, YouTube, newsletter, or a subset?" Proceed only after the target is confirmed.

---

### ❌ Synonym-Swapping Instead of Platform-Native Rewrite on Verbatim Failure

**Detection**:
```bash
# Find sentences that appear verbatim across platform sections
grep -v "^#\|^---\|^$\|^Status:\|^Generated:\|^Primary" content_drafts.md | sort | uniq -d
```

**What it looks like**: LinkedIn draft opens with "We cut deploy time by 80%. Here's what changed." X thread also opens with "We cut deploy time by 80%. Here's what changed." Rewrite swaps "Here's" to "This is".

**Why wrong**: Synonym swaps preserve the same sentence structure, register, and cadence. A LinkedIn hook and an X hook serve different scroll-stopping functions and cannot share a sentence in any form — cross-platform readers notice the register mismatch even when words differ.

**Fix**: Rewrite the hook for the second platform from scratch, starting from the atomic idea (not from the other platform's draft). The two hooks should be unrecognizable as siblings.

---

## Manual Fallback Patterns (When Scripts Are Unavailable)

### Fallback for `--mode hype` Gate

When `scan-negative-framing.py --mode hype` fails or is unavailable:

```bash
# Run exact-match scan manually against content_drafts.md (case-insensitive)
grep -in \
  "excited to share\|thrilled to announce\|game-changing\|revolutionary\|groundbreaking\
\|don't miss out\|limited time\|unlock your potential\|dive into\|leverage\|synergy\
\|best-in-class\|world-class\|transformative\|disruptive" content_drafts.md
```

Each match is a hard rejection — do not soften or rephrase around the phrase. Replace the entire sentence with a specific result, number, counterintuitive claim, or observation.

```bash
# Verify clean after rewrite (should return no output)
grep -in "game-changing\|revolutionary\|transformative\|disruptive\|synergy\|leverage" content_drafts.md
```

Note in the Phase 5 delivery output that the automated gate was unavailable and manual fallback was used.

### Fallback for `--mode cross-platform` Gate

When `scan-negative-framing.py --mode cross-platform` is unavailable:

```bash
# Find lines appearing in two or more platform sections
grep -v "^#\|^---\|^$\|^Status:\|^Generated:\|^Primary\|^Subject" content_drafts.md \
  | sort | uniq -d
```

Non-empty output means a sentence appears verbatim in multiple platform sections. Rewrite it in one platform with platform-native register — not a synonym swap. Re-run the command to verify clean.

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|-------|------------|-----|
| `unrecognized arguments: --mode hype` | Script does not yet support `--mode` flag | Use manual `grep -in` fallback; note in delivery |
| `unrecognized arguments: --mode cross-platform` | Script does not yet support `--mode` flag | Use `uniq -d` fallback; note in delivery |
| Gate never exits 0 after 3 rewrites | Hype phrase is inside a quoted source block or attribution | Remove or rephrase the quoted material itself |
| `content_drafts.md: No such file or directory` | Phase 3 artifact was not saved before Phase 4 | Return to Phase 3, save the file, then re-run Phase 4 |
| Script exits 0 but delivery has hype phrase | Phrase was added in post-gate LLM edits | Re-run script after any edits made after the gate passed |
| Source yields 0 atomic ideas | Source is a URL, title, or one-sentence fragment without substance | Ask user for the full source content before proceeding |
| `content_ideas.md` has 1 idea but 5 platforms requested | Narrow source asset can't support multi-platform variation | Produce the strongest single-platform draft; offer others as optional in Phase 5 |
| Verbatim check flags subject line match | Newsletter subject line shares words with X hook | Subject line word matches in isolation don't fail the check — only full sentences |

---

## Detection Commands Reference

```bash
# Manual hype phrase scan (hard rejections, case-insensitive)
grep -in "excited to share\|thrilled to announce\|game-changing\|revolutionary\|groundbreaking\|don't miss out\|limited time\|unlock your potential\|dive into\|leverage\|synergy\|best-in-class\|world-class\|transformative\|disruptive" content_drafts.md

# Find verbatim sentences shared across platform sections
grep -v "^#\|^---\|^$\|^Status:\|^Generated:\|^Primary\|^Subject" content_drafts.md | sort | uniq -d

# Check gate status (should read READY before Phase 5)
grep "Status:" content_drafts.md

# Find unresolved placeholders before delivery
grep -E "\[URL\]|\[handle\]|\[date\]|\[title\]|\[name\]" content_drafts.md

# Verify content_ideas.md exists and has numbered ideas
grep -cE "^[0-9]+\." content_ideas.md 2>/dev/null || echo "ERROR: content_ideas.md missing or has no numbered ideas"

# Confirm expected platform sections exist in drafts
grep -E "^## (X|LinkedIn|TikTok|YouTube|Newsletter)" content_drafts.md
```

---

## See Also

- `references/phase-playbook.md` — Source-level error cases (source too long, fewer than 3 ideas, ambiguous source)
- `references/platform-specs.md` — Character limits and format constraints that trigger revision needs
