# Python Local Conventions and Gates

Host-specific incidents, operator conventions, and version-pinned gotchas for this machine's Python work. Generic Python idioms stay out; the base model covers those.

## Hard Gates (STOP / REPORT / FIX)

Before writing Python code, check for these patterns. If found: STOP implementation, REPORT to the user, FIX before continuing. Framework: `skills/shared-patterns/forbidden-patterns-template.md`.

| Pattern | Why blocked | Fix |
|---------|-------------|-----|
| `except OSError: pass` (broad swallow) | Catches permission denied, IO errors, NFS stale handles — beyond just missing files. Caused 2 critical silent failures in reddit_mod.py | `except FileNotFoundError: pass` for expected-missing; separate `except OSError as e:` with stderr warning |
| `int(untrusted_json_value)` without guard | Crashes entire pipeline on one malformed entry from user-editable JSON | Wrap in `try: int(x) except (ValueError, TypeError): default` |
| `# type: ignore` without error code and reason | Hides real type errors, defeats type safety | `# type: ignore[specific-error]  # Reason: ...` — or fix the type |

```bash
# Detection
grep -rn "except OSError: pass" --include="*.py"
grep -rn "# type: ignore$" --include="*.py"
```

## Ruff Exception: Peewee E712

Use truthiness (`if value:`) and identity (`is None`) in ordinary code. The one sanctioned exception:

```python
# Peewee ORM field comparisons require == True for SQL generation
query = User.select().where(User.active == True)
# E712 should be suppressed for this specific ORM pattern
```

## Environment on This Host

- **venv for every deploy.** System `pip` may belong to a different Python than `python3`, so packages land in the wrong site-packages. Create the venv first and install inside it with `python -m pip`:

```bash
python3 -m venv .venv && . .venv/bin/activate && python -m pip install -e '.[dev]'
```

- **Installing uv**: use a package manager: `pipx install uv` or `python3 -m pip install --user uv`. This host's policy blocks installer scripts downloaded and run in one step.

## CLI Pipeline Conventions (reddit_mod)

- **Validate all input on new CLI handlers.** Every existing handler validates input (e.g., `_resolve_subreddit`); a new subcommand that accepts subreddit/path from stdin JSON or env var without that validation creates path traversal via crafted stdin JSON. Reuse the same validation function; when input arrives from a new source, validate BEFORE any file path construction.
- **Surface all computed data in LLM prompts.** The LLM can only use data that appears in the prompt; a computed `repeat_offender_count` left out of the prompt string is dead computation. Every signal computed for classification appears in the rendered prompt. Test: "is this value in the prompt string?"
- **Define every new category.** Adding `BAN_RECOMMENDED` to a classification list without usage criteria leaves the LLM no way to distinguish it from existing categories. Each new category ships with a definition, usage criteria, and auto-mode behavior in the prompt.

## Version-Pinned Security Gotchas

Pinned CVEs/commits worth loading when the task touches parsing, serialization, or outbound requests.

| Gotcha | Pin | Fix |
|--------|-----|-----|
| tar extraction writes outside target dir | CVE-2007-4559; `filter=` added in 3.12, default became `"data"` in 3.14 | Always pass `tar.extractall(dir, filter="data")` so 3.12 and 3.13 behave like 3.14 |
| `yaml.load` reaches `os.system` via `!!python/object` | CVE-2020-1747 (PyYAML FullLoader before 5.3.1) | `yaml.safe_load` |
| ML model files (`.pkl`, `.joblib`) execute code on load | CVE-2025-1716; GHSA-g8c6-8fjj-2r4m (python-socketio pickle across servers) | JSON or validated formats across trust boundaries |
| Pydantic response DTO with `extra="allow"` passes arbitrary fields to the response | Sentry commit `0c0aae90ac1` | `extra="ignore"` on response DTOs + `response_model=` on every endpoint returning DB data |
| SSRF despite string-based URL checks | CVE-2024-34351 (Next.js Server Actions, same bug class) | Resolve DNS, reject private, loopback, link-local, and metadata ranges at the IP layer (`ipaddress.ip_address(...).is_global`), and disable redirects: `requests` `allow_redirects=False`; httpx already defaults to `follow_redirects=False` |
| Jinja2 sandbox escapes via `render_template_string(user_input)` | CVE-2019-10906, CVE-2016-10745 | Render from template files; user data enters as context variables only |
