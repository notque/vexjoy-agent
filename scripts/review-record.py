#!/usr/bin/env python3
"""Write or check the local review record the review-before-push gate reads.

/pr-review calls ``mark`` at the end of a review that left no unresolved
Critical or Important findings. The record covers one commit SHA of one repo;
a fix commit needs its own review and its own record.

``mark`` needs ``--findings-file``: the findings file /pr-review wrote for this
review. It must exist, be non-empty, and be modified after the commit's
committer time; its sha256 goes into the record. This stops accidental
self-marking. It does not stop a determined agent that writes a fake file.

Usage:
    python3 ~/.claude/scripts/review-record.py mark --sha SHA --findings-file /tmp/pr-review-SHA12.md \
        --summary "3 agents, 0 critical, 0 important" --critical 0 --important 0 [--repo-dir DIR]
    python3 ~/.claude/scripts/review-record.py check [--sha REV] [--repo-dir DIR]

Exit codes: 0 ok, 1 refused or no record, 2 usage or git error.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

for _lib in (
    Path.home() / ".gemini" / "hooks" / "lib",
    Path.home() / ".claude" / "hooks" / "lib",
    Path(__file__).resolve().parent.parent / "hooks" / "lib",
):
    if _lib.is_dir() and str(_lib) not in sys.path:
        sys.path.insert(0, str(_lib))

import review_record

# Verdicts that mean findings are still open: the current NEEDS_CHANGES and
# BLOCK, plus the older REQUEST-CHANGES / REQUEST_CHANGES spellings.
_NON_PASS_VERDICT = r"(?:BLOCK|NEEDS_CHANGES|REQUEST[-_]CHANGES)"


def _active_runtime_prefix() -> str:
    """Return ~/.gemini or ~/.claude depending on active environment."""
    runtime = os.environ.get("VEXJOY_HOOK_RUNTIME")
    if (
        runtime == "antigravity"
        or bool(os.environ.get("ANTIGRAVITY_AGENT"))
        or bool(os.environ.get("ANTIGRAVITY_APP_DATA_DIR"))
        or bool(os.environ.get("ANTIGRAVITY_CLI"))
    ):
        return "~/.gemini"
    return "~/.claude"


def _validate_findings_content(content: str, review_type: str | None = None) -> list[str]:
    """Validate review output structure. Returns list of errors (empty if valid)."""
    if not content.strip():
        return ["findings content is empty"]

    # Markdown headings, or the unindented label lines of the review skill's
    # Phase 4 template ("Review Summary:", "BLOCKING:", "Verdict: PASS").
    if not re.search(
        r"^#{1,4}\s+(?:Verdict|Critical|Important|Findings|Scope|Summary|Strengths|Review|Analysis|Severity)\b",
        content,
        re.MULTILINE | re.IGNORECASE,
    ) and not re.search(
        r"^\**(?:Verdict|Review Summary|Blocking|Should Fix|Suggestions)\**:",
        content,
        re.MULTILINE | re.IGNORECASE,
    ):
        return ["missing review structure: expected headings like ## Verdict, ## Findings, ## Scope, or ## Critical"]

    for line in content.splitlines():
        stripped = line.strip()
        if re.search(rf"\b{_NON_PASS_VERDICT}\b", stripped, re.IGNORECASE):
            if not re.search(rf"\b0\s+{_NON_PASS_VERDICT}\b", stripped, re.IGNORECASE) and not re.search(
                rf"\b(?:no|zero)\s+{_NON_PASS_VERDICT}\b", stripped, re.IGNORECASE
            ):
                return [f"findings file contains blocking verdict: {stripped}"]

    if review_type:
        return _schema_errors(content, review_type)
    return []


def _schema_errors(content: str, review_type: str) -> list[str]:
    """Run validate-review-output.py's parser and schema check for one type.

    Any failure to run the validator is an error, never a pass: --type asks
    for schema validation, so a missing jsonschema or a validator crash refuses
    the record with the reason instead of silently skipping the check.
    """
    vro_path = Path(__file__).resolve().parent / "validate-review-output.py"
    if not vro_path.is_file():
        return [f"cannot validate against the {review_type} schema: {vro_path} is missing"]
    try:
        spec = importlib.util.spec_from_file_location("validate_review_output", vro_path)
        if spec is None or spec.loader is None:
            return [f"cannot validate against the {review_type} schema: cannot load {vro_path}"]
        vro = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(vro)
    except SystemExit as exc:
        # The validator exits 3 at import when jsonschema is not installed.
        return [
            f"cannot validate against the {review_type} schema: the validator exited {exc.code} on load "
            "(is jsonschema installed? pip install -r requirements.txt)"
        ]
    except Exception as exc:
        return [f"cannot validate against the {review_type} schema: {type(exc).__name__}: {exc}"]
    try:
        data = vro.parse_markdown(content, review_type)
        if not data:
            return [f"failed validation against the {review_type} schema: no review structure found"]
        errors = vro.validate_structure(data, review_type)
    except Exception as exc:
        return [f"{review_type} schema validation crashed: {type(exc).__name__}: {exc}"]
    return [f"failed validation against the {review_type} schema: {err}" for err in errors]


def _remotes(repo_dir: str) -> dict[str, str]:
    proc = review_record.git(["remote", "-v"], repo_dir)
    out: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2] == "(push)":
            out[parts[0]] = parts[1]
    return out


def _resolve(args: argparse.Namespace) -> tuple[str, str]:
    identity = review_record.repo_identity(args.repo_dir)
    if not identity:
        print(f"review-record: {args.repo_dir} is not inside a git repository", file=sys.stderr)
        sys.exit(2)
    sha = review_record.resolve_commit(args.sha, args.repo_dir)
    if not sha:
        print(f"review-record: cannot resolve {args.sha!r} to a commit", file=sys.stderr)
        sys.exit(2)
    return identity, sha


def cmd_mark(args: argparse.Namespace) -> int:
    if args.critical or args.important:
        print(
            f"review-record: refused: {args.critical} critical and {args.important} important findings are open; "
            "fix them, commit, and review the new commit",
            file=sys.stderr,
        )
        return 1
    if not args.summary.strip():
        print("review-record: refused: --summary is empty", file=sys.stderr)
        return 1
    identity, sha = _resolve(args)
    findings = Path(args.findings_file).expanduser()
    try:
        body = findings.read_bytes()
        mtime = findings.stat().st_mtime
    except OSError:
        print(f"review-record: refused: findings file {findings} does not exist", file=sys.stderr)
        return 1
    if not body.strip():
        print(f"review-record: refused: findings file {findings} is empty", file=sys.stderr)
        return 1
    committed = review_record.git(["show", "-s", "--format=%ct", sha], args.repo_dir).stdout.strip()
    if not committed.isdigit() or mtime <= int(committed):
        print(
            f"review-record: refused: findings file {findings} is older than commit {sha[:12]}; "
            "it must come from a review of this commit",
            file=sys.stderr,
        )
        return 1
    head = review_record.resolve_commit("HEAD", args.repo_dir)
    if sha == head:
        dirty = review_record.git(["status", "--porcelain", "--untracked-files=no"], args.repo_dir)
        if dirty.stdout.strip():
            print(
                "review-record: refused: tracked files differ from HEAD, so the review did not cover the commit; "
                "commit the changes and review the new commit",
                file=sys.stderr,
            )
            return 1
    if not getattr(args, "skip_validation", False):
        val_errors = _validate_findings_content(
            body.decode("utf-8", errors="replace"),
            review_type=getattr(args, "type", None),
        )
        if val_errors:
            print(
                f"review-record: refused: findings file {findings} failed review validation: {'; '.join(val_errors)}",
                file=sys.stderr,
            )
            return 1
    path = review_record.write_record(
        identity,
        sha,
        args.summary.strip()[:500],
        findings_sha256=hashlib.sha256(body).hexdigest(),
        findings_path=str(findings.resolve()),
        remotes=_remotes(args.repo_dir),
    )
    print(json.dumps({"recorded": sha, "repo": identity, "path": str(path)}))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    identity, sha = _resolve(args)
    record = review_record.read_record(identity, sha)
    if record is None:
        print(json.dumps({"reviewed": False, "sha": sha, "repo": identity}))
        return 1
    print(json.dumps({"reviewed": True, **record}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("mark", "check"):
        p = sub.add_parser(name)
        p.add_argument("--repo-dir", default=".", help="any directory inside the repo (default: cwd)")
        p.add_argument("--sha", default="HEAD", help="reviewed commit (default: HEAD)")
        if name == "mark":
            p.add_argument("--summary", required=True, help="one line: what was reviewed and the result")
            p.add_argument("--findings-file", required=True, help="findings file /pr-review wrote for this commit")
            p.add_argument("--critical", type=int, required=True, help="unresolved Critical findings")
            p.add_argument("--important", type=int, required=True, help="unresolved Important findings")
            p.add_argument(
                "--skip-validation",
                action="store_true",
                help="skip structural validation of the findings file",
            )
            p.add_argument(
                "--type",
                choices=("base", "systematic", "parallel", "sapcc-review", "sapcc-audit"),
                help="review schema type to validate against",
            )
    args = parser.parse_args(argv)
    return cmd_mark(args) if args.cmd == "mark" else cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
