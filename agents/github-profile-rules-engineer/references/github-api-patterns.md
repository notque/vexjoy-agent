<!--
scope: github-profile-rules-engineer
version: 1.0.0
date: 2026-04-05
purpose: GitHub REST API usage patterns for profile analysis
level: 3 (API endpoints, rate limit handling, pagination, error-fix mappings)
-->

# GitHub API Patterns — GitHub Profile Rules Engineer

Key endpoints, rate limit handling, pagination, and sampling strategy for extracting rules from public GitHub profiles.

---

## Key Endpoints

| Purpose | Method + URL | Returns | Notes |
|---------|-------------|---------|-------|
| User info | `GET /users/{username}` | Profile, `public_repos`, `login` | Verify user exists before bulk fetching |
| Repo listing | `GET /users/{username}/repos?sort=pushed&per_page=100` | Array of repo objects with `pushed_at`, `language`, `fork` | Sort by `pushed_at` for activity order |
| File tree | `GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1` | Tree of all paths + `truncated` flag | May be truncated at 100k entries |
| File contents | `GET /repos/{owner}/{repo}/contents/{path}` | `content` (base64), `encoding`, `sha` | Decode before analyzing |
| Commits list | `GET /repos/{owner}/{repo}/commits?per_page=30` | Array with `author`, `commit.message` | Use for activity recency, not rule extraction |
| PR list | `GET /repos/{owner}/{repo}/pulls?state=all&per_page=50` | Array with `number`, `user.login` | Filter by author to get developer's PRs |
| PR review comments | `GET /repos/{owner}/{repo}/pulls/{pull_number}/reviews` | Array of review objects with `body`, `state` | `CHANGES_REQUESTED` reviews = strongest preference signals |
| PR inline comments | `GET /repos/{owner}/{repo}/pulls/{pull_number}/comments` | Line-level comments with `path`, `line`, `body` | Highest-signal source for style preferences |
| Default branch | `GET /repos/{owner}/{repo}` | `default_branch`, `pushed_at`, `size` | Get SHA for tree fetching |

---

## Rate Limit Handling

GitHub applies two limits: unauthenticated (60 req/hr) and authenticated (5000 req/hr). Always check headers.

**Check before each request:**

```python
# WebFetch pattern — inspect response headers
response = WebFetch("https://api.github.com/users/{username}", headers={
    "Authorization": "token {token}",  # omit if unauthenticated
    "Accept": "application/vnd.github+json"
})

remaining = int(response.headers.get("X-RateLimit-Remaining", 0))
reset_epoch = int(response.headers.get("X-RateLimit-Reset", 0))

if remaining < 10:
    # Back off — do not continue fetching
    # Report: "Rate limit near exhaustion. Resuming after {reset_epoch} epoch."
    # Convert reset_epoch to human time: datetime.fromtimestamp(reset_epoch)
    raise RateLimitNearExhaustion(reset_at=reset_epoch)
```

**Key rule:** Back off when `X-RateLimit-Remaining < 10`, not when it hits 0. Hitting 0 causes 403 errors that look like auth failures.

**With token:** Provide `Authorization: Bearer {token}` in headers. Token raises limit from 60 to 5000 requests per hour.

---

## Pagination

GitHub paginates at 100 items per page for most endpoints. Iterate using the `Link` header.

```python
# Pattern: follow Link rel="next" until absent
url = "https://api.github.com/users/{username}/repos?per_page=100&sort=pushed"
all_repos = []

while url:
    response = WebFetch(url, headers={"Accept": "application/vnd.github+json"})
    all_repos.extend(response.json())

    # Link header format:
    # <https://api.github.com/...?page=2>; rel="next", <...?page=5>; rel="last"
    link_header = response.headers.get("Link", "")
    next_url = None
    for part in link_header.split(","):
        if 'rel="next"' in part:
            next_url = part.split(";")[0].strip().strip("<>")
    url = next_url
```

**Note:** For repo listing, stop paginating once you have the top 5 by `pushed_at`. Fetching all 100+ repos wastes rate limit budget.

---

## Raw File Content: Decoding

`GET /repos/{owner}/{repo}/contents/{path}` returns base64-encoded content. Always decode.

```python
import base64

response = WebFetch(
    "https://api.github.com/repos/{owner}/{repo}/contents/{path}",
    headers={"Accept": "application/vnd.github+json"}
)
data = response.json()

# Guard: API returns array for directories, dict for files
if isinstance(data, list):
    # Path is a directory — pick files from listing instead
    raise ValueError(f"{path} is a directory, not a file")

if data.get("encoding") == "base64":
    content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
else:
    content = data.get("content", "")
```

**Large file guard:** Files over 1MB return `content: null` with a `download_url`. Fetch `download_url` directly for large files, or skip files over 500KB — they are unlikely to show style patterns efficiently.

---

## Sampling Strategy

**Repo selection:** Take top 5 repos by `pushed_at`, excluding forks (`fork: false`). Do not sort by stars — popular repos may be old showcase work that predates current style.

```python
repos = sorted(
    [r for r in all_repos if not r["fork"]],
    key=lambda r: r["pushed_at"],
    reverse=True
)[:5]
```

