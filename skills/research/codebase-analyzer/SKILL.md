---
name: codebase-analyzer
promoted_to: research
description: "Compatibility stub for deterministic Go pattern measurement; new analysis routes through research."
user-invocable: false
allowed-tools: [Read, Bash]
context: fork
routing:
  triggers: [analyze codebase, discover patterns, style vector, code cartographer, pattern frequency, structural metrics]
  category: analysis
  pairs_with: [assessment, programming]
---

# Codebase Analyzer

This capability is promoted to `research`. Existing workflows may still run the bundled `cartographer.py`, `cartographer_omni.py`, or `cartographer_ultimate.py` for deterministic Go measurements. Treat their counts as observations: derive an enforceable local convention only from representative in-scope files, excluding generated/vendor code, and report sample size and frequency. Mixed patterns remain observations rather than rules.
