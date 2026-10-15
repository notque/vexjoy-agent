"""Scope for the mutation check: registered hooks and validators that have a test file."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Tests whose file name does not follow `test_<hook_stem>*.py`. Each entry was read to confirm the test loads the hook.
TEST_OVERRIDES: dict[str, list[str]] = {
    "adr-lifecycle-on-merge.py": ["test_adr_lifecycle_hook.py"],
    "hook-version-parity-check.py": ["test_hook_version_parity.py"],
    "pending-advisory-injector-userprompt.py": ["test_pending_advisory.py"],
    "session-manifest-cache.py": ["test_manifest_cache.py"],
    "routing-outcome-finalizer.py": ["test_acceptance_detector.py", "test_weak_positive.py"],
    "routing-decision-recorder.py": [
        "test_routing_decision_recorder.py",
        "test_routing_pipeline_token.py",
        "test_telemetry_envelope.py",
    ],
    "routing-outcome-recorder.py": ["test_routing_decision_recorder.py"],
    "routing-outcome-stop-fallback.py": ["test_routing_decision_recorder.py"],
    "fish-shell-detector.py": [],
}

DENY_SOURCE = re.compile(
    r"deny_tool_use|permissionDecision|\"decision\"\s*:\s*\"block\"|sys\.exit\(2\)|\bexit\(2\)|\"deny\"|'deny'"
)


@dataclass
class Target:
    """One file to mutate and the tests that cover it."""

    name: str
    kind: str  # hook | validator
    source: str  # repo-relative path
    tests: list[str]  # repo-relative paths
    events: list[str] = field(default_factory=list)
    deny: bool = False  # registered PreToolUse and the source has a deny/block path


def registered_hooks(repo: Path) -> dict[str, list[str]]:
    """Return {hook file name: [events]} from `.claude/settings.json`."""
    settings = json.loads((repo / ".claude" / "settings.json").read_text(encoding="utf-8"))
    out: dict[str, list[str]] = {}
    for event, groups in settings.get("hooks", {}).items():
        for group in groups:
            for hook in group.get("hooks", []):
                match = re.search(r"hooks/([\w\-]+\.py)", hook.get("command", ""))
                if match:
                    events = out.setdefault(match.group(1), [])
                    if event not in events:
                        events.append(event)
    return out


def _hook_tests(repo: Path, hook: str) -> list[str]:
    tests_dir = repo / "hooks" / "tests"
    if hook in TEST_OVERRIDES:
        names = TEST_OVERRIDES[hook]
    else:
        stem = hook[:-3].replace("-", "_")
        names = sorted(p.name for p in tests_dir.glob(f"test_{stem}*.py"))
    return [f"hooks/tests/{n}" for n in names if (tests_dir / n).exists()]


def discover(repo: Path) -> tuple[list[Target], list[dict[str, str]]]:
    """Return (targets, excluded) where excluded lists registered hooks with no test and why."""
    targets: list[Target] = []
    excluded: list[dict[str, str]] = []
    for hook, events in sorted(registered_hooks(repo).items()):
        path = repo / "hooks" / hook
        if not path.exists():
            excluded.append({"name": hook, "reason": "registered file missing"})
            continue
        tests = _hook_tests(repo, hook)
        if not tests:
            excluded.append({"name": hook, "reason": "no test file"})
            continue
        deny = "PreToolUse" in events and bool(DENY_SOURCE.search(path.read_text(encoding="utf-8")))
        targets.append(Target(hook, "hook", f"hooks/{hook}", tests, events, deny))
    for path in sorted((repo / "scripts").glob("validate-*.py")):
        test = repo / "scripts" / "tests" / f"test_{path.stem.replace('-', '_')}.py"
        if test.exists():
            targets.append(Target(path.name, "validator", f"scripts/{path.name}", [f"scripts/tests/{test.name}"]))
        else:
            excluded.append({"name": path.name, "reason": "no test file"})
    return targets, excluded


def scope_json(targets: list[Target], excluded: list[dict[str, str]]) -> dict:
    """Return the scope as a JSON-able dict with counts."""
    return {
        "counts": {
            "targets": len(targets),
            "hooks": sum(t.kind == "hook" for t in targets),
            "validators": sum(t.kind == "validator" for t in targets),
            "deny_hooks": sum(t.deny for t in targets),
            "excluded": len(excluded),
        },
        "targets": [asdict(t) for t in targets],
        "excluded": excluded,
    }
