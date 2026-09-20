---
name: content-engine
promoted_to: content
description: "Repurpose a supplied source into distinct, platform-native drafts; never publishes."
user-invocable: false
allowed-tools: [Read, Write, Bash, Grep, Glob, Edit]
routing:
  triggers: ["repurpose this", "adapt for social", "turn this into posts", "platform variants"]
  pairs_with: [content]
  category: content
  disambiguate: voice-writer
---

# Content engine

Require the source asset and target platform(s); ask only when either cannot be
inferred. Respect the requested platforms and goal—this skill creates drafts,
not API calls or publishing actions.

Extract the few standalone claims, observations, or results that carry the
source. Draft each platform version independently from those facts rather than
shortening one master version. Preserve factual meaning, user voice constraints,
and unresolved placeholders. Do not invent proof, metrics, reactions, or links.

Before delivery:

1. Enforce current platform hard limits using authoritative/live information
   when a limit matters; do not rely on stored growth folklore or posting-time
   claims.
2. Remove generic announcement/hype language in favor of source-specific facts.
3. Check that no complete sentence is duplicated across platform variants.
4. Flag placeholders and identify which draft is recommended for the stated goal.
