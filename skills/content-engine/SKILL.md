---
name: content-engine
description: "Repurpose source assets into platform-native social content."
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
routing:
  triggers:
    - repurpose this
    - adapt for social
    - turn this into posts
    - content from article
    - content from demo
    - content from doc
    - write variants for
    - social content from
    - platform variants
    - repurpose for
  pairs_with:
    - x-api
  category: content
  disambiguate: voice-writer
---

# Content Engine Skill

Repurpose anchor content into platform-native variants. Produces drafts only -- no API calls or publishing. Posting is handled by `x-api` (single platform) or `crosspost` (multi-platform).

Platform-native means each variant is written from scratch for its target: different register (conversational on X, professional on LinkedIn, punchy on TikTok), different structure (thread vs. long-form vs. short script vs. newsletter section), different hook style. Shortening the same text for each platform is not adaptation.

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| errors, error handling | `error-handling.md` | Loads detailed guidance from `error-handling.md`. |
| tasks related to this reference | `phase-playbook.md` | Loads detailed guidance from `phase-playbook.md`. |
| tasks related to this reference | `platform-specs.md` | Loads detailed guidance from `platform-specs.md`. |

## Instructions

### Phase 1: GATHER -- Collect Inputs Before Writing Anything

Establish everything needed to write platform-native variants. Do not begin writing until this phase completes.

**Required inputs:**

| Input | Description | If Missing |
|-------|-------------|------------|
| Source asset | Content being adapted (article, demo description, launch doc, insight, transcript) | Ask -- required |
| Target platforms | X, LinkedIn, TikTok, YouTube, newsletter -- one or many | Ask if not inferable |
| Audience | Builders, investors, customers, operators, general | Infer if strong signal; ask if ambiguous |
| Goal | Awareness, conversion, recruiting, authority, launch support, engagement | Infer from source if obvious; ask otherwise |
| Constraints | Character limits, brand voice notes, phrases to avoid | Skip if none stated |

**Gate**: Source asset present AND at least one target platform identified. Both missing means nothing to work with -- do not guess.

Produce only requested platforms. If the user says "turn this into an X thread", produce an X thread. Offer other platforms in Phase 5, but do not produce unrequested variants.

Do not write any content in this phase. Only collect and confirm inputs.

---

### Phase 2: EXTRACT -- Identify 3-7 Atomic Ideas

Identify discrete, postable units inside the source asset. Each atomic idea must stand alone on at least one platform without requiring knowledge of the source.

**Steps:**

1. Read the full source asset
2. Identify ideas that are:
   - Specific (concrete claim, result, observation, or instruction -- not a vague theme)
   - Standalone (no dependency on other ideas to be understood)
   - Relevant to the stated goal and audience
3. Rank by relevance to the stated goal
4. Write each atomic idea as one sentence maximum

Fewer than 3 ideas: source is very narrow -- proceed with what exists (minimum 1) and note in the output file. More than 7: asset lacks coherence -- ask the user which section to focus on.

See `${CLAUDE_SKILL_DIR}/references/phase-playbook.md` for the `content_ideas.md` output template.

**Gate**: Numbered atomic ideas saved to `content_ideas.md`. Each is specific and standalone. The file must exist before proceeding.

---

### Phase 3: DRAFT -- Write Platform-Native Variants

Write one draft per target platform, starting from the primary atomic idea as raw material.

Every draft must be written from scratch for its platform. Do not write one version and shorten for others. No two platform drafts may share a verbatim sentence. If the LinkedIn draft opens with "This article covers..." or the X tweet says "New post: [title]. Key points: 1, 2, 3", that is a summary, not an adaptation.

Apply platform-specific rules -- see `${CLAUDE_SKILL_DIR}/references/phase-playbook.md` for X, LinkedIn, TikTok, YouTube, and Newsletter register/hook/structure/length/hashtag/link/CTA rules, plus the `content_drafts.md` output template.

**Gate**: One draft per target platform saved to `content_drafts.md`. No two drafts share a verbatim sentence. The file must exist before proceeding.

---

### Phase 4: GATE -- Quality Check Before Delivery

Mechanically verify drafts before delivery. Both script checks must exit 0. The gate cannot be bypassed -- LLM self-assessment misses hype phrases in context and cannot do reliable verbatim comparison. Run the scripts.

#### Check 1: Hype Phrase Scan

```bash
python3 scripts/scan-negative-framing.py --mode hype --drafts content_drafts.md
```

See `${CLAUDE_SKILL_DIR}/references/phase-playbook.md` for banned hype phrases and replacement guidance.

**If exit non-zero**: Rewrite affected sections, save, re-run. Do not proceed until exit 0.

#### Check 2: Cross-Platform Verbatim Check

```bash
python3 scripts/scan-negative-framing.py --mode cross-platform --drafts content_drafts.md
```

Identifies any sentence appearing verbatim in two or more platform sections.

**If exit non-zero**: Rewrite the flagged sentence(s) in one platform -- platform-native, not a synonym swap. Re-run. Do not proceed until exit 0.

#### Secondary LLM Check (after scripts pass)

Once both scripts exit 0, verify:
- [ ] Each draft reads natively for its platform
- [ ] Every hook is strong and specific -- not a topic sentence or summary opener
- [ ] CTAs match the stated goal and platform norms
- [ ] No placeholder text that cannot be published as-is (flag, do not remove)

**Gate**: Both script checks exit 0. All LLM checklist items confirmed. Update `content_drafts.md` status from `DRAFT -- pending Phase 4 gate` to `READY`. Proceed only when gate passes.

---

### Phase 5: DELIVER -- Present Drafts with Posting Guidance

Hand off clean drafts with enough context for the user or a downstream skill to act immediately. See `${CLAUDE_SKILL_DIR}/references/phase-playbook.md` (Phase 5: Delivery Details) for delivery order, per-draft inclusions, downstream handoff table, optional behaviors, and artifact list.

---

## Error Handling

See `${CLAUDE_SKILL_DIR}/references/phase-playbook.md` for error cases: source too long, script flag unsupported, platform unspecified, ambiguous source, fewer than 3 ideas.

---

## References

| Signal | Load |
|--------|------|
| Phase 3 DRAFT -- writing platform variants | `references/platform-specs.md`, `references/phase-playbook.md` |
| Phase 4 GATE -- running quality checks | `references/phase-playbook.md`, `references/error-handling.md` |
| Script fails, gate won't pass, source errors | `references/error-handling.md` |
| Platform rules, character limits, posting norms | `references/platform-specs.md` |
| Delivery, handoff, artifact templates | `references/phase-playbook.md` |

- `${CLAUDE_SKILL_DIR}/references/platform-specs.md` -- Character limits, format rules, and posting norms per platform
- `${CLAUDE_SKILL_DIR}/references/phase-playbook.md` -- Full platform rules for Phase 3, banned hype phrases for Phase 4, error handling
- `${CLAUDE_SKILL_DIR}/references/error-handling.md` -- Gate failure recovery, script fallbacks, error-fix mappings, detection commands
- `scripts/scan-negative-framing.py` -- Negative framing and hype phrase detection
