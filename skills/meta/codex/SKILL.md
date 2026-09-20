---
name: codex
version: "1.0.0"
description: "Run a /do-selected GPT-5.6 model and effort through the Codex CLI from a non-Codex harness."
user-invocable: false
compatibility: "Requires codex CLI on PATH; /do supplies model and reasoning effort."
allowed-tools: [Read, Bash, Grep, Glob]
routing:
  force_route: true
  triggers: [through codex, codex exec, dispatch to codex, run on codex, codex analysis, gpt-5.6]
  pairs_with: [data, pr-workflow]
  complexity: Medium
  category: meta
---

# Codex execution lane

This skill owns the repository's general `codex exec` mechanics. `/do` owns model selection; do not duplicate its benchmark table or silently substitute a local default. Under Claude Code this is an explicit cross-provider lane, not the automatic default. Reviews belong to `pr-workflow`'s Codex-review flow.

## Contract

1. Require the model and reasoning effort selected by `/do`. Deterministic work stays in scripts.
2. Check `command -v codex`. If absent, use the policy-selected Claude fallback and report the lane change.
3. Give Codex a self-contained prompt: minimal repository context, concrete task and relative paths, and exact output contract. Codex has no conversation history; point it at files instead of embedding them.
4. Prompts leave the harness. Exclude credentials and names from local-only inventories. Scan before sending:

```bash
printf '%s' "$PROMPT" | rg -n 'Bearer|Authorization|token|secret|api[_-]?key|password|PRIVATE KEY'
```

Scrub a hit when possible; otherwise use the in-harness model.
5. For a read-only task:

```bash
OUT=$(mktemp)
codex exec -m "$CODEX_MODEL" -c "model_reasoning_effort=\"$CODEX_EFFORT\"" \
  -s read-only --skip-git-repo-check -o "$OUT" \
  "$(cat <<'PROMPT'
[self-contained prompt]
PROMPT
)"
cat "$OUT"
```

For authorized writes, omit `-s read-only`, run in the target repository, and inspect `git status --short` plus `git diff`. Never commit merely because this lane ran.
6. Accept only exit code 0 and the requested output shape. Apply deterministic verification when available and return the model/effort with the result.

## Local failures

- `bwrap` / `Failed RTM_NEWADDR`: retry without `-s read-only` only when the outer harness already supplies a sandbox. Never combine read-only sandboxing with `--dangerously-bypass-approvals-and-sandbox`.
- Empty/truncated `-o`: shorten the prompt and reference files; capture stdout as fallback.
- Other non-zero exits: surface stderr. Auth, API, and prompt-length failures are not blind-retry cases.
