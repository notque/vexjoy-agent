#!/usr/bin/env python3
"""
GitHub API Fetcher — fetch repos, file contents, and PR reviews via GitHub REST API.

Caller: pipelines/github-profile-rules/SKILL.md (Phases 1-3)
Purpose: Lightweight GitHub data retrieval for programming rules extraction.
         Uses ONLY the GitHub REST API — no git clone, no subprocess git.

Usage:
    python3 scripts/github-api-fetcher.py repos --username USER [--token TOKEN] [--max-repos N] [--output-dir DIR]
    python3 scripts/github-api-fetcher.py sample-files --username USER --repo REPO [--token TOKEN] [--max-files N] [--output-dir DIR]
    python3 scripts/github-api-fetcher.py pr-reviews --username USER [--token TOKEN] [--max-reviews N] [--output-dir DIR]

Output: JSON to stdout and/or files in output-dir.
Exit codes: 0 = success, 1 = error.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

GITHUB_API_BASE = "https://api.github.com"


def make_request(url: str, token: str | None = None) -> tuple[dict | list | None, dict]:
    """Make a GitHub API request and return (data, headers).

    Returns (None, headers) on error. Handles rate limiting.
    """
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "github-profile-rules-fetcher/1.0",
    }
    if token:
        headers["Authorization"] = f"token {token}"

    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            resp_headers = dict(response.headers)
            remaining = resp_headers.get("X-RateLimit-Remaining", "unknown")

            # Rate limit warning
            try:
                if remaining != "unknown" and int(remaining) < 10:
                    reset_time = resp_headers.get("X-RateLimit-Reset", "0")
                    reset_dt = time.strftime("%H:%M:%S", time.localtime(int(reset_time)))
                    print(
                        f"WARNING: Rate limit low ({remaining} remaining). Resets at {reset_dt}",
                        file=sys.stderr,
                    )
            except (ValueError, TypeError):
                pass

            data = json.loads(response.read().decode("utf-8"))
            return data, resp_headers

    except urllib.error.HTTPError as e:
        if e.code == 403:
            resp_headers = dict(e.headers) if hasattr(e, "headers") else {}
            remaining = resp_headers.get("X-RateLimit-Remaining", "0")
            if remaining == "0":
                reset_time = resp_headers.get("X-RateLimit-Reset", "0")
                reset_dt = time.strftime("%H:%M:%S", time.localtime(int(reset_time)))
                print(
                    f"ERROR: Rate limit exceeded. Resets at {reset_dt}. Use --token for higher limits (5000 req/hr).",
                    file=sys.stderr,
                )
            return None, resp_headers
        elif e.code == 404:
            print(f"ERROR: Not found: {url}", file=sys.stderr)
            return None, {}
        else:
            print(f"ERROR: HTTP {e.code} for {url}: {e.reason}", file=sys.stderr)
            return None, {}
    except urllib.error.URLError as e:
        print(f"ERROR: Connection failed for {url}: {e.reason}", file=sys.stderr)
        return None, {}
    except Exception as e:
        print(f"ERROR: Unexpected error for {url}: {e}", file=sys.stderr)
        return None, {}


def check_rate_limit(token: str | None = None) -> dict:
    """Check current rate limit status."""
    data, _ = make_request(f"{GITHUB_API_BASE}/rate_limit", token)
    if data:
        core = data.get("rate", {})
        return {
            "limit": core.get("limit", 0),
            "remaining": core.get("remaining", 0),
            "reset": core.get("reset", 0),
        }
    return {"limit": 0, "remaining": 0, "reset": 0}


def cmd_repos(args: argparse.Namespace) -> int:
    """Fetch public repos for a user, sorted by stars."""
    username = args.username
    token = args.token
    max_repos = args.max_repos
    output_dir = args.output_dir

    # Verify user exists
    user_data, _ = make_request(f"{GITHUB_API_BASE}/users/{username}", token)
    if user_data is None:
        print(f"ERROR: User '{username}' not found.", file=sys.stderr)
        return 1

    public_repos_count = user_data.get("public_repos", 0)
    if public_repos_count == 0:
        print(f"ERROR: User '{username}' has no public repositories.", file=sys.stderr)
        return 1

    # Fetch repos (paginated, sorted by stars)
    repos = []
    page = 1
    per_page = min(max_repos, 100)

    while len(repos) < max_repos:
        url = f"{GITHUB_API_BASE}/users/{username}/repos?sort=stars&direction=desc&per_page={per_page}&page={page}"
        data, _ = make_request(url, token)
        if not data:
            break

        repos.extend(data)
        if len(data) < per_page:
            break
        page += 1

    repos = repos[:max_repos]

    # Build output
    result = {
        "username": username,
        "public_repos_total": public_repos_count,
        "repos_fetched": len(repos),
        "user_profile": {
            "name": user_data.get("name", ""),
            "bio": user_data.get("bio", ""),
            "company": user_data.get("company", ""),
            "location": user_data.get("location", ""),
            "blog": user_data.get("blog", ""),
            "created_at": user_data.get("created_at", ""),
        },
        "repos": [],
    }

    for repo in repos:
        repo_info = {
            "name": repo.get("name", ""),
            "full_name": repo.get("full_name", ""),
            "description": repo.get("description", ""),
            "language": repo.get("language", ""),
            "stars": repo.get("stargazers_count", 0),
            "forks": repo.get("forks_count", 0),
            "open_issues": repo.get("open_issues_count", 0),
            "created_at": repo.get("created_at", ""),
            "updated_at": repo.get("updated_at", ""),
            "pushed_at": repo.get("pushed_at", ""),
            "default_branch": repo.get("default_branch", "main"),
            "has_wiki": repo.get("has_wiki", False),
            "topics": repo.get("topics", []),
            "license": (repo.get("license") or {}).get("spdx_id", ""),
            "fork": repo.get("fork", False),
            "size": repo.get("size", 0),
        }
        result["repos"].append(repo_info)

    # Language distribution
    lang_counts: dict[str, int] = {}
    for r in result["repos"]:
        lang = r.get("language")
        if lang:
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
    result["language_distribution"] = dict(sorted(lang_counts.items(), key=lambda x: x[1], reverse=True))

    # Output
    output_json = json.dumps(result, indent=2)

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "repos.json")
        with open(output_path, "w") as f:
            f.write(output_json)
        print(f"Saved repos to {output_path}", file=sys.stderr)

    print(output_json)
    return 0


def cmd_sample_files(args: argparse.Namespace) -> int:
    """Fetch sample file contents from a repo via API."""
    username = args.username
    repo = args.repo
    token = args.token
    max_files = args.max_files
    output_dir = args.output_dir

    # Get file tree
    # First get default branch
    repo_data, _ = make_request(f"{GITHUB_API_BASE}/repos/{username}/{repo}", token)
    if repo_data is None:
        print(f"ERROR: Repo '{username}/{repo}' not found.", file=sys.stderr)
        return 1

    default_branch = repo_data.get("default_branch", "main")

    # Get recursive tree
    tree_data, _ = make_request(
        f"{GITHUB_API_BASE}/repos/{username}/{repo}/git/trees/{default_branch}?recursive=1",
        token,
    )
    if tree_data is None:
        print(f"ERROR: Could not fetch tree for '{username}/{repo}'.", file=sys.stderr)
        return 1

    tree = tree_data.get("tree", [])

    # Filter for code files (skip binaries, vendor, node_modules, etc.)
    skip_dirs = {
        "vendor",
        "node_modules",
        ".git",
        "dist",
        "build",
        "__pycache__",
        ".tox",
        ".eggs",
        "venv",
        ".venv",
    }
    code_extensions = {
        ".go",
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".rb",
        ".rs",
        ".java",
        ".kt",
        ".swift",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".cs",
        ".php",
        ".sh",
        ".bash",
        ".zsh",
        ".fish",
        ".yml",
        ".yaml",
        ".toml",
        ".json",
        ".md",
    }

    candidate_files = []
    for item in tree:
        if item.get("type") != "blob":
            continue
        path = item.get("path", "")

        # Skip excluded directories
        parts = path.split("/")
        if any(p in skip_dirs for p in parts):
            continue

        # Check extension
        _, ext = os.path.splitext(path)
        if ext.lower() in code_extensions:
            candidate_files.append(
                {
                    "path": path,
                    "size": item.get("size", 0),
                    "sha": item.get("sha", ""),
                }
            )

    # Sort by size (prefer smaller, more readable files) and sample
    candidate_files.sort(key=lambda x: x["size"])
    # Take a mix: some small, some medium
    sampled = candidate_files[:max_files]

    result = {
        "username": username,
        "repo": repo,
        "total_files_in_tree": len(tree),
        "candidate_code_files": len(candidate_files),
        "files_sampled": len(sampled),
        "files": [],
    }

    for file_info in sampled:
        path = file_info["path"]
        # Fetch file content via API
        content_data, _ = make_request(
            f"{GITHUB_API_BASE}/repos/{username}/{repo}/contents/{path}",
            token,
        )
        if content_data is None:
            continue

        # Content is base64 encoded
        import base64

        content_b64 = content_data.get("content", "")
        try:
            content = base64.b64decode(content_b64).decode("utf-8", errors="replace")
        except Exception:
            content = "[binary or decode error]"

        # Truncate very large files
        max_content_len = 5000
        truncated = len(content) > max_content_len
        if truncated:
            content = content[:max_content_len] + "\n... [truncated]"

        result["files"].append(
            {
                "path": path,
                "size": file_info["size"],
                "content": content,
                "truncated": truncated,
                "language": os.path.splitext(path)[1].lstrip("."),
            }
        )

    output_json = json.dumps(result, indent=2)

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        safe_repo = repo.replace("/", "_")
        output_path = os.path.join(output_dir, f"files-{safe_repo}.json")
        with open(output_path, "w") as f:
            f.write(output_json)
        print(f"Saved file samples to {output_path}", file=sys.stderr)

    print(output_json)
    return 0


def cmd_pr_reviews(args: argparse.Namespace) -> int:
    """Fetch PR reviews given by a user across their repos."""
    username = args.username
    token = args.token
    max_reviews = args.max_reviews
    output_dir = args.output_dir

    result = {
        "username": username,
        "reviews_fetched": 0,
        "reviews": [],
        "repos_checked": 0,
    }

    # Strategy: Search for PRs where user has commented/reviewed
    # Use the search API to find review comments by user
    search_url = (
        f"{GITHUB_API_BASE}/search/issues?q=reviewed-by:{username}+is:pr+is:public&sort=updated&order=desc&per_page=30"
    )

    search_data, _ = make_request(search_url, token)
    if search_data is None:
        print(f"WARNING: Could not search for reviews by '{username}'.", file=sys.stderr)
        # Fall back: check user's own repos for PR reviews
        search_data = {"items": []}

    prs = search_data.get("items", [])[:max_reviews]

    for pr in prs:
        pr_url = pr.get("pull_request", {}).get("url", "")
        if not pr_url:
            continue

        # Fetch PR reviews
        reviews_url = f"{pr_url}/reviews"
        reviews_data, _ = make_request(reviews_url, token)
        if not reviews_data:
            continue

        # Filter for reviews by this user
        user_reviews = [r for r in reviews_data if (r.get("user") or {}).get("login", "").lower() == username.lower()]

        for review in user_reviews:
            result["reviews"].append(
                {
                    "pr_title": pr.get("title", ""),
                    "pr_url": pr.get("html_url", ""),
                    "repo": pr.get("repository_url", "").replace(f"{GITHUB_API_BASE}/repos/", ""),
                    "state": review.get("state", ""),
                    "body": review.get("body", "") or "",
                    "submitted_at": review.get("submitted_at", ""),
                }
            )

        # Also fetch review comments (inline comments)
        comments_url = f"{pr_url}/comments"
        comments_data, _ = make_request(comments_url, token)
        if comments_data:
            user_comments = [
                c for c in comments_data if (c.get("user") or {}).get("login", "").lower() == username.lower()
            ]
            for comment in user_comments:
                result["reviews"].append(
                    {
                        "pr_title": pr.get("title", ""),
                        "pr_url": pr.get("html_url", ""),
                        "repo": pr.get("repository_url", "").replace(f"{GITHUB_API_BASE}/repos/", ""),
                        "state": "COMMENT",
                        "body": comment.get("body", "") or "",
                        "path": comment.get("path", ""),
                        "diff_hunk": comment.get("diff_hunk", ""),
                        "submitted_at": comment.get("created_at", ""),
                    }
                )

        result["repos_checked"] += 1

    result["reviews_fetched"] = len(result["reviews"])

    output_json = json.dumps(result, indent=2)

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "pr-reviews.json")
        with open(output_path, "w") as f:
            f.write(output_json)
        print(f"Saved PR reviews to {output_path}", file=sys.stderr)

    print(output_json)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="github-api-fetcher",
        description=(
            "Fetch GitHub user data via REST API for programming rules extraction. "
            "API-only: no git clone, no subprocess git."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # repos command
    repos_parser = subparsers.add_parser("repos", help="List public repos for a user, sorted by stars")
    repos_parser.add_argument("--username", required=True, help="GitHub username to analyze")
    repos_parser.add_argument(
        "--token", default=None, help="GitHub personal access token (optional, for higher rate limits)"
    )
    repos_parser.add_argument("--max-repos", type=int, default=10, help="Maximum repos to fetch (default: 10)")
    repos_parser.add_argument("--output-dir", default=None, help="Directory to save output files")

    # sample-files command
    files_parser = subparsers.add_parser("sample-files", help="Sample code files from a repo via API")
    files_parser.add_argument("--username", required=True, help="GitHub username (repo owner)")
    files_parser.add_argument("--repo", required=True, help="Repository name")
    files_parser.add_argument("--token", default=None, help="GitHub personal access token")
    files_parser.add_argument("--max-files", type=int, default=10, help="Maximum files to sample (default: 10)")
    files_parser.add_argument("--output-dir", default=None, help="Directory to save output files")

    # pr-reviews command
    reviews_parser = subparsers.add_parser("pr-reviews", help="Fetch PR reviews given by a user")
    reviews_parser.add_argument("--username", required=True, help="GitHub username")
    reviews_parser.add_argument("--token", default=None, help="GitHub personal access token")
    reviews_parser.add_argument(
        "--max-reviews", type=int, default=20, help="Maximum PRs to check for reviews (default: 20)"
    )
    reviews_parser.add_argument("--output-dir", default=None, help="Directory to save output files")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    commands = {
        "repos": cmd_repos,
        "sample-files": cmd_sample_files,
        "pr-reviews": cmd_pr_reviews,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
