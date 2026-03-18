---
name: python-doc-generator
description: |
  Generate comprehensive technical documentation for a Python source file.
  Uses AST extraction, parallel multi-agent research (4 agents), structured
  generation, and deterministic verification.
version: 2.0.0
route_to:
  agent: python-general-engineer
  skill: python-doc-generator
  enhancements:
    - verification-before-completion
trigger:
  keywords:
    - document python
    - generate python docs
    - python doc pipeline
    - document script
    - document hook
parameters:
  required:
    - name: source
      description: Path to the Python file to document (e.g., scripts/feature-state.py)
  optional:
    - name: output
      description: Path for the output documentation file (default: alongside source as {name}-docs.md)
    - name: deep
      description: Include private functions and internal architecture (default: false)
      default: "false"
    - name: quick
      description: Skip research and verification for draft-quality output (default: false)
      default: "false"
---

# python-doc-generator

Entry point command for the Python Documentation Generator pipeline.

## Usage

```
/do document python scripts/feature-state.py
/do generate python docs for hooks/error-learner.py
/do document hook hooks/retro-knowledge-injector.py
```

## What It Does

1. **ADR** (Phase 0): Creates a persistent reference document for the documentation task.
2. **Extract** (Phase 1, `python-doc-verifier.py extract`): AST-parses the source file to inventory all functions, classes, constants, and CLI entry points deterministically.
3. **Research** (Phase 2, parallel multi-agent): Dispatches 4 research agents in parallel to investigate code architecture, usage patterns, ecosystem context, and output examples. This breadth of research produces richer examples and more complete documentation than sequential search.
4. **Outline** (Phase 3, template selection): Selects the appropriate documentation template (CLI tool, utility library, hook, data layer) and maps every public element to an outline section.
5. **Generate** (Phase 4, structured writing): Writes each section following the outline, grounded in source code and research.
6. **Verify** (Phase 5, `python-doc-verifier.py verify`): Validates generated docs against source -- checks function coverage, argument documentation, structural quality, and accuracy.
7. **Output** (Phase 6): Delivers final documentation with verification report. Cleans up temporary files.

## Components

| Component | Path | Purpose |
|-----------|------|---------|
| Skill | `skills/python-doc-generator/SKILL.md` | 7-phase pipeline with parallel research |
| Script | `scripts/python-doc-verifier.py` | AST extraction + deterministic verification |
| Reference | `skills/python-doc-generator/references/doc-templates.md` | Templates per module type |
| Agent | `agents/python-general-engineer.md` | Python domain expertise (reused) |

## Verification Script

The pipeline uses `scripts/python-doc-verifier.py` for deterministic validation:

```bash
# Extract documentable elements
python3 scripts/python-doc-verifier.py extract --source FILE.py --human

# Verify docs against source
python3 scripts/python-doc-verifier.py verify --source FILE.py --doc DOC.md --human

# Check doc structure quality
python3 scripts/python-doc-verifier.py check-structure --doc DOC.md --human
```

## Routing

Routes to `python-general-engineer` with the `python-doc-generator` skill (`skills/python-doc-generator/SKILL.md`). The pipeline is self-contained and produces a verification report alongside the documentation.
