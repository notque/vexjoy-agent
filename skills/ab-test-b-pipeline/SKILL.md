---
name: python-doc-generator
description: |
  Generate comprehensive technical documentation for a Python source file using
  AST extraction, parallel multi-agent research, structured generation, and
  deterministic verification. Supports CLI tools, utility libraries, hooks, and
  data layer modules. Use for "document python", "generate python docs",
  "document script", or "document hook".
version: 2.0.0
user-invocable: false
agent: python-general-engineer
model: opus
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
---

# Python Documentation Generator

## Operator Context

This skill operates as an operator for Python documentation generation, configuring Claude's behavior for producing structured, verified technical documentation grounded in source code analysis and codebase-wide research. It implements a **Pipeline** pattern -- Extract, Research, Outline, Generate, Verify, Output -- with deterministic validation gates.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md files before execution
- **Over-Engineering Prevention**: Document what exists in the source code. Do not invent features, speculate about future capabilities, or add content not grounded in the actual implementation.
- **Source-Grounded Writing**: Every claim in the documentation must trace to either AST extraction data or codebase research findings. No hallucinated function signatures, invented parameters, or fabricated behavior.
- **Deterministic Verification**: Phase 5 uses `scripts/python-doc-verifier.py` for machine verification. Documentation must pass with score >= 70% and zero accuracy issues. This is non-negotiable.
- **Parallel Research Mandate**: Phase 2 MUST dispatch 4 parallel research agents. Sequential grep-based research is banned (Architecture Rule 12).

### Default Behaviors (ON unless disabled)
- **Communication Style**: Report facts without self-congratulation. Show verification scores and file paths.
- **Temporary File Cleanup**: Remove `/tmp/research-*.md` and `/tmp/extract-*.json` artifacts after completion. Keep only the final documentation file.
- **Module Type Detection**: Classify source as CLI tool, utility library, hook, or data layer and select the matching documentation template.
- **Code Block Inclusion**: Include working code examples showing actual usage patterns discovered during research.

### Optional Behaviors (OFF unless enabled)
- **Deep Mode** (`--deep`): Include private functions and internal architecture details
- **Quick Mode** (`--quick`): Skip research and verification for draft-quality output
- **Custom Output Path** (`--output PATH`): Override default output location

## What This Skill CAN Do
- Extract all documentable elements from Python source via AST (functions, classes, constants, CLI interface)
- Research how the module is used across the codebase via parallel multi-agent dispatch
- Generate structured documentation with overview, API reference, examples, and architecture sections
- Verify generated docs deterministically against source code
- Classify modules and apply type-specific documentation templates (CLI, library, hook, data layer)
- Produce a verification report alongside the documentation

## What This Skill CANNOT Do
- **Document non-Python files**: Only `.py` files are supported
- **Generate tutorials or guides**: Produces reference documentation, not learning material
- **Modify source code**: Read-only analysis of the target file
- **Replace domain expertise**: The documentation reflects what the code does, not what it should do

## Instructions

### Phase 0: ADR

**Goal**: Create a persistent reference document before work begins.

**Step 1**: Create `adr/python-doc-{module-name}.md` with:
- Context: Which module is being documented and why
- Decision: Which documentation template applies (CLI, library, hook, data layer)
- Constraints: Module complexity, public API size, CLI interface presence
- Test Plan: Verification score target (>= 70%, 0 accuracy issues)

**Step 2**: Re-read the ADR before every major decision to prevent context drift.

**Gate**: ADR file exists. Proceed to Phase 1.

### Phase 1: EXTRACT

**Goal**: Build a deterministic inventory of all documentable elements in the source file.

**Step 1**: Run the extraction script:
```bash
python3 scripts/python-doc-verifier.py extract --source {source_file} --human
```

This produces an AST-based inventory of:
- Module docstring
- Public functions (name, args, returns, decorators, docstrings)
- Private functions (count and names)
- Classes (name, bases, methods, dataclass status)
- Module-level constants (UPPER_CASE)
- CLI detection (argparse, `__main__` guard, shebang)

