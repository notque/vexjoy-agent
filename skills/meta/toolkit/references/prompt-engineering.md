# Model-Aware Prompt Engineering Guide

Write prompts that match each model family's observed execution habits, pack context at the high-attention edges, and state rules positively so automated validators pass cleanly.

## Model-family behavior and counters

Observed behavior across VexJoy sessions and routing telemetry shows distinct failure modes per model family. Counter each tendency directly in the prompt contract:

| Model family | Observed tendency | Prompt counter |
|---|---|---|
| **Claude (Opus / Sonnet / Fable)** | Expands scope proactively or substitutes a cleaner goal silently at lower effort. | Add an explicit `Out of scope` line, route through `/d` for the Jev intent gate, and attach `--strict-scope` when touching narrow paths. |
| **Gemini / Argon (Antigravity)** | Follows literal instructions tightly and sometimes stops before implied follow-through (linters, doc sync, cleanup). | State every end-to-end done criterion and exact verification command explicitly in `Verify with`. |
| **GPT / Codex** | Produces terse patches and narrow edits that skip edge-case tests or adjacent callers. | State explicit test cases, edge conditions, and owned file boundaries in the task contract. |

Combine model counters with composable presets via `python3 scripts/prompt_presets.py --list` (`--strict-scope`, `--spike`, `--review-only`, `--ship`, `--local-only`). For underspecified requests, run the one-turn compiler in `skills/meta/do/references/prompt-compiler.md` (`/prompt`) before editing.

## Five reusable 5-line prompt skeletons

Each skeleton mirrors the 5-line contract used by `/prompt` and `scripts/build-dispatch.py`. Replace bracketed slots with real paths and commands.

### 1. Debug

```text
1. Outcome: Reproduce and fix [bug symptom] in [path:symbol] without changing public behavior.
2. Out of scope: Unrelated modules, schema changes, or formatting edits outside owned files (--strict-scope).
3. Verify with: [failing test command] fails before the fix and passes after, plus [linter command] exits 0.
4. Owned paths / assumptions: [source file], [test file]; root cause must be confirmed from runtime output or trace before patching.
5. Open question: None (report root cause and regression test output in the summary).
```

### 2. Refactor

```text
1. Outcome: Extract [target behavior] from [source path] into [new:target path] while preserving all existing API contracts.
2. Out of scope: Behavior changes, dependency upgrades, or edits outside listed callers (--strict-scope --local-only).
3. Verify with: [full test suite command] passes with 0 failures and [typecheck/lint command] exits 0.
4. Owned paths / assumptions: [source path], [new:target path], [caller paths], [test path]; existing tests cover current behavior.
5. Open question: Keep legacy wrapper re-export at [old symbol] (default: yes, remove in a follow-up PR).
```

### 3. Architecture critique

```text
1. Outcome: Review [design doc or module paths] for failure modes, coupling risks, and missing operational invariants (--review-only).
2. Out of scope: Editing files, writing prototype code, or proposing unrelated rewrites.
3. Verify with: Every finding cites concrete `file:line` evidence, failure trigger, impact, and one minimal remediation.
4. Owned paths / assumptions: Read-only access to [paths]; target deployment runs on [runtime / scale assumptions].
5. Open question: Prioritize [reliability vs. latency vs. migration risk] (default: rank by blast radius first).
```

### 4. Deep research synthesis

```text
1. Outcome: Compare [option A], [option B], and [option C] for [decision] in a single decision matrix with a clear recommendation (--spike).
2. Out of scope: Production code edits or committing exploratory scripts.
3. Verify with: Cite primary docs, benchmarks, or repo file:line evidence for every claim; mark unverified claims explicitly.
4. Owned paths / assumptions: Sources in [paths or URLs]; decision constraints are [budget, latency, OS support].
5. Open question: Target primary runtime [Linux / cross-platform] (default: cross-platform Linux and Windows).
```

### 5. Eval rubric

```text
1. Outcome: Write a deterministic pass/fail eval rubric and [N] representative test cases for [skill or script] at [new:eval path].
2. Out of scope: Modifying the production skill under test during baseline rubric creation (--local-only).
3. Verify with: Running [eval command] scores baseline outputs reproducibly across 2 runs with binary criteria and zero subjective scales.
4. Owned paths / assumptions: [subject path], [new:eval path]; include at least 2 negative or edge-case prompts.
5. Open question: Include held-out validation split (default: yes, reserve 20% of cases as held-out).
```

## Positive vs. negative framing rules

Models attend strongly to the nouns and verbs named in an instruction. Prohibition-heavy phrasing names the unwanted action and triggers compliance drift, while positive directives specify the exact target behavior.

| Framing issue | Rewrite positively |
|---|---|
| Prohibition header ("Bad practices", "What to reject") | Name the required standard ("Required patterns", "Verification rules") or pair every failure mode with an explicit `Preferred` column. |
| Uppercase bans ("forbidden", "do not") | State the bounded action ("Edit only listed files", "Keep all changes local", "Make zero remote pushes"). |
| Emotional or grievance framing in prose | State observable facts, trade-offs, and next actions directly. |

Validate instruction and editorial files with both repo scripts:

- Instruction docs (skills, agents, references): run `python3 scripts/validate_positive_instruction_docs.py --fleet` and `python3 scripts/validate-references.py --check-do-framing`.
- Editorial and narrative prose: run `python3 scripts/scan-negative-framing.py <file>` to catch grievance, accusatory, or self-flagellation phrasing.

## Context-packing order

Transformer attention peaks at the beginning and end of a prompt and weakens across dense middle sections. Order every non-trivial prompt and dispatch payload in four zones:

1. **Top edge (high attention):** Role, exact 1-sentence `Outcome`, and hard boundaries (`Out of scope`, active presets).
2. **Upper middle:** Owned file list (`file:line` pointers) and grounded design decisions.
3. **Lower middle (evidence zone):** Retrieved excerpts, command outputs, or error logs wrapped in `<untrusted-content>` tags when sourced from external or repository data. Include only slices tied to the task; omit raw full-file dumps that carry no decision signal.
4. **Bottom edge (high attention):** Exact verification commands (`Verify with`), required output format, and closing check.

### Context budget checks

- Keep raw excerpts bounded to the relevant function, diff hunk, or failing trace rather than pasting entire logs.
- Put immutable constraints and acceptance checks at both edges when a prompt exceeds ~2,000 tokens so long retrieved evidence in the middle leaves the exit criteria intact.
- Replace repeated prose rules with a single preset flag (`--strict-scope`, `--review-only`, `--local-only`, `--spike`, `--ship`) so `scripts/build-dispatch.py` injects the exact canonical rule deterministically.
