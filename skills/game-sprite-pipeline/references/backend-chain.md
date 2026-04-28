# Codex CLI default with Nano Banana fallback

Operational documentation for the backend chain locked in by ADR-198. Two-step backend selection: Codex CLI first (user's existing paid subscription), Gemini Nano Banana fallback (user's existing API key), fail-loud on absence. Both paths use keys the user already holds — there is no third-party billing the toolkit hides. The Local-First principle (PHILOSOPHY.md, user-owned-key clause) authorizes this fallback chain.

## Detection logic

`sprite_generate.py` runs this in order on every generation call:

```python
def select_backend() -> Literal["codex", "nano-banana"]:
    # Step 1: Codex CLI
    if shutil.which("codex"):
        try:
            subprocess.run(["codex", "--version"], check=True, capture_output=True, timeout=10)
            return "codex"
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            print("[backend] codex CLI present but auth check failed; trying Nano Banana", file=sys.stderr)

    # Step 2: Nano Banana via GEMINI_API_KEY (or GOOGLE_API_KEY)
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return "nano-banana"

    # Step 3: fail loudly with both fix paths
    raise BackendUnavailableError(
        "No image-generation backend available.\n\n"
        "Fix path 1 (Codex CLI, recommended):\n"
        "  Install Codex CLI and run `codex auth` to authenticate against your existing subscription.\n\n"
        "Fix path 2 (Nano Banana fallback):\n"
        "  Set GEMINI_API_KEY (or GOOGLE_API_KEY) in your environment to enable the Nano Banana fallback."
    )
```

The error message lists BOTH fix paths so the user knows which key/install they need. Surfacing both surfaces is intentional — the user picks whichever is convenient.

## Codex CLI invocation contract (v0.125+)

ADR-198 locked in this contract. Codex CLI 0.125+ does NOT expose `--output-image`, `--aspect-ratio`, `--reference`, or `--seed` as direct CLI flags. Image generation happens through the agent's internal `image_gen` tool, invoked from prompt text.

**Command shape:**

```bash
codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check \
  [-i <ref1> <ref2> ... --] \
  "<wrapped prompt>"
```

**Wrapped-prompt semantics:**

- Aspect ratio, seed, and reference-image semantics are encoded INTO the wrapped prompt text, not as CLI flags.
- The wrapped prompt instructs the agent: `"Use your image_gen tool to create the following image. Then save the resulting PNG to this absolute path: <output>. After saving, run ls -la <path> to verify the file exists."`
- Reference images use `-i` (alias `--image`), `nargs=*`. The reference list MUST be terminated with `--` before the positional prompt — otherwise the prompt string is consumed as another image filename.
- `reference` accepts either a single `Path` or a list of `Path`s. The sprite pipeline passes a list when both a grid-canvas template and a character portrait are inputs.

**Subprocess and verification:**

- Subprocess timeout: **360 seconds**. The agent loop wrapping `image_gen` is slower than the old direct-imagegen call (the v0.124 path was ~180s; v0.125 needs the larger budget).
- Verify on success: `output.exists() and output.stat().st_size > 0`. A 0-exit with missing/empty output is treated as failure.
- The implementation lives in `scripts/sprite_generate.py:codex_generate` (HEAD commit `0178861`).

When Codex CLI evolves its image-generation surface again, this section needs an explicit revision — probably a new ADR superseding ADR-198's invocation-contract subsection. The contract is documented in this one canonical place so the next CLI revision has a clear amend target.

## Nano Banana fallback dispatch

When Codex is unavailable AND `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) is set, dispatch through the existing `nano-banana-builder` skill's scripts. The skill never imports the Gemini SDK directly — composition through the existing skill is the contract.

```bash
# Reference-guided generation (spritesheet Phase C, portrait-loop with reference)
python3 ~/.claude/scripts/nano-banana-generate.py with-reference \
    --prompt "<full prompt>" \
    --reference <canvas-or-ref-image> \
    --output <path> \
    --model pro \
    --aspect-ratio 1:1
```

```bash
# Portrait mode (no reference image needed)
python3 ~/.claude/scripts/nano-banana-generate.py generate \
    --prompt "<full prompt>" \
    --output <path> \
    --model pro \
    --aspect-ratio 4:5
