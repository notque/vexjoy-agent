"""Local review records: proof that /pr-review passed on one commit of one repo.

Shared by ``hooks/pretool-review-before-push-gate.py`` (reads) and
``scripts/review-record.py`` (writes). A record lives at
``~/.claude/state/review-records/<repo-key>/<sha>.json``, where the repo key
hashes the realpath of the repo's git common dir, so every worktree of one
clone shares records and a second clone or another repo does not.

A record covers exactly one commit SHA. A fix commit has a new SHA and needs a
new record. The reader re-checks the repo and SHA stored inside the file, so a
record copied between directories does not count.

`mark` must name the findings file /pr-review wrote after the commit, and the
record stores its sha256. That stops an agent from passing its own push by
accident; it does not stop a determined agent that fakes a findings file.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

RECORD_VERSION = 2
GIT_TIMEOUT = 5


def records_root() -> Path:
    """Directory holding review records for the active runtime."""
    env = os.environ.get("VEXJOY_STATE_DIR")
    if env:
        return Path(env) / "review-records"
    runtime = os.environ.get("VEXJOY_HOOK_RUNTIME")
    if (
        runtime == "antigravity"
        or bool(os.environ.get("ANTIGRAVITY_AGENT"))
        or bool(os.environ.get("ANTIGRAVITY_APP_DATA_DIR"))
        or bool(os.environ.get("ANTIGRAVITY_CLI"))
    ):
        return Path.home() / ".gemini" / "state" / "review-records"
    if runtime == "codex" or bool(os.environ.get("CODEX_HOME")):
        return Path.home() / ".codex" / "state" / "review-records"
    return Path.home() / ".claude" / "state" / "review-records"


def candidate_records_roots() -> list[Path]:
    """Every candidate review records root across supported runtimes, active first."""
    active = records_root()
    roots = [active]
    for candidate in (
        Path.home() / ".gemini" / "state" / "review-records",
        Path.home() / ".claude" / "state" / "review-records",
        Path.home() / ".codex" / "state" / "review-records",
    ):
        if candidate not in roots:
            roots.append(candidate)
    return roots


def git(args: list[str], cwd: str | Path | None, git_opts: list[str] | None = None) -> subprocess.CompletedProcess:
    """Run git with *git_opts* (e.g. ``--git-dir=x``) before *args*; never raises on non-zero."""
    return subprocess.run(
        ["git", *(git_opts or []), *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT,
        check=False,
    )


def repo_identity(cwd: str | Path | None, git_opts: list[str] | None = None) -> str | None:
    """Realpath of the git common dir for *cwd*, or None outside a repo."""
    proc = git(["rev-parse", "--git-common-dir"], cwd, git_opts)
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    common = Path(proc.stdout.strip())
    if not common.is_absolute():
        base = Path(cwd) if cwd else Path.cwd()
        common = base / common
    return os.path.realpath(common)


def resolve_commit(rev: str, cwd: str | Path | None, git_opts: list[str] | None = None) -> str | None:
    """Full commit SHA for *rev*, peeling tags, or None."""
    proc = git(["rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}"], cwd, git_opts)
    sha = proc.stdout.strip()
    if proc.returncode != 0 or len(sha) < 40:
        return None
    return sha


def record_path(identity: str, sha: str) -> Path:
    import hashlib

    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return records_root() / key / f"{sha}.json"


def read_record(identity: str, sha: str) -> dict | None:
    """The record for (*identity*, *sha*) when it exists and names that repo and SHA."""
    import hashlib

    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    for root in candidate_records_roots():
        record_file = root / key / f"{sha}.json"
        try:
            data = json.loads(record_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        if data.get("version") != RECORD_VERSION or data.get("repo") != identity or data.get("sha") != sha:
            continue
        digest = data.get("findings_sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            continue
        if data.get("critical", 1) != 0 or data.get("important", 1) != 0:
            continue
        return data
    return None


def write_record(
    identity: str,
    sha: str,
    summary: str,
    *,
    findings_sha256: str,
    findings_path: str,
    remotes: dict[str, str] | None = None,
) -> Path:
    """Write the record atomically (temp file then rename) and return its path."""
    import tempfile
    from datetime import datetime, timezone

    path = record_path(identity, sha)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": RECORD_VERSION,
        "repo": identity,
        "sha": sha,
        "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": summary,
        "critical": 0,
        "important": 0,
        "findings_sha256": findings_sha256,
        "findings_path": findings_path,
        "remotes": remotes or {},
    }
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return path
