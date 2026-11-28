# One-Turn Prompt Compiler

Compile an underspecified request into a concrete 5-line task contract in one turn before running edits or mutating commands. Once ratified, pass the contract straight into `/do` or `/d` as `task_spec`.

## When to run

Run the prompt compiler when any of these triggers apply:

- The user invokes `/prompt <request>`.
- The request includes `--shape` or asks to "shape this prompt".
- `scripts/jev-intent-align.py` flags low `has_actionable_outcome` or sets `clarification_needed`.

Skip the compiler when the request already names a concrete target, clear scope boundaries, and a verification command or observable proof. Proceed directly to `/do` or `/d`.

## Grounding step (read-only)

Before drafting the card, inspect up to 5 relevant files or run read-only repository checks (`git status`, `git branch`, directory listings, symbol searches) to anchor file paths and assumptions in real repository state. Make zero file edits and run zero mutating commands during compilation.

If the prompt includes standalone preset flags (`--strict-scope`, `--spike`, `--review-only`, `--ship`, `--local-only`), write the raw request to a temp file and extract them via `$SDIR` so shell quoting and leading flags stay safe:

```bash
SDIR="${HOME}/.claude/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.gemini/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.hermes/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.factory/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.codex/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.reasonix/scripts"
REQUEST_FILE=$(mktemp)
cat <<'EOF' > "$REQUEST_FILE"
<request>
EOF
python3 "$SDIR/prompt_presets.py" --extract-file "$REQUEST_FILE" --json
rm -f "$REQUEST_FILE"
```

Reflect the extracted presets in the card's scope and verification lines.

## Five-line ratification card

Emit this compact card as the visible response before taking any action:

```markdown
1. **Outcome:** <one sentence naming the exact deliverable>
2. **Out of scope:** <explicit exclusions and boundaries>
3. **Verify with:** <exact command or observable proof>
4. **Owned paths / assumptions:** <concrete repo paths and grounded assumptions>
5. **Open question (only if needed):** <at most 1 load-bearing question with a recommended default; omit line 5 if none>
```

### Field rules

| Line | Rule |
|---|---|
| 1. Outcome | State one concrete deliverable in active voice. Preserve every explicit constraint from the user's request. |
| 2. Out of scope | Name adjacent files, refactors, pushes, or follow-up work that stay untouched. Include active preset limits such as `--strict-scope` or `--local-only`. |
| 3. Verify with | Name the exact test, lint, validator command, or observable output that proves completion. |
| 4. Owned paths / assumptions | List verified paths from the read-only grounding pass (prefix planned new files with `new:`) and any load-bearing assumptions. |
| 5. Open question | Include only when an ambiguity changes the implementation path. State one recommended default so a single reply ratifies it. Omit this line when the grounding pass resolves every detail. |

## Example card

Raw prompt: `/prompt make routing presets work in dispatch --strict-scope --local-only`

```markdown
1. **Outcome:** Add composable prompt constraint presets (`--strict-scope`, `--spike`, `--review-only`, `--ship`, `--local-only`) and inject active preset rules into `scripts/build-dispatch.py` output.
2. **Out of scope:** Touching hooks, `README.md`, or pushing commits (`--strict-scope`, `--local-only`).
3. **Verify with:** `pytest -q -n 0 scripts/tests/test_prompt_presets.py scripts/tests/test_build_dispatch.py` and `ruff check scripts/prompt_presets.py scripts/build-dispatch.py --config pyproject.toml`.
4. **Owned paths / assumptions:** `new:scripts/prompt_presets.py`, `scripts/build-dispatch.py`, `new:scripts/tests/test_prompt_presets.py`; output without presets stays byte-identical.
```

Reply `go` to run with `/do` (or `/d`), or edit any line to adjust.

## Continuation into `/do` or `/d`

When the user replies `go`, `proceed`, `yes`, or sends a one-line adjustment:

1. Apply any edited line directly without repeating the full card.
2. Map the ratified lines into `task_spec` and invoke `/do` (or `/d` if requested):
   - `task_spec.request_verbatim`: original user request, unchanged.
   - `task_spec.intent`: Line 1 (`Outcome`).
   - `task_spec.constraints`: Line 2 (`Out of scope`). Leave canonical preset rules to `prompt_presets` so `build-dispatch.py` injects each preset once without duplication.
   - `task_spec.acceptance`: Line 3 (`Verify with`).
   - `task_spec.files` and `task_spec.ownership`: Line 4 (`Owned paths / assumptions`).
   - `task_spec.decisions` or `task_spec.clarification`: Line 5 answer or ratified default (if present).
   - `prompt_presets`: list of extracted preset names (if any); `build-dispatch.py` appends their canonical constraint text automatically.
3. Proceed straight into execution without re-asking clarifying questions.