```

`--model pro` (gemini-3-pro-image-preview) is the default for portrait/spritesheet because quality matters more than speed for canonical assets. Drafts can pass `--backend-flag --model=flash`.

## Capability matrix

| Capability | Codex CLI (v0.125+) | Nano Banana | Notes |
|------------|----------------------|-------------|-------|
| Single image from text | Yes (via `image_gen` tool) | Yes | Both work for portrait mode |
| Reference image input | Yes (`-i ref --`) | Yes (1 ref) | Codex accepts a list; Nano Banana single-ref |
| Multiple reference inputs | Yes | No | Codex passes 2+ via `-i` list with `--` terminator |
| Grid-template input for layout | Yes (with prompt instructions) | No | Codex consumes a magenta grid canvas as one of the `-i` references; Nano Banana lacks layout awareness |
| Aspect-ratio control | Encoded in prompt text | Full (10 ratios via flag) | Nano Banana has finer flag-level control |
| Seed reproducibility | Encoded in prompt text | Yes (via `--seed`) | Codex seed travels in the prompt body (no flag exposed) |
| Cost | User's Codex subscription | User's Gemini API key | Both billed under existing user accounts |

## Auth checks

| Backend | Auth check | Failure indicator | Fall-through? |
|---------|------------|-------------------|---------------|
| Codex CLI | `codex --version` returns 0 | Non-zero exit or timeout | Yes — try Nano Banana |
| Nano Banana | `GEMINI_API_KEY` or `GOOGLE_API_KEY` non-empty | Both empty | No — raise `BackendUnavailableError` |

Auth-check failures fall through to the next step rather than aborting the skill. Only step 3 (no backend at all) raises.

## Fail-loud message

When no backend is available, the user sees this exact message (or equivalent):

```
BackendUnavailableError: No image-generation backend available.

Fix path 1 (Codex CLI, recommended):
  Install Codex CLI and run `codex auth` to authenticate against your existing subscription.

Fix path 2 (Nano Banana fallback):
  Set GEMINI_API_KEY (or GOOGLE_API_KEY) in your environment to enable the Nano Banana fallback.
```

Both fix paths surface together. The user picks whichever is convenient; the skill does not prefer one over the other beyond the chain order.

## Backend-specific tweaks

`sprite_generate.py` adapts prompts when it knows the active backend:

| Tweak | Codex (v0.125+) | Nano Banana |
|-------|-----------------|-------------|
| Magenta-bg repetition | Repeat at start AND end of wrapped prompt | Single mention (compact prompts work better) |
| Negative-prompt block | Inline in main prompt | Inline (no separate negative-prompt API) |
| Aspect-ratio | Encoded in wrapped prompt text | `--aspect-ratio` flag |
| Reference-image weight | Pass via `-i ref --`; weight encoded in prompt | Strong (Nano Banana respects refs heavily) |
| Save instruction | "save to absolute path: <output>; verify with ls -la" | `--output <path>` flag |

These adaptations are applied automatically; the user does not specify them.

## Cost visibility

Both backends are billed under user-existing accounts:

- **Codex CLI**: monthly subscription; image generation counts against the subscription's token/image budget.
- **Nano Banana**: per-call billing on the user's Gemini API key. Free tier covers ~hundreds of generations per day; paid tier scales linearly.

`sprite_generate.py` logs which backend was used per call so the user can audit cost attribution after a batch run:

```
[backend] portrait gen for "bangkok_belle_nisa" → codex (call 1/8)
[backend] portrait gen for "general_gideon" → codex (call 2/8)
[backend] portrait gen for "test_subject_03" → nano-banana (call 3/8)  # codex auth refresh
...
```

The mid-batch backend switch is a feature: when Codex's auth token expires partway through a long batch, the chain auto-falls-through to Nano Banana so the batch completes rather than fail-loud-and-stop. The log records which calls hit which backend for cost attribution.

<!-- no-pair-required: section header; pair lives in subsection -->
## Failure Modes to Detect

### Signal: Adding a third paid backend as a silent fallback

**Detection:** "If Codex fails AND Gemini fails, try OpenAI directly with `OPENAI_API_KEY`" or "fall through to remove.bg for bg removal."

**Why wrong:** The user-owned-key clause (PHILOSOPHY.md, ADR-198) authorizes fallbacks gated on environment variables the user explicitly set — Codex auth and `GEMINI_API_KEY` qualify because the user holds the keys. A direct OpenAI API call billed to whoever set `OPENAI_API_KEY` is a different relationship: the toolkit is now picking which billing account gets charged. The user expects the documented chain (Codex → Nano Banana → fail loud); their card gets charged because step 3 quietly hit a paid endpoint they did not authorize. Trust violation, principle violation.

**Preferred Action**: Stop at the two authorized backends. Raise `BackendUnavailableError` at step 3 with both fix paths. If a third backend is genuinely needed, propose an ADR amendment that gates it on an explicit env var the user must set (the same pattern as `GEMINI_API_KEY` does for Nano Banana), so the fallback is explicit rather than silent.

### Signal: Caching auth state across runs without revalidation

**Detection:** Storing `BACKEND_DETECTED=codex` in a config file and trusting it on subsequent runs.

**Why wrong:** Codex auth tokens expire. `GEMINI_API_KEY` may be revoked. A cached "yes" can produce stale failures that look like the backend itself is broken.

**Do instead**: Run the detection logic at the start of every `sprite_generate.py` invocation. The check is fast (≤100ms for `codex --version`, instant for env-var check). Cheap to re-run; expensive to debug stale auth.

## Reference loading hint

Load when:
- Backend selection is failing (see fail-loud error above)
- Codex CLI version updates and the invocation contract may need amendment (current contract: v0.125+, ADR-198)
- Adding a new backend (rare; principle is two-step + fail-loud, requires ADR amendment)
- Debugging cost attribution across a batch run
