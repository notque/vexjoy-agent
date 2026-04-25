# Backend Chain

Two-step backend selection. Codex CLI first (user's existing paid subscription), Gemini Nano Banana fallback (user's existing API key), fail-loud on absence. No third backend, no paid-API fallback. The Local-First principle (PHILOSOPHY.md) requires that absence of free backends be visible, not silently monetized.

## Detection logic

`sprite_generate.py` runs this in order on every generation call:

```python
def select_backend() -> Literal["codex", "nano-banana"]:
    # Step 1: Codex CLI
    if shutil.which("codex"):
        # auth check via lightweight invocation
        try:
            subprocess.run(["codex", "--version"], check=True, capture_output=True, timeout=10)
            return "codex"
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            print("[backend] codex CLI present but auth check failed; trying Nano Banana", file=sys.stderr)

    # Step 2: Nano Banana via GEMINI_API_KEY
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return "nano-banana"

    # Step 3: fail loudly
    raise BackendUnavailableError(
        "No image-generation backend available. "
        "Install Codex CLI and authenticate, or set GEMINI_API_KEY. "
        "This skill does not call paid APIs directly."
    )
```

The error message explicitly mentions both options and tells the user paid APIs are not consulted. This is intentional — silent paid fallbacks are the failure mode the principle exists to prevent.

## Codex CLI invocation

Codex CLI is invoked via subprocess:

```bash
codex exec "<full prompt>" --output-image <path> --model image-1
```

Flags vary by Codex CLI version; `sprite_generate.py` runs `codex --help` once at startup to detect supported flags and adapts. If imagegen subcommand syntax is not detected (older Codex versions), the script falls through to Nano Banana.

### Capability matrix

| Capability | Codex CLI | Nano Banana | Notes |
|------------|-----------|-------------|-------|
| Single image from text | Yes | Yes | Both work for portrait mode |
| Reference image input | Yes (1 ref) | Yes (1 ref) | Both support `--reference` |
| Multiple reference inputs | Empirical | No | Codex may accept 2; Nano Banana is single-ref |
| Grid-template input for layout | Empirical | No | Codex empirically tested at skill build; Nano Banana lacks layout awareness |
| Aspect-ratio control | Limited | Full (10 ratios) | Nano Banana has finer control |
| Seed reproducibility | Yes | Yes | Both honor `--seed` |
| Cost | Subscription | API per-call | Both are user-existing; no separate billing surface |

### Empirical validation note

The `Empirical` cells above need real-call validation during skill build. If Codex CLI does not consume a magenta grid canvas as a structural input for spritesheet mode, the skill auto-falls-back to per-frame generation + Pillow compositing. This fallback is implemented and is the safe default until Codex grid support is confirmed.

The current behavior:

```python
def generate_spritesheet(...):
    if backend == "codex" and CODEX_GRID_TEMPLATE_SUPPORTED:
        # single call: pass canvas + reference, prompt for "place character in each cell"
        ...
    else:
        # fallback: generate N frames individually, composite with Pillow
        for cell in grid_cells:
            frame = generate_single_frame(cell)
            paste(canvas, frame, cell.bbox)
```

`CODEX_GRID_TEMPLATE_SUPPORTED` defaults to `False` (conservative). Flip to `True` after empirical validation confirms it works.

## Nano Banana dispatch

Calls the existing `nano-banana-builder` skill's scripts:

```bash
python3 ~/.claude/scripts/nano-banana-generate.py with-reference \
    --prompt "<full prompt>" \
    --reference <canvas-or-ref-image> \
    --output <path> \
    --model pro \
    --aspect-ratio 1:1
```

For portrait mode (no reference image needed):

```bash
python3 ~/.claude/scripts/nano-banana-generate.py generate \
    --prompt "<full prompt>" \
    --output <path> \
    --model pro \
    --aspect-ratio 4:5
```

`--model pro` (gemini-3-pro-image-preview) is the default for portrait/spritesheet because quality matters more than speed for canonical assets. Drafts can pass `--backend-flag --model=flash`.

## Auth checks

| Backend | Auth check | Failure indicator |
|---------|------------|-------------------|
| Codex CLI | `codex --version` returns 0 | Non-zero exit or timeout |
| Nano Banana | `GEMINI_API_KEY` or `GOOGLE_API_KEY` non-empty | Both empty |

Auth-check failures fall through to the next step rather than aborting the skill. Only step 3 (no backend at all) raises.

## Fail-loud message

When no backend is available, the user must see this exact message (or equivalent):

```
ERROR: No image-generation backend available.

Tried in order:
  1. Codex CLI (`codex` not in PATH or auth failed)
  2. Gemini Nano Banana (GEMINI_API_KEY not set)

This skill does not call paid APIs directly. To proceed:
  - Install Codex CLI: npm install -g @openai/codex (or equivalent), then `codex auth`
  - OR set GEMINI_API_KEY: export GEMINI_API_KEY=<your-key>

Never set OPENAI_API_KEY for this skill — paid fallbacks are intentionally
prohibited per the Local-First principle (docs/PHILOSOPHY.md).
```

## Backend-specific tweaks

`sprite_generate.py` adapts prompts when it knows the active backend:

| Tweak | Codex | Nano Banana |
|-------|-------|-------------|
| Magenta-bg repetition | Repeat at start AND end | Single mention (compact prompts work better) |
| Negative-prompt block | Inline in main prompt | Inline (no separate negative-prompt API) |
| Aspect-ratio | Use `--aspect-ratio` flag | Use `--aspect-ratio` flag |
| Reference-image weight | Default | Strong (Nano Banana respects refs heavily) |

These adaptations are applied automatically; user does not specify them.

## Cost visibility

Both backends are billed under user-existing accounts:

- **Codex CLI**: monthly subscription; image generation counts against the subscription's token/image budget.
- **Nano Banana**: per-call billing on the user's Gemini API key. Free tier covers ~hundreds of generations per day; paid tier scales linearly.

`sprite_generate.py` logs which backend was used per call so the user can audit cost attribution after a batch run:

```
[backend] portrait gen for "bangkok_belle_nisa" → codex (call 1/8)
[backend] portrait gen for "general_gideon" → codex (call 2/8)
...
```

<!-- no-pair-required: section header; pair lives in subsection -->
## Anti-pattern

### Anti-pattern: Adding a third paid backend as silent fallback

**What it looks like:** "If Codex fails AND Gemini fails, try OpenAI directly with `OPENAI_API_KEY`".

**Why wrong:** Silent paid fallbacks make cost invisible. The user expects free-tier behavior because the skill says "local-first"; their card gets charged because step 3 quietly hit a paid endpoint. Trust violation, principle violation.

**Do instead**: Fail loudly at step 3. Tell the user exactly what is missing and how to fix it. If the user wants OpenAI direct calls, they should add it explicitly via a separate skill or a deliberate config knob — not a silent runtime fallback.

### Anti-pattern: Caching auth state across runs without revalidation

**What it looks like:** Storing `BACKEND_DETECTED=codex` in a config file and trusting it on subsequent runs.

**Why wrong:** Codex auth tokens expire. `GEMINI_API_KEY` may be revoked. A cached "yes" can produce stale failures that look like the backend itself is broken.

**Do instead**: Run the detection logic at the start of every `sprite_generate.py` invocation. The check is fast (≤100ms for `codex --version`, instant for env-var check). Cheap to re-run; expensive to debug stale auth.

## Reference loading hint

Load when:
- Backend selection is failing (see fail-loud error above)
- Adding a new backend (rare; principle is two-step + fail-loud)
- Debugging cost attribution across a batch run
