# Generation Checklist

Full reference for Phase 3 (GENERATE) of the voice-writer pipeline.

---

## Full Generation Checklist

- [ ] Sentence length varies according to profile distribution
- [ ] Contractions match target rate
- [ ] No em-dashes (use commas, periods, or restructure)
- [ ] Opening matches voice pattern signatures
- [ ] Closing matches voice pattern signatures
- [ ] Transition words from profile preferred list
- [ ] Banned patterns avoided (exploration verbs, corporate jargon)
- [ ] Banned words avoided (scan against `references/banned-words.md`)
- [ ] Argument builds in documented direction (if architectural patterns present)
- [ ] Concessions use documented structure and pivot markers (if applicable)
- [ ] Analogies drawn from documented domains only (if applicable)
- [ ] Specific numbers included for all claims, not vague adjectives

---

## Architectural Patterns Application Rules

When the voice skill has an `## Architectural Patterns` section, apply these rules:

- **Argument flow**: Build the piece using the documented direction (inductive/deductive/mixed). If inductive, lead with evidence and land the claim late. If deductive, open with the claim.
- **Concessions**: When handling disagreement, follow the documented concession structure and use the documented pivot markers — not generic "however" or "on the other hand."
- **Analogy domains**: Draw analogies ONLY from the documented source domains. Do NOT use generic analogies from undocumented domains.
- **Bookends**: Open with the documented opening move, close with the documented closing move.

If the voice skill has no `## Architectural Patterns` section, skip this step entirely.

---

## Em-Dash Prohibition

NEVER generate em-dashes in any voice output. Em-dashes are the most reliable AI marker. Use commas, periods, or restructure sentences instead.

This applies to all voices, all modes, all content types. No exceptions.

---

## Step 4b Detail: Architectural Patterns Check

Before writing, explicitly check the loaded voice SKILL.md for an `## Architectural Patterns` section. If it exists:

1. Note the argument direction (inductive / deductive / mixed)
2. Copy out the documented pivot markers for concessions
3. List the documented analogy domains
4. Note the opening move and closing move for bookends

Apply these throughout generation — do not revert to generic patterns partway through.

---

## Important Constraints

- **Single voice per piece**: Do not blend voice patterns. Use exactly one voice profile per piece and follow that voice skill's patterns exclusively.
- **No over-engineering**: Generate the content the user requested, nothing more. Do not add features, modes, or structure the user did not request.
- **Preview before write**: Display full draft for approval before writing to file unless Direct Write Mode is enabled.
