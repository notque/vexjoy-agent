# Create Voice — Phase Status Banners

Report progress at each phase gate using these banner templates. Be direct about what passed or failed, not congratulatory.

## Phase 1/7: COLLECT

```
Phase 1/7: COLLECT
  Samples: {count} across {file_count} files
  Sources: {list of source types}
  GATE: {PASS if >= 50 / FAIL if < 50}
```

## Phase 2/7: EXTRACT

```
Phase 2/7: EXTRACT
  Profile: skills/voice-{name}/profile.json
  Samples analyzed: {N}
  Total words: {N}
  Total sentences: {N}
  Average sentence length: {X} words
  GATE: {PASS/FAIL}
```

## Phase 3/7: PATTERN

```
Phase 3/7: PATTERN
  Phrase fingerprints: {count}
  Thinking patterns: {count}
  Linguistic architectures: {count}/4 documented
  Length distribution: {very short}% / {short}% / {medium}% / {long}%
  Natural typos: {count}
  Wabi-sabi markers: {list}
  GATE: {PASS/FAIL}
```

## Phase 4/7: RULE

```
Phase 4/7: RULE
  Positive traits: {count} (with dampening)
  Contrastive aspects: {count}
  Hard prohibitions: {count}
  Wabi-sabi rules: {count}
  Anti-essay patterns: {list}
  Architectural patterns: {count}
  GATE: {PASS/FAIL}
```

## Phase 5/7: GENERATE

```
Phase 5/7: GENERATE
  SKILL.md: {line_count} lines
  Samples section: {line_count} lines
  config.json: created
  Template sections: {present_count}/{required_count}
  GATE: {PASS/FAIL}
```

## Phase 6/7: VALIDATE

```
Phase 6/7: VALIDATE
  Test 1 (short): {score}/100 - {PASS/FAIL}
  Test 2 (medium): {score}/100 - {PASS/FAIL}
  Test 3 (long): {score}/100 - {PASS/FAIL}
  Banned patterns: {CLEAN/violations found}
  Iterations: {N}/3
  GATE: {PASS/FAIL}
```

## Phase 7/7: ITERATE

```
Phase 7/7: ITERATE
  Authorship match: {X}/5 roasters
  Iterations completed: {N}
  Final validation score: {X}/100
  GATE: {PASS/FAIL}
```

## Final Output

After all phases complete:

```
===============================================================
 VOICE CREATION COMPLETE: {name}
===============================================================
 Files created:
   skills/voice-{name}/SKILL.md              (voice skill)
   skills/voice-{name}/profile.json          (metrics)
   skills/voice-{name}/config.json           (validation config)
   skills/voice-{name}/references/samples/   (organized samples)

 Validation: {PASSED/FAILED} (score: {X}/100)
 Authorship Match: {X}/5 roasters
===============================================================
```
