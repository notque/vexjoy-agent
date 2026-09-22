---
name: writing
description: "Writing: voice creation and validation, prose editing, anti-AI cleanup, professional communication, translation."
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
  - Agent
routing:
  force_route: true
  not_for: "code comments (use code-quality), API documentation (use docs-sync-checker), scheduling or calendaring content (use content), code review (use review)"
  triggers:
    - "write article"
    - "blog post"
    - "write in voice"
    - "voice pipeline"
    - "voice-writer"
    - "voice writer"
    - "validate voice"
    - "voice fidelity"
    - "write email"
    - "draft memo"
    - "executive summary"
    - "status update"
    - "meeting notes"
    - "pushback email"
    - "disagree professionally"
    - "translate"
    - "translation"
    - "localize"
    - "draft article"
    - "generate content"
    - "professional communication"
    - "draft response"
  category: content
  pairs_with:
    - joy-check
    - content
---

# Writing Skill

Five modes. Match the request to the correct mode and follow its section.

| Request matches | Mode |
|---|---|
| Article, blog post, content using a voice profile | Voice Writing |
| Build a voice profile from writing samples | Voice Creation |
| Check draft against voice profile fidelity | Voice Validation |
| Email, memo, status update, meeting notes, pushback | Professional Communication |
| Translate or localize a document | Translation |

## Deep References

| Signal | Load | Content |
|---|---|---|
| Narrative validation, 500+ word content | `references/narrative-patterns.md` | 13-check rubric (StoryScope-derived) |
| Professional-communication examples | `references/pc-examples.md` | Worked transformation examples |
| Professional-communication templates | `references/pc-templates.md` | Status templates, phrase transformations |
| Voice creation: pattern extraction | `references/cv-pattern-identification.md` | Phrase fingerprints, architectures |
| Voice creation: triple-validation | `references/cv-extraction-validation.md` | Recurrence/power/exclusivity rubric |
| Voice creation: skill file generation | `references/cv-skill-generation.md` | SKILL.md structure, frontmatter, samples |
| Voice creation: rules template | `references/cv-voice-rules-template.md` | Positive/contrastive identity, prohibitions |
| Voice creation: iteration and authorship | `references/cv-iteration-guide.md` | Validation commands, authorship matching |
| Voice creation: phase banners | `references/cv-phase-banners.md` | Progress reporting templates |
| Translation modes, chunking | `references/tr-modes.md` | Quick/normal/refined, parallel dispatch |
| Translation glossary | `references/tr-glossary-template.md` | Glossary format, term-preservation rules |

---

## Mode 1: Voice Writing

13-phase pipeline for voice-profiled articles and blog posts. Each phase runs as a separate agent dispatch. Phase artifacts are files in `.voice-phase/`, not context between agents.

Set `VOICE_WRITER_ACTIVE=1` before dispatching any phase agent.

### Phases

1. **LOAD**: Identify voice profile. Run `ls ~/.claude/skills/ | grep voice-` for available profiles. Read `profile.json`, all `references/`, and the target site's `CLAUDE.md`. Output: `.voice-phase/01-load.json`.

2. **GROUND**: Anchor in lived experience. Identify: core problem, personal experience, the "vex" (frustration) and "joy" (resolution), 3-5 concrete details, single reader takeaway. Output: `.voice-phase/02-grounding.md`.

3. **STATS-CHECKPOINT**: Extract target ranges from profile (sentence/paragraph length, pronoun density, contraction rate, banned patterns). Output: `.voice-phase/03-stats-baseline.json`.

4. **GENERATE**: Write the full draft in target voice. Apply narrative structure guidance: let evidence speak, mix emotional registers, weave secondary threads, leave room for uncertainty, reference specifically, vary intensity, include one unpredicted event, acknowledge the reader, vary temporal structure, close with forward motion, subvert one expectation. Target 1200-2000 words. Output: `.voice-phase/04-draft.md`.

5. **HOOK-GATE**: Check opening for at least one concrete number, specific date, or unexpected detail. Score 1-10. If < 8, pull the most surprising finding from the body into the opening. Max 3 attempts. Output: `.voice-phase/05-hook-score.json`.

6. **VALIDATE**: Call the Skill tool with `voice-validator` (or run Voice Validation below). Measure metrics against Phase 3 targets. Flag deviations > 1 stddev. Output: `.voice-phase/06-validation-report.json`.

