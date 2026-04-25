# Backend Chain

Codex CLI imagegen is the **sole** backend. There is no fallback. If Codex is unavailable, the skill fails loudly rather than silently calling a paid alternative. The Local-First principle (PHILOSOPHY.md) requires that absence of the free backend be visible, not silently monetized.

> **Why no fallback?** Earlier drafts of this skill chained Codex -> Gemini Nano Banana -> fail-loud. We removed Nano Banana entirely because (a) it is a separate paid surface the user must opt into deliberately, (b) Codex's existing subscription already covers the user's image-gen budget, and (c) silent multi-backend chains are the failure mode the principle exists to prevent. If you need a second backend, add it explicitly with a deliberate environment variable, not a runtime fallback.

## Detection logic

`sprite_generate.py` runs this on every generation call:

```python
def select_backend() -> BackendChoice:
    if shutil.which("codex"):
        try:
            subprocess.run(["codex", "--version"],
                           check=True, capture_output=True, timeout=10)
            return BackendChoice("codex", "codex --version exit 0")
        except (...) as e:
            raise BackendUnavailableError(
                "Codex CLI is on PATH but the auth/version check failed. "
                "Run `codex login` and retry. This skill does not fall "
                "back to paid APIs."
            ) from e

    raise BackendUnavailableError(
        "Codex CLI is not available. Install Codex CLI and run "
        "`codex login`. This skill uses Codex as its sole backend."
    )
```

## Codex CLI invocation pattern

Codex CLI does **not** have a `codex image generate` subcommand. Image
generation happens via `codex exec`: the Codex agent has access to an
internal `image_gen` tool, and we invoke it by *prompting the agent* to use
that tool and to save the result at a specific absolute path.

The actual command line shape, as built by `sprite_generate.py`:

```bash
codex exec \
    --dangerously-bypass-approvals-and-sandbox \
    --skip-git-repo-check \
    [-i /path/to/reference.png] \
    "$WRAPPED_PROMPT"
```

`$WRAPPED_PROMPT` is the user's prompt wrapped with explicit imagegen
instructions:

```
Use your image_gen tool to create the following image. Then save the
resulting PNG file to this absolute path: /tmp/sprite-demo/raw/foo.png
After saving, run `ls -la <path>` to verify the file exists.

Image specification:
ART_STYLE: ...
DESCRIPTION: ...
RULES: solid magenta background, single character centered, ...
NEGATIVE: cropped body, multiple characters, watermarks, ...

Aspect ratio target: 1:1 square (1024x1024).
```

Codex first writes the generated PNG into
`$CODEX_HOME/generated_images/<session-id>/ig_<hash>.png`, then the agent
runs `cp` to move it to the requested output path, then runs `ls -la` to
confirm. The Python wrapper checks `output.exists() and st_size > 0` after
the subprocess returns so a missing file is caught loudly.

### Why `--dangerously-bypass-approvals-and-sandbox`?

The default `--full-auto`/`--sandbox workspace-write` mode runs every shell
command through bubblewrap. On hosts without correctly-configured
bubblewrap (DigitalOcean droplets, many Linux containers), bubblewrap fails
with `loopback: Failed RTM_NEWADDR: Operation not permitted` *before* the
agent's `cp` step can run. The image is generated inside Codex's session
dir but never reaches the requested output path.

The skill therefore uses `--dangerously-bypass-approvals-and-sandbox`,
which trusts Codex to run inside the user's existing OS-level sandboxing
(this is consistent with how the Codex CLI is invoked elsewhere in the
toolkit and how the user already runs trusted automation). The flag name
is loud on purpose: it signals that this code path runs Codex with normal
shell privileges. We rely on the user's existing OS isolation.

### Capability matrix

| Capability | Codex CLI | Notes |
|------------|-----------|-------|
| Single image from text | Yes | Both modes |
| Reference image input | Yes | `-i <path>` flag (Codex 0.125+) |
| Aspect-ratio control | Encoded in prompt | No public CLI flag; embed in prompt body |
| Seed reproducibility | Best-effort | No public CLI flag; comment in prompt body |
| Wall-clock per call | ~20-60s typical | Cap at 180-240s |

