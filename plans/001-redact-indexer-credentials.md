# Plan 001: The search-engine indexer never prints a credential

> **Executor instructions**: follow this plan step by step. Run every
> verification command and confirm the expected result before the next step.
> If a STOP condition occurs, stop and report. Do not improvise. Do not run
> any step marked OWNER-GATED. When done, update this plan's row in
> `plans/README.md`, unless a reviewer dispatched you and maintains the index.
>
> **Drift check (run first)**: `git diff --stat c0f87bbf..HEAD -- scripts/search-engine-indexer.py scripts/tests/test_search_engine_indexer.py`
> If an in-scope file changed, compare the "Current state" excerpts with the
> live code. A mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: security
- **Kind**: fix
- **Planned at**: commit `c0f87bbf`, 2026-11-09

## Why this matters

`scripts/search-engine-indexer.py` submits a URL to Google, IndexNow, and
Baidu. In `--dry-run` mode it returns, and then prints, the Baidu endpoint URL
with the push token in its query string, and the IndexNow payload with the API
key. On a network error it prints `str(exception)`, and a `requests` exception
message contains the request URL, so the Baidu token prints there too. Agents
run this script and its stdout lands in chat transcripts and logs. This host's
rules forbid printing credentials. After this plan, no output path of the
script contains either credential.

## Current state

`scripts/search-engine-indexer.py` is a standalone CLI (argparse, `requests`
imported at module top). No test file exists for it.

IndexNow, `scripts/search-engine-indexer.py:182-190`:

```python
    payload = {
        "host": host,
        "key": indexnow_key,
        "keyLocation": f"https://{host}/{indexnow_key}.txt",
        "urlList": [url],
    }

    if dry_run:
        return {"status": "dry_run", "endpoint": INDEXNOW_ENDPOINT, "payload": payload}
```

Baidu, `scripts/search-engine-indexer.py:232-235`:

```python
    endpoint = f"{BAIDU_PUSH_ENDPOINT}?site={site_url}&token={push_token}"

    if dry_run:
        return {"status": "dry_run", "endpoint": endpoint, "payload": url}
```

Both functions end with the same error path (`:206-207` and `:249-250`):

```python
    except requests.exceptions.RequestException as e:
        return {"status": "error", "error": str(e)}
```

Both also return `response.text[:300]` on a non-success status (`:204`, `:247`).

Printing, `scripts/search-engine-indexer.py:328-336` (inside `_output_result`):

```python
            elif api_status == "dry_run":
                print("    Status: Dry run")
                print(f"    Endpoint: {api_result.get('endpoint', '')}")
...
    else:
        print(json.dumps(result, indent=2))
```

Conventions:

- Redaction format on this host: `<redacted:type:last4>`, for example
  `<redacted:token:ab12>`.
- Tests load hyphenated scripts with `importlib`. Exemplar:
  `scripts/tests/test_generate_skill_index.py:1-22` (`_load_gsi`). Match it.
- Tests stay offline: never call a real endpoint; patch `requests.post` with
  `monkeypatch`.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Tests (this plan) | `python3 -m pytest scripts/tests/test_search_engine_indexer.py -n 0 -q` | all pass |
| Lint | `ruff check scripts/search-engine-indexer.py scripts/tests/test_search_engine_indexer.py --config pyproject.toml` | `All checks passed!` |
| Format | `ruff format --check scripts/search-engine-indexer.py scripts/tests/test_search_engine_indexer.py --config pyproject.toml` | exit 0 |

Do not run the script itself against a real `.env`, and do not read any `.env`
file.

## Scope

**In scope** (the only files to modify):
- `scripts/search-engine-indexer.py`
- `scripts/tests/test_search_engine_indexer.py` (create)

**Out of scope** (do not touch):
- The real request sent to Baidu or IndexNow: the live `requests.post` call
  must still carry the real token and key.
- `BAIDU_PUSH_ENDPOINT` (an `http://` URL). See Maintenance notes.
- `submit_google`: its dry-run returns no credential.
- Any `.env` file, `README.md`, and docs.

## Git workflow

- Branch: `fix/advisor-001-redact-indexer-credentials`.
- One commit. Message style: one lowercase past-tense sentence, no type
  prefix, no trailing period. Example from `git log`:
  `dropped the platform import from the stdin reader because it loaded subprocess into every hook on python 3.10`.
- No `Co-Authored-By` or "Generated with" lines.
- Do not push, open a PR, merge, deploy, or tag.

## Steps

### Step 1: Write the failing tests

Create `scripts/tests/test_search_engine_indexer.py`. Load the script with
`importlib.util.spec_from_file_location("search_engine_indexer", SCRIPT)`.
Use fake credentials defined in the test, for example
`FAKE_TOKEN = "tok-FAKE-0000-wxyz"` and `FAKE_KEY = "key-FAKE-1111-abcd"`.
Cases:

