"""Contract tests for CI dependency version pins.

Every ``pip install`` in CI workflows must pin packages to the version in
``requirements.lock`` so that a new upstream release cannot silently change
or break gates on an unrelated PR.
"""

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

# debt: not in requirements.lock; shrink this set, never grow it
KNOWN_UNPINNED = {"pytest", "pytest-xdist", "numpy"}

_INSTALL_RE = re.compile(r"^\s*-?\s*(?:run:\s*)?pip install (.+)$", re.MULTILINE)


def _normalize(name: str) -> str:
    """Normalize a package name per PEP 503."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _load_lockfile() -> dict[str, str]:
    """Return ``{normalized_name: version}`` from ``requirements.lock``."""
    lock: dict[str, str] = {}
    for line in (_REPO_ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "==" in line:
            name, version = line.split("==", 1)
            lock[_normalize(name)] = version
    return lock


def _collect_installs() -> list[tuple[str, str, int, list[str], bool]]:
    """Collect pip install commands from all CI workflow files.

    Returns a list of ``(file, file:line, line_number, tokens, has_lockfile)``
    tuples. Tokens are the package specifiers after ``-r <file>`` pairs are
    stripped.
    """
    results: list[tuple[str, str, int, list[str], bool]] = []
    workflows = sorted((_REPO_ROOT / ".github" / "workflows").glob("*.yml"))
    for wf in workflows:
        text = wf.read_text(encoding="utf-8")
        for match in _INSTALL_RE.finditer(text):
            line_number = text[: match.start()].count("\n") + 1
            raw_tokens = match.group(1).split()
            tokens: list[str] = []
            has_lockfile = False
            skip_next = False
            for tok in raw_tokens:
                if skip_next:
                    if tok == "requirements.lock":
                        has_lockfile = True
                    skip_next = False
                    continue
                if tok == "-r":
                    skip_next = True
                    continue
                tokens.append(tok)
            label = f"{wf.name}:{line_number}"
            results.append((wf.name, label, line_number, tokens, has_lockfile))
    return results


def test_parser_finds_installs() -> None:
    """Guard against a broken regex that collects nothing and passes vacuously."""
    installs = _collect_installs()
    assert installs, "the install regex found no pip install commands in any workflow"


def test_ci_installs_are_pinned() -> None:
    """Every pip-installed package in CI must be pinned or accounted for."""
    lock = _load_lockfile()
    installs = _collect_installs()
    failures: list[str] = []
    for _file, label, _line, tokens, has_lockfile in installs:
        for tok in tokens:
            if "==" in tok:
                continue
            normalized = _normalize(tok)
            if normalized in KNOWN_UNPINNED:
                continue
            if has_lockfile and normalized in lock:
                continue
            fix = f"pin it to {tok}=={lock[normalized]}" if normalized in lock else "add it to requirements.lock"
            failures.append(f"{label}: bare '{tok}' ({fix})")
    assert not failures, "unpinned CI installs let a new upstream release break unrelated PRs:\n  " + "\n  ".join(
        failures
    )


def test_ci_pins_match_lockfile() -> None:
    """Explicit version pins in CI must match requirements.lock."""
    lock = _load_lockfile()
    installs = _collect_installs()
    mismatches: list[str] = []
    for _file, label, _line, tokens, _has_lockfile in installs:
        for tok in tokens:
            if "==" not in tok:
                continue
            name, version = tok.split("==", 1)
            normalized = _normalize(name)
            if normalized in lock and version != lock[normalized]:
                mismatches.append(f"{label}: {tok} but lock has {normalized}=={lock[normalized]}")
    assert not mismatches, "CI version pins diverged from requirements.lock:\n  " + "\n  ".join(mismatches)


def test_known_unpinned_is_not_stale() -> None:
    """Every entry in KNOWN_UNPINNED must still appear bare in some command.

    When a pin lands, remove the name from KNOWN_UNPINNED so the set
    only shrinks.
    """
    installs = _collect_installs()
    all_bare: set[str] = set()
    for _file, _label, _line, tokens, _has_lockfile in installs:
        for tok in tokens:
            if "==" not in tok:
                all_bare.add(_normalize(tok))
    stale = KNOWN_UNPINNED - all_bare
    assert not stale, f"KNOWN_UNPINNED has entries no longer used bare in CI: {stale}"