**File selection per repo:** Sample 20 files maximum. Prioritize:
1. Files in root-level source directories (not generated, not vendor)
2. Mix of file types if polyglot repo
3. Skip: `vendor/`, `node_modules/`, `*.min.js`, `*_generated.go`, `*.pb.go`, `dist/`

```python
skip_paths = {"vendor/", "node_modules/", "dist/", ".git/"}
skip_suffixes = (".min.js", "_generated.go", ".pb.go", ".lock")

sampled = [
    entry for entry in tree["tree"]
    if entry["type"] == "blob"
    and not any(entry["path"].startswith(p) for p in skip_paths)
    and not any(entry["path"].endswith(s) for s in skip_suffixes)
][:20]
```

---

## Correct Patterns

### Pattern: Fetch PR reviews for preference signals

PR `CHANGES_REQUESTED` reviews are the strongest signal for developer preferences — they chose to block a merge over a specific pattern.

```python
# Get PRs authored by the target developer
prs = WebFetch(
    f"https://api.github.com/repos/{owner}/{repo}/pulls?state=all&per_page=30",
    headers={"Accept": "application/vnd.github+json"}
).json()

target_prs = [pr for pr in prs if pr["user"]["login"] != username]
# ^ PRs where the developer is the REVIEWER, not the author

for pr in target_prs[:10]:
    reviews = WebFetch(
        f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr['number']}/reviews"
    ).json()
    for review in reviews:
        if review["user"]["login"] == username and review["state"] == "CHANGES_REQUESTED":
            # High-signal: developer explicitly requested a change
            inline = WebFetch(
                f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr['number']}/comments"
            ).json()
            # Extract patterns from inline comment bodies
```

### Pattern: Resolve default branch SHA for tree fetch

```python
repo_meta = WebFetch(f"https://api.github.com/repos/{owner}/{repo}").json()
default_branch = repo_meta["default_branch"]
branch_data = WebFetch(
    f"https://api.github.com/repos/{owner}/{repo}/branches/{default_branch}"
).json()
sha = branch_data["commit"]["sha"]

tree = WebFetch(
    f"https://api.github.com/repos/{owner}/{repo}/git/trees/{sha}?recursive=1"
).json()

if tree.get("truncated"):
    # Tree exceeds 100k entries — do not rely on completeness
    # Sample from known source directories instead
    pass
```

---

## Anti-Pattern Catalog

| Anti-Pattern | Why Wrong | Correct Approach |
|--------------|-----------|-----------------|
| **Recursive tree on large repos without checking `truncated`** | Tree silently omits files beyond 100k entries; missing files create false "absence" signals | Always check `tree["truncated"]`; if true, fetch subdirectory trees explicitly |
| **Analyzing only the default branch** | Developer may be iterating style in a feature branch; main may reflect old conventions | Check `pushed_at` across branches; if a non-default branch is more recently pushed, sample it too |
| **Fetching entire file list before filtering** | Wastes rate limit on vendor/generated files | Apply path filters before fetching file contents |
| **Using stars as proxy for activity** | High-star repos may be years old with different style | Sort repos by `pushed_at`, not `stargazers_count` |
| **Treating 403 as definitive auth failure** | 403 can mean rate limited OR auth required — they look identical | Check `X-RateLimit-Remaining` first; if > 0, the 403 is an auth failure, not rate limiting |
| **Skipping fork check** | Forked repos contain upstream code, not developer's style | Filter `fork: false` before sampling |

---

## Error-Fix Mappings

| Status | Scenario | Diagnosis | Fix |
|--------|----------|-----------|-----|
| `403` | `X-RateLimit-Remaining: 0` | Rate limited | Wait until `X-RateLimit-Reset` epoch; offer user token prompt |
| `403` | `X-RateLimit-Remaining: 60` (or high) | Auth required for this endpoint | Endpoint needs token; report scope needed |
| `404` | User endpoint | Username doesn't exist | Report "User not found" — do not proceed |
| `404` | Repo contents endpoint | Repo exists but path doesn't, OR repo is private | Skip this path; log as inaccessible |
| `422` | Tree or commits endpoint | Invalid ref or SHA | Re-fetch repo metadata to get fresh default branch SHA |
| `451` | Any endpoint | DMCA takedown / legal restriction | Skip repo entirely; log as unavailable |
| `503` | Any endpoint | GitHub degraded | Retry after 30s; report if persistent |

---

## Detection Commands Reference

Use these patterns when validating fetched data quality before rule extraction:

```bash
# Verify repos are sorted by activity, not stars
# (check pushed_at values in fetched repo list)
python3 -c "
import json, sys
repos = json.load(sys.stdin)
for r in repos[:5]:
    print(r['name'], r['pushed_at'], 'fork:', r['fork'])
"

# Confirm tree is not truncated
python3 -c "
import json, sys
tree = json.load(sys.stdin)
print('truncated:', tree.get('truncated', False))
print('entries:', len(tree.get('tree', [])))
"

# Check rate limit headroom before bulk analysis
curl -sI https://api.github.com/rate_limit \
  -H "Authorization: Bearer {token}" | grep -i ratelimit
```