`sprite_generate.py` exposes `--timeout` (default 240s) so callers can
tighten the cap when they know what they want.

## Auth checks

| Backend | Auth check | Failure indicator |
|---------|------------|-------------------|
| Codex CLI | `codex --version` returns 0 | Non-zero exit or timeout |

Auth-check failure raises `BackendUnavailableError` immediately. There is
no second step.

## Fail-loud message

When Codex is unavailable, the user sees:

```
ERROR: Codex CLI is not available.

Install Codex CLI and run `codex login`, then retry.

This skill uses Codex CLI imagegen as its sole backend. There is no
fallback to paid APIs (no Gemini, no Nano Banana, no OpenAI direct).
The skill fails loud rather than silently charging your card on a
backend you did not opt into.
```

If Codex is on PATH but unauthenticated:

```
ERROR: Codex CLI is on PATH but the auth/version check failed: <error>.

Run `codex login` to authenticate, then retry.
```

## Failure modes

| Symptom | Cause | Fix |
|---------|-------|-----|
| `codex login` required, then no PNG file | Auth not refreshed | Run `codex login`; check `~/.codex/auth.json` is valid |
| `bwrap: loopback: Failed RTM_NEWADDR` in log | bubblewrap sandbox broken on host | Skill already uses `--dangerously-bypass-approvals-and-sandbox`; if you patched it out, restore it |
| Codex returns 0 but output file missing | Prompt did not invoke imagegen tool | Prompt body must say "Use your image_gen tool..."; the wrapper handles this. If you bypassed the wrapper, restore `_build_codex_prompt` |
| Codex hangs >180s | Backend slow / model retry | Raise `--timeout`; check `--log-file` for the agent's reasoning trace |
| Output is wrong aspect (e.g., 1254x1254 vs 1024x1024) | Codex picks dimensions; aspect hint is best-effort | Post-process resize in Phase D/F |
| `codex` not in PATH | Codex CLI not installed | `npm install -g @openai/codex` (or per OS) |
| Repeated `failed to record rollout items` warnings | Cosmetic Codex bug | Ignore; not a real failure |

## Cost visibility

Codex CLI image generation is billed under the user's Codex subscription
(no per-call charge surface visible to the skill). `sprite_generate.py`
logs every dispatch so the user can audit batch cost attribution after a
run:

```
[backend] selected=codex (codex --version exit 0)
[backend:codex] generating -> /tmp/sprite-demo/raw/01.png (timeout 240s)
[backend:codex] generating -> /tmp/sprite-demo/raw/02.png (timeout 240s)
...
```

<!-- no-pair-required: section header; pair lives in subsection -->
## Anti-pattern

### Anti-pattern: Adding a paid-API fallback as silent step 2

**What it looks like:** "If Codex fails, try OpenAI directly with `OPENAI_API_KEY`" or "fall back to Gemini Nano Banana via `GEMINI_API_KEY`".

**Why wrong:** Silent paid fallbacks make cost invisible. The user expects free-tier behavior because the skill says "local-first"; their card gets charged because step 2 quietly hit a paid endpoint. Trust violation, principle violation. We removed the Nano Banana branch from this skill exactly to enforce this.

**Do instead**: Fail loudly. Tell the user exactly what is missing and how to fix it. If they want OpenAI direct calls, they should add it explicitly via a separate skill or a deliberate env-var-gated path -- not a silent runtime fallback.

### Anti-pattern: Caching auth state across runs without revalidation

**What it looks like:** Storing `BACKEND_DETECTED=codex` in a config file and trusting it on subsequent runs.

**Why wrong:** Codex auth tokens expire. A cached "yes" produces stale failures that look like the backend itself is broken.

**Do instead**: Run the detection logic at the start of every `sprite_generate.py` invocation. The check is fast (<=100ms for `codex --version`). Cheap to re-run; expensive to debug stale auth.

## Reference loading hint

Load when:
- Backend selection is failing (see fail-loud error above)
- Codex returns 0 but the expected output file is missing
- Debugging a Codex-CLI prompt that does not appear to invoke imagegen