**Step 2**: Also run the JSON extraction for machine consumption:
```bash
python3 scripts/python-doc-verifier.py extract --source {source_file} > /tmp/extract-{module-name}.json
```

**Step 3**: Classify the module type based on extraction results:

| Signal | Module Type | Template |
|--------|-------------|----------|
| `has_cli_entry: true` + `has_argparse: true` | CLI Tool | `references/doc-templates.md#cli-tool` |
| No CLI entry + multiple public functions | Utility Library | `references/doc-templates.md#utility-library` |
| Located in `hooks/` + uses `hook_utils` | Hook | `references/doc-templates.md#hook` |
| Primarily classes + data models | Data Layer | `references/doc-templates.md#data-layer` |

**Step 4**: Read the source file directly to capture details AST misses (inline comments, magic strings, environment variable usage, file I/O patterns).

**Step 5**: Save extraction summary to `/tmp/extract-{module-name}-summary.md` with:
- Module type classification
- Public API count (functions + classes + constants)
- CLI subcommands (if applicable)
- Key imports and dependencies

**Gate**: Extraction JSON exists at `/tmp/extract-{module-name}.json`. Module type classified. Summary saved. Proceed to Phase 2.

### Phase 2: RESEARCH (Parallel Multi-Agent)

**Goal**: Discover how the module is actually used in the codebase. Research breadth directly determines the quality of examples and completeness of the final documentation.

**IMPORTANT**: This phase MUST use parallel multi-agent dispatch per Architecture Rule 12. Sequential grep is banned. The A/B test (Round 1) proved that sequential research produces a 1.40-point Examples gap and 0.60-point Completeness gap vs parallel research.

**If `--quick` is set**: Skip this phase entirely. Proceed to Phase 3 with extraction data only.

**Step 1: Prepare shared research context**

Assemble a context block from Phase 1 artifacts to give all research agents common grounding:

```
SHARED CONTEXT FOR RESEARCH AGENTS:
- Module: {source_file}
- Type: {module_type} (CLI tool | utility library | hook | data layer)
- Public API: {list of public function names and class names}
- Constants: {list of constant names}
- CLI subcommands: {list if applicable, or "N/A"}
- Key imports: {list of imports}
- Module docstring: {first 200 chars}
```

**Step 2: Dispatch 4 parallel research agents**

Launch all 4 agents simultaneously using the Task tool. Each agent receives the shared context block and saves findings to a separate artifact file. Each has a 5-minute timeout.

**Agent 1: Code Analysis** -- Internal architecture, data flow, algorithms
- Read the full source file
- Map the call graph between functions (which functions call which)
- Identify data flow patterns (input -> transform -> output)
- Note error handling patterns and edge cases
- Document any non-obvious algorithms or business logic
- Save to `/tmp/research-code-analysis.md`

**Agent 2: Usage Patterns** -- Importers, callers, real-world invocation examples
- Search for all files that import from this module: `from {module} import` and `import {module}`
- For each importer, read the relevant code sections to understand HOW the module is called
- Capture actual argument values used in real invocations
- Note which public functions are most/least used
- Identify common calling patterns (e.g., always called inside a try/except, always with specific args)
- Save to `/tmp/research-usage-patterns.md`

**Agent 3: Ecosystem/Context** -- Related modules, configuration, system role, tests
- Find related modules in the same directory or package
- Check for test files that exercise this module
- Look for configuration files or environment variables the module depends on
- Determine the module's role in the larger system architecture
- Find any documentation that already references this module (READMEs, CLAUDE.md, ADRs)
- Save to `/tmp/research-ecosystem.md`

**Agent 4: Output/Examples** -- Return values, output shapes, concrete examples
- For CLI tools: run `--help` if possible, capture actual output format
- For functions: find concrete return values in test files or callers
- Collect real-world examples of the module being used successfully
- Identify output formats (JSON, plain text, structured data)
- Find error outputs and edge case behaviors
- Save to `/tmp/research-examples.md`

