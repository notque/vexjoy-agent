---
name: writing
description: "Write or validate voice-matched prose, derive a reusable voice from samples, reshape technical notes for an audience, or translate while preserving terminology."
user-invocable: true
allowed-tools: [Read, Write, Bash, Grep, Glob, Edit, Task, Skill, Agent]
routing:
  force_route: true
  not_for: "code comments, API documentation, scheduling content, or code review"
  triggers: [write article, blog post, write in voice, voice pipeline, voice-writer, voice writer, create voice, new voice, voice from samples, validate voice, voice fidelity, write email, draft memo, executive summary, status update, meeting notes, pushback email, disagree professionally, translate, translation, localize, draft article, generate content, professional communication, draft response]
  category: content
  pairs_with: [joy-check, content]
---

# Writing

Choose one mode. Preserve claims and user-supplied facts in every mode; do not invent evidence to improve fluency.

## Voice-matched writing

Load the requested voice profile, its measured profile, and only the references it routes to. Ground the piece in supplied source material, then draft. Validate against that profile and revise failed dimensions without normalizing authentic irregularities. A generic anti-AI rule never overrides a corpus-backed voice feature.

When a profile includes executable validators, run them and report their actual findings. For longer narrative work, check for monotonous structure only where the target corpus does not exhibit it; there is no universal requirement for reader address, surprise, paragraph length, or a particular closing.

## Voice creation

Read `references/voice-creation.md`. Separate a held-out set before deriving the profile. Quantitative style belongs in `profile.json`; qualitative rules require cited, recurring evidence. The generated profile should contain enough representative excerpts to demonstrate the voice, not arbitrary instruction or line-count padding.

## Voice validation

Run the target profile's deterministic checks first. Then cite each mismatch, make the smallest meaning-preserving revision, and rescan. Stop after three passes and disclose remaining mismatches. Treat a validator that rejects the source author's real held-out writing as miscalibrated; do not “fix” the author to satisfy it.

## Professional communication

Extract the propositions before rewriting: facts, uncertainty, impact, blockers, decisions, owners, and dates. Choose structure for the audience and request rather than forcing every message into a status template. Never strengthen a hypothesis into a root cause or manufacture an owner/timeline. For operational updates, make unresolved actions and their ownership visibly distinct from background detail.

## Translation and localization

Match target-language register and idiom while preserving meaning, identifiers, formatting, and uncertainty. For a long or terminology-heavy document, read `references/translation.md`. Reassemble chunks in source order and run a document-wide terminology pass; independently fluent chunks are not a consistent translation.

Deliver the requested artifact, plus only consequential assumptions, untranslated terms, or validation failures.