1. `submit_baidu(url, site, FAKE_TOKEN, dry_run=True)`: `json.dumps(result)`
   does not contain `FAKE_TOKEN`; `result["endpoint"]` contains
   `<redacted:token:wxyz>`.
2. `submit_indexnow(url, host, FAKE_KEY, dry_run=True)`: `json.dumps(result)`
   does not contain `FAKE_KEY`.
3. Baidu error path: monkeypatch `mod.requests.post` to raise
   `requests.exceptions.ConnectionError(f"failed: {endpoint_with_token}")`
   where the message contains `FAKE_TOKEN`; the returned `error` string does
   not contain `FAKE_TOKEN`.
4. IndexNow error path: same, with `FAKE_KEY` in the exception message.
5. Non-success status: monkeypatch `requests.post` to return an object with
   `status_code = 500` and `text` containing `FAKE_TOKEN`; the returned
   `error` does not contain it.
6. Live call still sends the real credential: monkeypatch `requests.post` to
   record its arguments and return `status_code = 200`; assert the recorded
   Baidu URL contains `FAKE_TOKEN` and the recorded IndexNow `json` has
   `key == FAKE_KEY`.
7. `_output_result` in human and JSON mode on a full dry-run result (`capsys`):
   stdout contains neither fake credential.

**Verify**: `python3 -m pytest scripts/tests/test_search_engine_indexer.py -n 0 -q` → cases 1-5 and 7 fail, case 6 passes.

### Step 2: Add the redaction helpers

In `scripts/search-engine-indexer.py`, below the `load_env_file`/`get_config`
block, add two module-level functions:

```python
def _redact(value: str, kind: str) -> str:
    """Return the host's redaction marker for a credential."""
    return f"<redacted:{kind}:{value[-4:]}>" if value else ""


def _scrub(text: str, secret: str, kind: str) -> str:
    """Replace every occurrence of *secret* in *text* with its marker."""
    return text.replace(secret, _redact(secret, kind)) if secret else text
```

**Verify**: `ruff check scripts/search-engine-indexer.py --config pyproject.toml` → `All checks passed!`

### Step 3: Redact the dry-run results and error strings

- `submit_baidu` dry-run: return an endpoint built with
  `_redact(push_token, "token")` in place of the token. Keep the real
  `endpoint` variable for the live `requests.post`.
- `submit_indexnow` dry-run: return a copy of `payload` with `key` set to
  `_redact(indexnow_key, "api-key")` and `keyLocation` built from the same
  marker. Do not mutate the `payload` used by the live call.
- In both functions, pass every returned `error` string (`str(e)` and
  `response.text[:300]`) through `_scrub` with that function's credential.

**Verify**: `python3 -m pytest scripts/tests/test_search_engine_indexer.py -n 0 -q` → all 7 pass.

### Step 4: Lint and format

**Verify**: the Lint and Format commands in the table → both succeed.

### Step 5 (OWNER-GATED: owner decision, credential rotation): Rotate if exposed

For the owner. If this script ever ran with `--dry-run`, or hit a network
error, in a session whose output was logged or kept in a transcript, rotate
`BAIDU_PUSH_TOKEN` (ziyuan.baidu.com) and `INDEXNOW_KEY`. The executor skips
this step and reports it as pending.

## Test plan

- New file `scripts/tests/test_search_engine_indexer.py`, 7 cases above.
- Structure model: `scripts/tests/test_generate_skill_index.py`.
- Verification: `python3 -m pytest scripts/tests/test_search_engine_indexer.py -n 0 -q` → 7 passed.

## Done criteria

- [ ] `python3 -m pytest scripts/tests/test_search_engine_indexer.py -n 0 -q` exits 0 with 7 tests passed
- [ ] `ruff check . --config pyproject.toml` exits 0
- [ ] `ruff format --check . --config pyproject.toml` exits 0
- [ ] `grep -n '"endpoint": endpoint' scripts/search-engine-indexer.py` returns no matches
- [ ] `git status --short` shows only the two in-scope files (plus `plans/README.md` if you maintain the index)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report if:

- The code at the "Current state" locations does not match the excerpts.
- A step's verification fails twice after a reasonable fix attempt.
- The fix needs a file outside the in-scope list.
- A test would need a real credential, a real `.env` file, or a network call.
- Case 6 fails after step 3: the live request no longer carries the real
  credential, so the script is broken.
- A step would need a deploy, a credential, a public listener, a scheduled
  job, data deletion, or a request to a third party.

## Maintenance notes

- A reviewer should check that every `return` in `submit_indexnow` and
  `submit_baidu` that includes text from the network or an exception goes
  through `_scrub`.
- Deferred: `BAIDU_PUSH_ENDPOINT` is `http://`, so the token travels in
  cleartext. Whether Baidu accepts `https://` on that host needs a live check,
  which is third-party egress. The owner decides.
- If a new search engine is added, its dry-run and error paths need the same
  treatment; extend test cases 1-5.