7. **REFINE**: Fix failed metrics. Tighten prose. Verify code examples. Re-validate changed sections. Output: `.voice-phase/07-refined-draft.md`.

8. **VARIETY-GATE**: Sentence length clusters: short (1-7 words) 30-45%, medium (8-20) 35-50%, long (21+) 10-25%. Every paragraph 3 sentences or fewer. At least 1 single-sentence paragraph per 500 words. Variety score (stddev) >= 8.0. Max 3 attempts. Output: `.voice-phase/08-variety-score.json`.

9. **JOY-CHECK**: Call the Skill tool with `joy-check`. Ensure the article celebrates problem-solving, not grievance. Output: `.voice-phase/09-joy-report.json`.

10. **ANTI-AI**: Run the private de-AI editor skill. Strip generic transitions, hedge stacking, summary conclusions, self-narrating structure. Voice profile overrides anti-AI rules -- if a flagged pattern exists in the voice profile's corpus, preserve it. Output: `.voice-phase/10-antiai-report.json`.

11. **CLOSE-GATE**: Verify closing uses one of 5 modes (Honest Uncertainty, Practical Trailing Observation, Self-Deprecating Admission, Specific Next Step, Just Stops). Must not summarize, callback to opening, or use "In conclusion". Score >= 7. Max 3 attempts. Output: `.voice-phase/11-close-score.json`.

12. **OUTPUT**: Apply front matter, write to `content/posts/YYYY-MM-DD-slug.md`. Report all gate scores. Write `.voice-pipeline-complete` marker. Output: final file.

13. **CLEANUP**: Report word count, reading time, preview URL. Flag gates that required multiple attempts.

---

## Mode 2: Voice Creation

7-phase pipeline to build a voice profile from writing samples. Each phase has a gate. Report progress with phase banners (load `references/cv-phase-banners.md`).

### Phase 1: COLLECT (Gate: 50+ samples)

Gather 50+ writing samples across contexts and lengths. Mix sources: Reddit, HN, blog, forum, email, chat, social. Do not clean typos -- imperfections ARE the voice. Do not cherry-pick. Save to `skills/voice-{name}/references/samples/*.md`.

### Phase 2: EXTRACT (Gate: profile.json valid, script exit 0)

Run deterministic analysis:

```bash
python3 ~/.claude/scripts/voice-analyzer.py analyze \
  --samples skills/voice-{name}/references/samples/*.md \
  --output skills/voice-{name}/profile.json
```

Add stylometry bands: `python3 scripts/voice-stylometry.py band --samples skills/voice-{name}/references/samples/*.md`. Merge into `profile.json`.

### Phase 3: PATTERN (Gate: 10+ phrase fingerprints, 3+ thinking patterns, 2/4 architectures)

Identify distinctive patterns from samples + profile.json. Load `references/cv-pattern-identification.md` for phrase fingerprints, thinking patterns, wabi-sabi markers, and linguistic architectures. Apply triple-validation rubric from `references/cv-extraction-validation.md`: every pattern must pass cross-domain recurrence, generative power, and distinguishing exclusivity. Verdict: KEEP / FOOTNOTE / DROP.

### Phase 4: RULE (Gate: 4+ positive traits, 6+ contrastive aspects, 3+ prohibitions)

Transform KEEP/FOOTNOTE patterns into rules. Load `references/cv-voice-rules-template.md`. Build: positive identity (with dampening adverbs), contrastive table (This Voice vs Generic AI), hard prohibitions, wabi-sabi rules, anti-essay patterns, architectural patterns.

### Phase 5: GENERATE (Gate: SKILL.md 2000+ lines, samples 400+ lines)

Generate the voice skill files. Load `references/cv-skill-generation.md`. Create `skills/voice-{name}/SKILL.md` and `config.json`. Most line count is SAMPLES, not rules (V7-V9 failed with rules-only; V10 passed with 100+ samples).

### Phase 6: VALIDATE (Gate: score >= 60, 0 errors)

Generate 3 test pieces (short, medium, long). Run:

```bash
python3 ~/.claude/scripts/voice-validator.py validate \
  --content /tmp/voice-sample-{name}-{N}.md \
  --profile skills/voice-{name}/profile.json --voice {name} --format text --verbose
python3 ~/.claude/scripts/voice-validator.py check-banned \
  --content /tmp/voice-sample-{name}-{N}.md --voice {name}
```

If validation flags natural imperfections as errors, adjust config.json thresholds, not the content. Max 3 iterations.