**Step 3: Collect and merge research artifacts**

After all agents complete, read all 4 artifact files and merge into a single research compilation at `/tmp/research-compilation-{module-name}.md` organized by:
1. Architecture & Data Flow (from Agent 1)
2. Usage Patterns & Callers (from Agent 2)
3. System Context & Related Modules (from Agent 3)
4. Concrete Examples & Output Shapes (from Agent 4)

**Gate**: At least 3 of 4 research agents completed successfully. Research compilation saved to `/tmp/research-compilation-{module-name}.md`. Proceed to Phase 3.

### Phase 3: OUTLINE

**Goal**: Map every documentable element to an outline section using the appropriate template.

**Step 1**: Read the documentation template for the classified module type from `skills/ab-test-b-pipeline/references/doc-templates.md`.

**Step 2**: Create an outline that maps:
- Every public function to an API Reference subsection
- Every class to a Class Reference subsection
- Every CLI subcommand to a Usage subsection (CLI tools)
- Every constant to a Configuration/Constants subsection
- Research findings to Examples and Architecture sections

**Step 3**: Verify outline completeness -- every public name from the extraction JSON must appear in at least one outline section.

**Step 4**: Save the outline to `/tmp/outline-{module-name}.md`.

**Gate**: Outline covers 100% of public API names. Outline saved. Proceed to Phase 4.

### Phase 4: GENERATE

**Goal**: Write each documentation section following the outline, grounded in extraction data and research findings.

**Step 1**: Read the full source file one more time for fresh context.

**Step 2**: Read the research compilation from `/tmp/research-compilation-{module-name}.md`.

**Step 3**: Read the outline from `/tmp/outline-{module-name}.md`.

**Step 4**: Write the documentation following the outline structure. For each section:

**Overview section**:
- One-paragraph purpose statement derived from module docstring and ecosystem research
- Key capabilities as bullet points
- Module type context (what kind of module this is and where it fits)

**Quick Start / Usage section** (CLI tools):
- Most common invocation pattern (from usage research)
- All subcommands with brief descriptions
- Complete argument reference with types and defaults

**API Reference section** (all types):
- Every public function with: signature, description, parameters table, return value, raises
- Every class with: purpose, constructor, public methods
- Use actual docstrings when available; supplement with source analysis when not

**Examples section**:
- At least one example per major public function or CLI subcommand
- Use REAL examples discovered during research (Agent 2 and Agent 4 findings)
- Include code blocks with proper language markers
- Show both typical usage and edge cases

**Architecture section** (if module is Medium+ complexity):
- Internal data flow (from Agent 1 research)
- Key design decisions (from code analysis)
- Relationships to other modules (from Agent 3 research)

**Error Handling section** (if module handles errors):
- Exit codes (CLI tools)
- Exceptions raised (libraries)
- Error recovery patterns

**Step 5**: Write the complete documentation to the output path (default: `{source_dir}/{module_name}-docs.md` or user-specified `--output` path).

**Gate**: Documentation file written. All outline sections populated. Proceed to Phase 5.

### Phase 5: VERIFY

**Goal**: Validate generated documentation against source code deterministically.

**Step 1**: Run structural check:
```bash
python3 scripts/python-doc-verifier.py check-structure --doc {output_path} --human
```

**Step 2**: Run full verification against source:
```bash
python3 scripts/python-doc-verifier.py verify --source {source_file} --doc {output_path} --human
```

**Step 3**: Evaluate results:
- If score >= 70% AND 0 accuracy issues: **PASS** -- proceed to Phase 6
- If score < 70% OR accuracy issues found: **FIX** -- address each issue:
  - Missing functions: Add documentation for each
  - Missing classes: Add documentation for each
  - Missing constants: Add to Configuration/Constants section
  - Undocumented args: Add parameter descriptions
  - Structure issues: Add missing sections (overview, examples, headers)
  - Accuracy issues: Correct function signatures and parameter names

