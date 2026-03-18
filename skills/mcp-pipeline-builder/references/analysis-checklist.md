# Phase 1 Analysis Checklist

Structured checklist for the ANALYZE phase. Complete every section before writing `analysis.md`.

---

## Stack Identification

- [ ] Primary language(s) — check file extensions, `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`
- [ ] Primary framework — Express, FastAPI, Django, Echo, Rails, etc.
- [ ] Package manager — npm/pnpm/yarn, pip/uv/poetry, go modules, cargo
- [ ] Runtime version constraints — Node ≥ 18? Python ≥ 3.11?
- [ ] Build tooling — TypeScript, webpack, esbuild, tsc, cargo build

**Signal files to read first**: `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `setup.py`, `Makefile`, `README.md` (for stated purpose).

---

## API Surface Discovery

Scan for each surface type that applies to this repo.

### REST Endpoints

- [ ] Find route definitions (`router.get`, `app.post`, `@app.route`, `r.Handle`, etc.)
- [ ] Note HTTP method (GET, POST, PUT, PATCH, DELETE)
- [ ] Note path and path parameters (e.g., `/users/{id}`)
- [ ] Note request body schema (look for validation models, JSON schema, Zod/Pydantic)
- [ ] Note authentication requirement (middleware, decorator, guard)
- [ ] File locations: `routes/`, `handlers/`, `api/`, `controllers/`

### CLI Commands

- [ ] Find command definitions (`cobra`, `click`, `argparse`, `commander`, `clap`)
- [ ] List top-level commands and subcommands
- [ ] Note flags and positional arguments for each command
- [ ] Note commands that require auth (API key, config file, env var)

### Exported Functions / Classes

- [ ] Read the main entry point (`index.ts`, `__init__.py`, `lib.rs`, `main.go`)
- [ ] List exported public functions (not internal/private)
- [ ] Identify classes with meaningful public methods
- [ ] Note which functions require configuration or instantiation to call

---

## Auth Pattern Recognition

Identify which auth pattern the service uses. Check these in order:

| Pattern | Detection Signals | Example Env Var |
|---------|------------------|-----------------|
| **API Key** | `X-API-Key` header, `?api_key=` param, `Bearer {key}` | `SERVICE_API_KEY` |
| **OAuth 2.0** | `Authorization: Bearer {token}`, token refresh logic, `CLIENT_ID`/`CLIENT_SECRET` | `SERVICE_CLIENT_ID`, `SERVICE_CLIENT_SECRET` |
| **Basic Auth** | `Authorization: Basic {base64}`, username/password config | `SERVICE_USER`, `SERVICE_PASSWORD` |
| **JWT** | `Authorization: Bearer {jwt}`, `jsonwebtoken`, `jwt.decode` | `SERVICE_JWT` or `SERVICE_TOKEN` |
| **None** | Public API, no auth middleware | — |

- [ ] Record auth pattern name
- [ ] Record the exact env var names needed (from `.env.example`, README, or source)
- [ ] Note if auth is optional vs required for each endpoint/command

---

## Entity Mapping

Answer: what "nouns" does this system manage?

Examples by domain:
- GitHub API: `repository`, `issue`, `pull_request`, `user`, `organization`
- Jira API: `project`, `issue`, `comment`, `attachment`, `sprint`
- Local file tool: `file`, `directory`, `search_result`

- [ ] List 3–10 primary entity types
- [ ] For each entity: list the CRUD operations available (create, read, update, delete, list)
- [ ] Note which entities are "nested" (e.g., `comment` belongs to `issue`)

---

## Read/Write Classification

Apply this heuristic to every discovered operation. Be explicit — every operation gets a classification.

### Read (safe to expose by default)

| Signal | Examples |
|--------|---------|
| HTTP `GET` method | `GET /repos/{owner}/{repo}` |
| HTTP `HEAD` method | `HEAD /files/{path}` |
| CLI verb: `get`, `list`, `show`, `describe`, `read`, `fetch`, `search`, `query`, `status`, `info`, `view` | `kubectl get pods`, `git log` |
| Function name prefix: `get_`, `list_`, `fetch_`, `read_`, `find_`, `search_`, `query_`, `describe_` | `get_user()`, `list_issues()` |
| Returns data without modifying state | Any pure fetch |

### Write (excluded by default; requires `--allow-destructive`)

| Signal | Examples |
|--------|---------|
| HTTP `POST`, `PUT`, `PATCH`, `DELETE` method | `DELETE /repos/{id}` |
| CLI verb: `create`, `update`, `delete`, `destroy`, `remove`, `edit`, `set`, `reset`, `push`, `apply`, `write` | `kubectl delete pod`, `git push` |
| Function name prefix: `create_`, `update_`, `delete_`, `set_`, `write_`, `apply_`, `destroy_`, `remove_` | `create_issue()`, `delete_file()` |
| Modifies external state, filesystem, or database | Any write or side effect |

**Borderline cases** (classify as write unless clearly safe):
- Trigger/dispatch operations — write
- Send/publish operations — write
- Sync/refresh that writes to remote — write
- Dry-run operations that only simulate — read

---

## Tool Count Heuristic

After listing all read operations:

- **5–15 operations**: Ideal. Proceed to Phase 2 design as-is.
- **15–20 operations**: Consider grouping. Which 2–3 operations always serve the same user intent?
- **> 20 operations**: Strong signal of over-wrapping. Phase 2 MUST group operations into workflow tools. Note grouping opportunities in `analysis.md`.
- **< 5 operations**: Thin API surface. Check if you missed CLI commands or exported functions.

---

## Output Format for `analysis.md`

Write the artifact with exactly these sections:

```markdown
# Analysis: {Repo Name}

## Service Purpose
{One sentence: what does this service/tool do?}

## Stack
- Language: {language}
- Framework: {framework or "none"}
- Package manager: {manager}
- Transport recommendation: stdio | HTTP (reason: {reason})

## Auth
- Pattern: {API key | OAuth | Basic | JWT | None}
- Required env vars: {VAR_NAME_1}, {VAR_NAME_2}

## Entities
| Entity | Description |
|--------|-------------|
| {name} | {what it represents} |

## Operations

### Read Operations
| Operation | Type | Path/Command/Function | Description |
|-----------|------|----------------------|-------------|
| {op_name} | REST GET | /path/{param} | {description} |

### Write Operations (excluded by default)
| Operation | Type | Path/Command/Function | Description |
|-----------|------|----------------------|-------------|
| {op_name} | REST POST | /path | {description} |

## Tool Count Signal
Read operations: {N}
Grouping opportunities: {list any identified}
Estimated tool count after grouping: {N}

## Notes
{Any unusual auth, rate limits, pagination requirements, or design flags}
```