### Phase 7: ITERATE (Gate: 4/5 authorship match)

Authorship matching: present hold-out samples mixed with generated samples to 5 roasters. Target: 4/5 say SAME AUTHOR. Load `references/cv-iteration-guide.md` for the full procedure. If failing, add more samples (not more rules). Max 3 iterations.

---

## Mode 3: Voice Validation

Critique-and-rewrite loop for voice fidelity. Max 3 iterations: scan, revise, rescan.

### Phase 1: IDENTIFY TARGET

Determine voice profile, mode, and content to validate. Load the target voice's checklist.

### Phase 2: SCAN

**Step 0**: Run deterministic stylometry checks if the voice has a `profile.json`:

```bash
python3 scripts/voice-stylometry.py check \
  --profile skills/voice-{name}/profile.json --draft <content-file>
```

Checks: burstiness band, punctuation profile, corrective antithesis, temporal openers, uniform paragraph shapes, profile decay.

**Step 1**: Run negative prompt checklist across all categories: Tone, Structure, Sentences, Language (ban: amazing, terrible, revolutionary, perfect, game-changing, transformative, incredible, outstanding, exceptional, groundbreaking), Emotion, Questions, Metaphors. For 500+ word content, add Narrative category (load `references/narrative-patterns.md`).

**Step 2**: Check pass conditions: feels human-written, voice-specific patterns present, could NOT be posted on LinkedIn without edits (for casual voices).

**Step 3**: Document each violation with: category, quoted text, fix recommendation.

### Phase 3: REVISE

Apply the smallest change that resolves each violation. Preserve meaning. Keep substance and arguments intact.

### Phase 4: VERIFY

Rescan revised content. If PASS: output with validation report. If FAIL and iteration < 3: return to Phase 3. If FAIL and iteration = 3: output with flagged concerns.

---

## Mode 4: Professional Communication

Transform dense technical communication into structured business formats.

### Phase 1: PARSE

Classify input type (technical update, debugging narrative, status report, dependency discussion). Extract ALL propositions: facts, implications, temporal markers, system references, blockers, emotional context. Document implicit context. Count propositions.

### Phase 2: STRUCTURE

Categorize propositions: Status, Actions, Impacts, Blockers, Next. Prioritize by business impact: Business Impact > Technical Functionality > Timeline > Resources > Risk.

### Phase 3: TRANSFORM

Apply standard template (load `references/pc-templates.md` for full library):

```
STATUS: GREEN|YELLOW|RED
KEY POINT: [single most important takeaway]
Summary: [3 bullets: accomplishment/issue + impact]
Technical Details: [2-3 sentences]
Next Steps: [specific actions with verb, scope, owner, timeline]
```

Tone rules: strip hedging, transform defensive language, preserve urgency markers, keep technical terms intact. Status: GREEN (complete, no follow-up), YELLOW (resolved with follow-up or blocked), RED (active critical issue). Always document reasoning.

### Phase 4: VERIFY

Compare output against extracted propositions -- zero information loss. Verify technical accuracy. Confirm status matches severity. Validate action items have (verb, scope, owner, timeline). Check detail level for audience.

---

## Mode 5: Translation

Translate documents using three modes: quick (single-pass), normal (analyze-then-translate), refined (full pipeline with polish). Core principle: rewrite as a skilled native writer, not word-for-word conversion.

### Phase 1: DETECT AND PREPARE

Infer mode: "quick/fast/draft" = quick; "professional/polished/refined" = refined; default = normal. Detect source and target languages. Flag documents > 2000 words for chunked parallel translation. Load `references/tr-modes.md`.

### Phase 2: ANALYZE (skip in quick mode)

Identify: language/dialect, register (academic/technical/narrative/marketing/casual/legal), document type, specialized terminology. For technical content, build glossary (load `references/tr-glossary-template.md`).

### Phase 3: TRANSLATE

Translation principles: use idiomatic target-language word order; break long source sentences at natural target-language pauses; render metaphors by intent, not literally; annotate specialized terms on first use; match register from Phase 2; preserve proper nouns and brand names.

For documents > 2000 words: split at heading/paragraph boundaries, build session glossary, dispatch parallel subagent calls per chunk with glossary injected, reassemble, check term consistency.

### Phase 4: POLISH (refined mode only)

Scan for register inconsistency. Rewrite literal-sounding constructions. Audit specialized term handling.

### Phase 5: DELIVER

Report: source, target, mode, word count, chunks, untranslated terms.
