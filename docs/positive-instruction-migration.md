# Positive Instruction Migration

This is the low-token migration loop for converting negatively framed instruction docs into positive-action guidance.

The model should not read whole files to perform repo-wide rewrites. Scripts find and isolate the work, the LLM rewrites only the isolated blocks, and scripts patch verified rewrites back into the repo.

## Target Schema

Instruction docs should teach through positive actions:

- what to do
- why it matters
- how to verify it

Preferred section shapes:

- `## Preferred Actions`
- `## Patterns to Detect and Fix`
- `### Signal`
- `### Why It Matters`
- `### Preferred Action`
- `### Verification`

Legacy headings like `Anti-Patterns`, `What NOT To Do`, `FORBIDDEN`, and `do NOT` should be treated as migration backlog, not as the target schema for new content.

## Low-Token Loop

### Phase 0: Deterministic normalization

Run the safe mechanical rewrites first:

```bash
python3 scripts/bulk_fix_instruction_joy.py --apply-safe-fixes \
  --output artifacts/bulk-fix-instruction-joy-report.json

python3 scripts/bulk_fix_do_framing.py --apply \
  --output artifacts/bulk-fix-do-framing-report.json
```

This clears the cheap wins before spending any LLM tokens.

### Phase 1: Extract only the remaining negative blocks

```bash
python3 scripts/extract_negative_instruction_blocks.py \
  --output artifacts/negative-instruction-blocks.json
```

Each record includes:

- exact file path
- exact line range
- block hash
- minimal block text
- estimated token size

### Phase 2: Build rewrite batches

```bash
python3 scripts/build_instruction_rewrite_batches.py \
  --input artifacts/negative-instruction-blocks.json \
  --output-dir artifacts/instruction-rewrite-batches \
  --max-tokens 3500
```

Each batch contains only the blocks that need semantic rewriting. No whole-file prompts.

### Phase 3: LLM rewrite

For each batch, rewrite only the extracted blocks:

- keep the same file and line range
- preserve the safety intent
- lead with the preferred action
- keep the why
- keep detection or verification details when already present
- do not add new scope

The output schema should be:

- `id`
- `file`
- `line_start`
- `line_end`
- `block_sha256`
- `replacement`

### Phase 4: Apply verified rewrites

```bash
python3 scripts/apply_instruction_block_rewrites.py \
  --input artifacts/rewrite-results.json
```

The apply step refuses to patch a block if the current text hash no longer matches the extracted block. That prevents stale rewrites from landing on moved or manually edited content.

### Phase 5: Validate

```bash
python3 scripts/validate-references.py --check-do-framing
python3 scripts/validate_positive_instruction_docs.py
python3 scripts/validate_reference_loading_tables.py
python3 -m pytest scripts/tests/test_bulk_fix_instruction_joy.py \
  scripts/tests/test_bulk_fix_do_framing.py \
  scripts/tests/test_extract_negative_instruction_blocks.py \
  scripts/tests/test_apply_instruction_block_rewrites.py \
  scripts/tests/test_validate_positive_instruction_docs.py \
  scripts/tests/test_validate_reference_loading_tables.py \
  scripts/tests/test_detect_unpaired_antipatterns.py \
  scripts/tests/test_check_do_framing.py -q
```

## Design Rules

- Use scripts for search, slicing, patching, and validation.
- Use the LLM only for semantic block rewrites.
- Never send whole files to the LLM when a single block is enough.
- Prefer positive-action headings and tables in new content.
- Thin orchestrators only count as token savings when they include a Reference Loading Table.
- Treat `Anti-Patterns` as legacy content to migrate, not the target schema for new templates.
