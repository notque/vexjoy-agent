#!/usr/bin/env python3
"""Work-proportional review sizing.

Maps a change's scope (changed-file count + package count) to a FILE_SCOPE_TIER
(1-4) and a recommended review composition. The point: stop paying a fixed
multi-agent tax. A 3-file change does not need a 27-agent four-wave review.

Tiers:
  Tier 1 (1-5 files, 1 pkg)    -> parallel-code-review, 3 agents
  Tier 2 (6-20 files, 1-2 pkg) -> comprehensive Wave 1 only (12)
  Tier 3 (21-50 files, 3-5 pkg)-> Wave 1 + Wave 2 subset (12+5); Wave 3 only on CRITICAL
  Tier 4 (50+ files, 5+ pkg)   -> full Wave 1+2+3 (12+10+5)

The max-rule: file count and package count each map to a tier independently;
the larger tier wins. A few files spread across many packages is a wide change.

Usage:
    python3 scripts/right-size-review.py --files 12 --packages 2
    python3 scripts/right-size-review.py --base main --head HEAD
    python3 scripts/right-size-review.py            # diff vs HEAD (working tree)

Output: JSON {tier, FILE_SCOPE_TIER, waves, agent_estimate, recommended, ...}.
Exit 0 always (a sizing signal never blocks a review).
"""

import argparse
import json
import re
import subprocess
import sys

# Validates the --findings value: NC/NH/NM (critical/high/medium counts).
_FINDINGS_RE = re.compile(r"^(\d+)C/(\d+)H/(\d+)M$", re.IGNORECASE)


def _tier_from_value(value: int, bounds: list[int]) -> int:
    """Return the 1-based tier for `value` given ascending upper bounds."""
    for i, upper in enumerate(bounds, start=1):
        if value <= upper:
            return i
    return len(bounds) + 1


def compute_tier(file_count: int, package_count: int) -> int:
    """Tier 1-4 from file and package counts. The larger of the two wins.

    File-derived bounds: <=5 -> 1, <=20 -> 2, <=50 -> 3, else 4.
    Package-derived bounds: <=1 -> 1, <=2 -> 2, <=5 -> 3, else 4.
    """
    file_tier = _tier_from_value(max(file_count, 0), [5, 20, 50])
    pkg_tier = _tier_from_value(max(package_count, 0), [1, 2, 5])
    return max(file_tier, pkg_tier)


def composition_for_tier(tier: int) -> dict:
    """Recommended review composition for a tier.

    agent_estimate is the up-front agent count; Wave 3 escalation on a CRITICAL
    finding (Tier 3) adds agents at runtime and is not counted here.
    """
    table = {
        1: {
            "waves": [],
            "agent_estimate": 3,
            "recommended": "parallel-code-review (3 reviewers: security, business, architecture)",
            "wave3_on_critical": False,
        },
        2: {
            "waves": [1],
            "agent_estimate": 12,
            "recommended": "comprehensive-review --wave1-only (12 foundation agents)",
            "wave3_on_critical": False,
        },
        3: {
            "waves": [1, 2],
            "agent_estimate": 17,  # Wave 1 (12) + Wave 2 subset (5)
            "recommended": "comprehensive-review Wave 1 + Wave 2 subset; Wave 3 only if a CRITICAL is found",
            "wave3_on_critical": True,
        },
        4: {
            "waves": [1, 2, 3],
            "agent_estimate": 27,  # Wave 1 (12) + Wave 2 (10) + Wave 3 (5)
            "recommended": "comprehensive-review full (Wave 1+2+3)",
            "wave3_on_critical": False,
        },
    }
    return table[tier]


def _git_scope(base: str | None, head: str) -> tuple[int, int]:
    """Compute (file_count, package_count) from a git range.

    Falls back to the working-tree diff vs HEAD when base is not given.
    Package count = distinct parent directories of changed files.
    """
    if base:
        cmd = ["git", "diff", "--name-only", f"{base}...{head}"]
    else:
        cmd = ["git", "diff", "--name-only", head]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return 0, 0
    files = [line for line in out.splitlines() if line.strip()]
    packages = {f.rsplit("/", 1)[0] if "/" in f else "." for f in files}
    return len(files), len(packages)


def main() -> int:
    parser = argparse.ArgumentParser(description="Work-proportional review sizing.")
    parser.add_argument("--files", type=int, help="changed-file count")
    parser.add_argument("--packages", type=int, help="package (directory) count")
    parser.add_argument("--base", help="git base ref (computes scope from range)")
    parser.add_argument("--head", default="HEAD", help="git head ref (default: HEAD)")
    parser.add_argument(
        "--findings",
        help="aggregated review findings NC/NH/NM; emits the rightsizing capture banner",
    )
    args = parser.parse_args()

    if args.files is not None:
        file_count = args.files
        package_count = args.packages if args.packages is not None else 1
    else:
        file_count, package_count = _git_scope(args.base, args.head)

    tier = compute_tier(file_count, package_count)
    comp = composition_for_tier(tier)

    # With --findings, emit the rightsizing banner the routing-decision-recorder
    # parses (ADR: review-tier-roi). Without it, JSON-only — existing callers
    # that json.loads(stdout) are unaffected. Malformed findings => warn, skip.
    if args.findings:
        fm = _FINDINGS_RE.match(args.findings.strip())
        if fm:
            print(
                f"rightsizing: tier={tier} files={file_count} packages={package_count} "
                f"agents_dispatched={comp['agent_estimate']} "
                f"findings={fm.group(1)}C/{fm.group(2)}H/{fm.group(3)}M"
            )
        else:
            print(f"warning: --findings must be NC/NH/NM, got {args.findings!r}", file=sys.stderr)

    result = {
        "tier": tier,
        "FILE_SCOPE_TIER": tier,
        "file_count": file_count,
        "package_count": package_count,
        "waves": comp["waves"],
        "agent_estimate": comp["agent_estimate"],
        "recommended": comp["recommended"],
        "wave3_on_critical": comp["wave3_on_critical"],
    }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
