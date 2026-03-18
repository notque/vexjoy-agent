#!/usr/bin/env python3
"""
Scan markdown docs for AI writing patterns using banned-patterns.json.

Usage:
    python3 scripts/scan-ai-patterns.py                    # scan all docs
    python3 scripts/scan-ai-patterns.py docs/VOICE-SYSTEM.md  # scan specific file
    python3 scripts/scan-ai-patterns.py --errors-only      # only show errors
    python3 scripts/scan-ai-patterns.py --json             # machine-readable output

Exit codes:
    0 = all files clean (zero errors)
    1 = errors found
"""

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
PATTERNS_FILE = SCRIPT_DIR / "data" / "banned-patterns.json"

# Default doc globs to scan
DEFAULT_GLOBS = [
    "README.md",
    "CHANGELOG.md",
    "docs/*.md",
    "hooks/README.md",
    "hooks/QUICKSTART.md",
]

SEVERITY_WEIGHTS = {"error": 3, "warning": 2, "info": 1}


def load_patterns() -> dict:
    with open(PATTERNS_FILE) as f:
        return json.load(f)


def scan_file(filepath: Path, db: dict, min_severity: str = "info") -> list[dict]:
    """Scan a file and return list of hits."""
    try:
        content = filepath.read_text()
    except Exception as e:
        return [{"error": str(e)}]

    content_lower = content.lower()
    min_weight = SEVERITY_WEIGHTS.get(min_severity, 0)
    hits = []

    for cat_name, cat in db["categories"].items():
        sev = cat["severity"]
        weight = SEVERITY_WEIGHTS.get(sev, 1)
        if weight < min_weight:
            continue

        for pat in cat["patterns"]:
            try:
                if any(c in pat for c in r".+*\()[]{}|?"):
                    for m in re.finditer(pat, content_lower):
                        line_num = content_lower[: m.start()].count("\n") + 1
                        ls = content_lower.rfind("\n", 0, m.start()) + 1
                        le = content_lower.find("\n", m.end())
                        if le == -1:
                            le = len(content_lower)
                        hits.append(
                            {
                                "file": str(filepath),
                                "line": line_num,
                                "severity": sev,
                                "category": cat_name,
                                "pattern": pat,
                                "context": content[ls:le].strip()[:120],
                            }
                        )
                else:
                    idx = 0
                    while True:
                        idx = content_lower.find(pat, idx)
                        if idx == -1:
                            break
                        line_num = content_lower[:idx].count("\n") + 1
                        ls = content_lower.rfind("\n", 0, idx) + 1
                        le = content_lower.find("\n", idx)
                        if le == -1:
                            le = len(content_lower)
                        hits.append(
                            {
                                "file": str(filepath),
                                "line": line_num,
                                "severity": sev,
                                "category": cat_name,
                                "pattern": pat,
                                "context": content[ls:le].strip()[:120],
                            }
                        )
                        idx += 1
            except re.error:
                pass

    return hits


def main():
    parser = argparse.ArgumentParser(description="Scan docs for AI writing patterns")
    parser.add_argument("files", nargs="*", help="Specific files to scan (default: all docs)")
    parser.add_argument("--errors-only", action="store_true", help="Only show error-severity hits")
    parser.add_argument("--json", action="store_true", dest="json_output", help="JSON output")
    args = parser.parse_args()

    db = load_patterns()
    min_severity = "error" if args.errors_only else "info"

    # Determine files to scan
    if args.files:
        files = [Path(f) for f in args.files]
    else:
        files = []
        for glob_pat in DEFAULT_GLOBS:
            files.extend(REPO_ROOT.glob(glob_pat))
        files = sorted(set(files))

    all_hits = []
    for f in files:
        hits = scan_file(f, db, min_severity)
        all_hits.extend(hits)

    if args.json_output:
        json.dump(all_hits, sys.stdout, indent=2)
        print()
    else:
        if not all_hits:
            print(f"CLEAN. {len(files)} files scanned, zero hits.")
        else:
            by_file: dict[str, list] = {}
            for h in all_hits:
                by_file.setdefault(h["file"], []).append(h)

            for filepath, file_hits in sorted(by_file.items()):
                error_count = sum(1 for h in file_hits if h["severity"] == "error")
                print(f"\n{filepath}: {len(file_hits)} hits ({error_count} errors)")
                for h in sorted(file_hits, key=lambda x: x["line"]):
                    print(f"  L{h['line']} [{h['severity']}] {h['category']}: \"{h['pattern']}\"")
                    print(f"    {h['context']}")

            total_errors = sum(1 for h in all_hits if h["severity"] == "error")
            print(f"\n{len(all_hits)} total hits, {total_errors} errors across {len(by_file)} files")

    total_errors = sum(1 for h in all_hits if h.get("severity") == "error")
    sys.exit(1 if total_errors > 0 else 0)


if __name__ == "__main__":
    main()