**Step 4**: After fixes, re-run verification. Maximum 2 fix cycles to prevent infinite loops.

**Step 5**: Run verification one final time in JSON mode for the report:
```bash
python3 scripts/python-doc-verifier.py verify --source {source_file} --doc {output_path}
```

**Gate**: Verification passes (score >= 70%, 0 accuracy issues). Or max 2 fix cycles exhausted (report final score). Proceed to Phase 6.

### Phase 6: OUTPUT

**Goal**: Deliver final documentation with verification report.

**Step 1**: Clean up temporary files:
- `/tmp/extract-{module-name}.json`
- `/tmp/extract-{module-name}-summary.md`
- `/tmp/research-code-analysis.md`
- `/tmp/research-usage-patterns.md`
- `/tmp/research-ecosystem.md`
- `/tmp/research-examples.md`
- `/tmp/research-compilation-{module-name}.md`
- `/tmp/outline-{module-name}.md`

**Step 2**: Report the results:

```
## Documentation Generated

**Source**: {source_file}
**Output**: {output_path}
**Module Type**: {type}

### Verification
- Score: {score}%
- Functions documented: {count}/{total}
- Classes documented: {count}/{total}
- Constants documented: {count}/{total}
- Structure: {pass/fail}
- Accuracy issues: {count}

### Research Coverage
- Research agents completed: {N}/4
- Importers found: {count}
- Test files found: {count}
- Related modules: {count}
```

**Gate**: Documentation delivered. Temporary files cleaned. Pipeline complete.

## Error Handling

### Error: Source File Not Found
**Cause**: The provided `--source` path does not exist
**Solution**: Verify the path is correct. Use `ls` or `glob` to find the file. Report the error to the user.

### Error: AST Parse Failure
**Cause**: The source file has syntax errors preventing AST parsing
**Solution**: The extraction script reports `SYNTAX ERROR` in the module docstring. Document what can be extracted from raw text analysis. Note the syntax error in the documentation.

### Error: Research Agent Timeout
**Cause**: A research agent exceeds the 5-minute timeout
**Solution**: The gate requires only 3 of 4 agents to complete. If 2+ fail, fall back to single-agent sequential research for the missing aspects. Note reduced research coverage in the output report.

### Error: Verification Score Too Low
**Cause**: Generated documentation misses significant public API elements
**Solution**: Check the verification JSON for specific missing items. Add them in the fix cycle. If the module has an unusually large public API, consider that some private-looking functions may be public.

## Anti-Patterns

### Anti-Pattern 1: Hallucinated Functions
**What it looks like**: Documentation describes functions or parameters that do not exist in the source
**Why wrong**: Creates misleading documentation that causes user errors
**Do instead**: Ground every function reference in the AST extraction JSON. If it is not in the extraction, it does not go in the docs.

### Anti-Pattern 2: Sequential Research
**What it looks like**: Running `grep` commands one at a time to find usage patterns
**Why wrong**: Sequential search produces tunnel vision -- each search informs the next, narrowing coverage. A/B testing proved this creates a 1.40-point gap in Examples quality.
**Do instead**: Dispatch 4 parallel research agents per Phase 2 instructions. Each explores independently for broader coverage.

### Anti-Pattern 3: Generic Examples
**What it looks like**: Examples that show `function(arg1, arg2)` without real values
**Why wrong**: Generic examples do not help users understand actual usage patterns
**Do instead**: Use real examples discovered during research -- actual argument values, actual calling contexts, actual output shapes.

### Anti-Pattern 4: Skipping Verification
**What it looks like**: Writing documentation and delivering it without running `python-doc-verifier.py`
**Why wrong**: Documentation may miss public functions, contain wrong signatures, or lack required sections
**Do instead**: Always run verification in Phase 5. Fix issues found. Report the final score.

## References

- **Verification Script**: `scripts/python-doc-verifier.py` -- AST extraction and deterministic verification
- **Documentation Templates**: `references/doc-templates.md` -- Section templates per module type
