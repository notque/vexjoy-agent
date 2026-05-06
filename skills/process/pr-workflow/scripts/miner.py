#!/usr/bin/env python3
"""
PR Miner: Extract tribal knowledge from GitHub PR reviews

USAGE:
    python3 miner.py owner/repo output.json
    python3 miner.py owner/repo output.json --limit 100
    python3 miner.py repo1,repo2,repo3 output.json --limit 50
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from github import Github, GithubException
except ImportError:
    print("Error: PyGithub not installed. Run: pip install PyGithub")
    sys.exit(1)


# Imperative keywords that indicate coding standards
IMPERATIVE_KEYWORDS = [
    "should",
    "must",
    "please",
    "always",
    "never",
    "avoid",
    "use",
    "prefer",
    "instead",
    "don't",
    "do not",
    "violates",
    "breaks",
    "needs to",
    "has to",
    "requirement",
    "required",
    "mandatory",
    "better to",
    "consider",
    "recommend",
]


class PRMiner:
    """Mines GitHub PRs for tribal knowledge"""

    def __init__(self, github_token: str):
        self.github = Github(github_token)
        self.interactions = []
        self.stats = {"prs_analyzed": 0, "comments_found": 0, "interactions_extracted": 0, "api_calls": 0}

    def mine_repo(
        self,
        repo_name: str,
        limit: int = 50,
        since: Optional[str] = None,
        reviewer_filter: Optional[str] = None,
        all_comments: bool = False,
    ):
        """Mine a single repository for tribal knowledge"""
        print(f"\n⛏️  Mining {repo_name}...")

        try:
            repo = self.github.get_repo(repo_name)
            self.stats["api_calls"] += 1
        except GithubException as e:
            print(f"Error accessing repo {repo_name}: {e}")
            return

        # Get merged PRs
        pulls = repo.get_pulls(state="closed", sort="updated", direction="desc")
        self.stats["api_calls"] += 1

        count = 0
        for pr in pulls:
            if count >= limit:
                break

            # Skip unmerged PRs
            if not pr.merged:
                continue

            # Date filter
            if since and pr.updated_at < datetime.fromisoformat(since).replace(tzinfo=timezone.utc):
                continue

            self.stats["prs_analyzed"] += 1

            # Mine review comments
            try:
                comments = pr.get_review_comments()
                self.stats["api_calls"] += 1

                for comment in comments:
                    self.stats["comments_found"] += 1

                    # Reviewer filter
                    if reviewer_filter and comment.user.login != reviewer_filter:
                        continue

                    # Check for imperative keywords (skip if all_comments flag is set)
                    if not all_comments and not self._has_imperative(comment.body):
                        continue

                    # Extract interaction
                    interaction = self._extract_interaction(pr, comment)
                    if interaction:
                        self.interactions.append(interaction)
                        self.stats["interactions_extracted"] += 1

                # Show progress
                sys.stdout.write(f"\r  PR #{pr.number}: {self.stats['interactions_extracted']} interactions found")
                sys.stdout.flush()

            except GithubException as e:
                print(f"\n  Warning: Error processing PR #{pr.number}: {e}")
                continue

            count += 1

        print(f"\n✓ {repo_name}: Analyzed {self.stats['prs_analyzed']} PRs")

    def _has_imperative(self, text: str) -> bool:
        """Check if comment contains imperative keywords"""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in IMPERATIVE_KEYWORDS)

    def _extract_interaction(self, pr, comment) -> Optional[Dict]:
        """Extract structured interaction data from PR comment"""
        try:
            # Parse diff hunk for code context
            code_before, code_after = self._parse_diff_hunk(comment.diff_hunk)

            # Determine resolution
            resolution = self._determine_resolution(pr, comment)

            return {
                "source": "pr_review",
                "pr_number": pr.number,
                "pr_title": pr.title,
                "pr_url": pr.html_url,
                "author": pr.user.login,
                "reviewer": comment.user.login,
                "file": comment.path,
                "line": comment.original_line or comment.line,
                "comment_text": comment.body,
                "diff_hunk": comment.diff_hunk,
                "code_before": code_before,
                "code_after": code_after,
                "resolution": resolution,
                "comment_url": comment.html_url,
                "created_at": comment.created_at.isoformat(),
                "pr_merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
            }
        except Exception as e:
            print(f"\n  Warning: Failed to extract interaction: {e}")
            return None

    def _parse_diff_hunk(self, diff_hunk: str) -> Tuple[str, str]:
        """
        Parse diff hunk to extract before/after code

        Diff hunk format:
        @@ -42,7 +42,7 @@
         context line
        -removed line
        +added line
         context line
        """
        if not diff_hunk:
            return "", ""

        lines = diff_hunk.split("\n")
        before_lines = []
        after_lines = []

        for line in lines[1:]:  # Skip header line
            if line.startswith("-") and not line.startswith("---"):
                before_lines.append(line[1:])  # Remove '-' prefix
            elif line.startswith("+") and not line.startswith("+++"):
                after_lines.append(line[1:])  # Remove '+' prefix
            elif not line.startswith("@"):
                # Context line - include in both
                before_lines.append(line[1:] if line else line)
                after_lines.append(line[1:] if line else line)

        return "\n".join(before_lines).strip(), "\n".join(after_lines).strip()

    def _determine_resolution(self, pr, comment) -> str:  # noqa: ARG002
        """
        Determine if comment led to code change

        Heuristics:
        1. Check if file was modified after comment
        2. Check if comment thread was resolved
        3. Check review state after comment
        """
        # Simple heuristic: if PR was merged and comment wasn't dismissed, likely changed
        # More sophisticated: would need to check commits after comment timestamp
        # For now, mark as "likely_changed" if merged, "unresolved" otherwise

        if pr.merged:
            # Check if comment has replies
            # More replies = more discussion = more likely changed
            return "likely_changed"
        else:
            return "unresolved"

    def save_results(self, output_file: str, repos: List[str]):
        """Save mined interactions to JSON"""
        data = {
            "metadata": {
                "repos": repos,
                "mined_at": datetime.now(timezone.utc).isoformat(),
                "pr_count": self.stats["prs_analyzed"],
                "comment_count": self.stats["comments_found"],
                "interaction_count": self.stats["interactions_extracted"],
                "api_calls": self.stats["api_calls"],
            },
            "interactions": self.interactions,
        }

        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)

        print("\n✅ Mining complete!")
        print(f"   PRs analyzed: {self.stats['prs_analyzed']}")
        print(f"   Comments found: {self.stats['comments_found']}")
        print(f"   Interactions extracted: {self.stats['interactions_extracted']}")
        print(f"   Saved to: {output_file}")

    def show_summary(self):
        """Show summary statistics"""
        if not self.interactions:
            print("No interactions found")
            return

        print("\n" + "=" * 80)
        print("MINING SUMMARY")
        print("=" * 80)

        # Top reviewers
        reviewer_counts = {}
        for interaction in self.interactions:
            reviewer = interaction["reviewer"]
            reviewer_counts[reviewer] = reviewer_counts.get(reviewer, 0) + 1

        print("\nTop Reviewers:")
        for reviewer, count in sorted(reviewer_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {reviewer}: {count} comments")

        # Top files
        file_counts = {}
        for interaction in self.interactions:
            file = interaction["file"]
            file_counts[file] = file_counts.get(file, 0) + 1

        print("\nMost Commented Files:")
        for file, count in sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {file}: {count} comments")

        # Keyword frequency
        keyword_counts = {}
        for interaction in self.interactions:
            text = interaction["comment_text"].lower()
            for keyword in IMPERATIVE_KEYWORDS:
                if keyword in text:
                    keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1

        print("\nTop Keywords:")
        for keyword, count in sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  '{keyword}': {count} occurrences")


def get_github_token() -> Optional[str]:
    """Get GitHub token from environment or file"""
    # Try environment variable
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return token

    # Try ~/.github-token file
    token_file = Path.home() / ".github-token"
    if token_file.exists():
        return token_file.read_text().strip()

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Mine GitHub PRs for tribal knowledge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 miner.py your-org/your-repo output.json
  python3 miner.py your-org/your-repo output.json --limit 100
  python3 miner.py your-org/your-repo,your-org/metrics-service output.json --limit 50
  python3 miner.py your-org/your-repo output.json --reviewer senior-reviewer
  python3 miner.py your-org/your-repo output.json --since 2024-06-01
        """,
    )

    parser.add_argument("repos", help="Repository name(s) (owner/repo or repo1,repo2)")
    parser.add_argument("output", help="Output JSON file")
    parser.add_argument("--limit", type=int, default=50, help="Max PRs per repo (default: 50)")
    parser.add_argument("--since", help="Only PRs updated since date (YYYY-MM-DD)")
    parser.add_argument("--reviewer", help="Filter by specific reviewer")
    parser.add_argument("--all-comments", action="store_true", help="Capture ALL comments (skip keyword filter)")
    parser.add_argument("--summary", action="store_true", help="Show summary after mining")
    parser.add_argument("--check-auth", action="store_true", help="Check GitHub authentication")

    args = parser.parse_args()

    # Get GitHub token
    token = get_github_token()
    if not token:
        print("Error: GitHub token not found")
        print("Set GITHUB_TOKEN environment variable or create ~/.github-token")
        sys.exit(1)

    # Check authentication
    if args.check_auth:
        try:
            g = Github(token)
            user = g.get_user()
            print(f"✓ Authenticated as: {user.login}")
            print(f"  API rate limit: {g.get_rate_limit().core.remaining}/{g.get_rate_limit().core.limit}")
            sys.exit(0)
        except Exception as e:
            print(f"✗ Authentication failed: {e}")
            sys.exit(1)

    # Parse repos
    repos = [r.strip() for r in args.repos.split(",")]

    # Create miner
    miner = PRMiner(token)

    # Mine each repo
    for repo in repos:
        miner.mine_repo(
            repo, limit=args.limit, since=args.since, reviewer_filter=args.reviewer, all_comments=args.all_comments
        )

    # Save results
    miner.save_results(args.output, repos)

    # Show summary if requested
    if args.summary:
        miner.show_summary()


if __name__ == "__main__":
    main()
