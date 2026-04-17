#!/usr/bin/env python3
"""
Deterministic feature lifecycle state management CLI.

Manages .feature/ directory structure for multi-phase feature development.
All output is structured JSON (default) or human-readable (--human flag).

Usage:
    python3 scripts/feature-state.py init FEATURE_NAME          # Create .feature/ structure + worktree
    python3 scripts/feature-state.py status                     # Show active features and their phases
    python3 scripts/feature-state.py status FEATURE_NAME        # Show specific feature status

    python3 scripts/feature-state.py checkpoint FEATURE PHASE   # Save phase checkpoint artifact
    python3 scripts/feature-state.py advance FEATURE PHASE      # Mark phase complete, advance to next
    python3 scripts/feature-state.py gate FEATURE GATE_ID       # Check gate status (human|auto|confidence)

    python3 scripts/feature-state.py retro-record FEATURE KEY VALUE  # Write L3 retro record
    python3 scripts/feature-state.py retro-record --adhoc TOPIC KEY VALUE  # Write directly to retro/L2/
    python3 scripts/feature-state.py retro-promote FEATURE KEY       # Promote L3→L2 if confidence threshold met
    python3 scripts/feature-state.py context-read FEATURE LEVEL      # Read context at L0/L1/L2 level

    python3 scripts/feature-state.py worktree FEATURE create   # Create git worktree for feature
    python3 scripts/feature-state.py worktree FEATURE path     # Print worktree path
    python3 scripts/feature-state.py worktree FEATURE cleanup  # Remove worktree after merge

    python3 scripts/feature-state.py retro-audit                # Audit retro/L2 for stale/orphan files

    python3 scripts/feature-state.py complete FEATURE          # Archive feature, cleanup worktree
    python3 scripts/feature-state.py abandon FEATURE --reason "reason"  # Abandon feature

Exit codes:
    0 = success
    1 = error
    2 = gate requires human input
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

# Constants
PHASES = ["design", "plan", "implement", "validate", "release"]
FEATURE_DIR = ".feature"
CONFIDENCE_THRESHOLD = 0.7  # Auto-flip gate when confidence exceeds this
DEFAULT_GATES = {
    "design.intent-discussion": "human",
    "design.approach-selection": "human",
    "design.design-approval": "human",
    "plan.plan-approval": "human",
    "plan.wave-ordering": "auto",
    "implement.architectural-deviation": "human",
    "implement.domain-agent-selection": "auto",
    "validate.quality-gates": "auto",
    "validate.test-coverage": "auto",
    "release.merge-strategy": "human",
    "retro.l3-records": "auto",
    "retro.l2-context": "auto",
    "retro.l1-summaries": "auto",
    "retro.phase-checkpoint": "auto",
}

TAG_SYNONYMS: dict[str, list[str]] = {
    "circuit-breaker": ["resilience", "fault-tolerance", "retry"],
    "middleware": ["interceptor", "wrapper"],
    "concurrency": ["parallel", "async", "threading"],
    "health-endpoint": ["healthcheck", "liveness", "readiness"],
    "state-machine": ["fsm", "state-management"],
    "testing": ["test", "unit-test", "integration-test"],
}


@dataclass
class FeatureState:
    """Current state of a feature."""

    name: str
    current_phase: str = "design"
    phases_completed: list[str] = field(default_factory=list)
    created: str = ""
    updated: str = ""
    worktree_path: str = ""
    branch: str = ""
    gates: dict[str, str] = field(default_factory=dict)
    retro_records: dict[str, Any] = field(default_factory=dict)


def get_feature_dir(base: Path, feature: str) -> Path:
    """Get .feature/ directory, respecting worktree if it exists."""
    return base / FEATURE_DIR


def find_project_root() -> Path:
    """Find project root by looking for .git directory."""
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists() or (current / ".git").is_file():
            return current
        current = current.parent
    return Path.cwd()


def load_state(feature_dir: Path, feature: str) -> FeatureState | None:
    """Load feature state from state file."""
    state_file = feature_dir / "state" / f"{feature}.json"
    if not state_file.exists():
        return None
    with open(state_file) as f:
        data = json.load(f)
    return FeatureState(**data)


def save_state(feature_dir: Path, state: FeatureState) -> None:
    """Save feature state to state file."""
    state_dir = feature_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / f"{state.name}.json"
    state.updated = datetime.now().isoformat()
    with open(state_file, "w") as f:
        json.dump(asdict(state), f, indent=2)


def slugify(name: str) -> str:
    """Convert feature name to filesystem-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower().strip())
    return slug.strip("-")


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize a new feature with .feature/ structure."""
    root = find_project_root()
    feature_name = slugify(args.feature_name)
    feature_dir = root / FEATURE_DIR

    if (feature_dir / "state" / f"{feature_name}.json").exists():
        output_error(f"Feature '{feature_name}' already exists")
        return 1

    # Create directory structure
    dirs = [
        feature_dir / "state" / "design",
        feature_dir / "state" / "plan",
        feature_dir / "state" / "implement",
        feature_dir / "state" / "validate",
        feature_dir / "state" / "release",
        feature_dir / "context",
        feature_dir / "context" / "design",
        feature_dir / "context" / "plan",
        feature_dir / "context" / "implement",
        feature_dir / "context" / "validate",
        feature_dir / "meta",
        feature_dir / "meta" / "design",
        feature_dir / "meta" / "plan",
        feature_dir / "meta" / "implement",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    # Create L0 system file
    l0_file = feature_dir / "FEATURE.md"
    if not l0_file.exists():
        l0_file.write_text(
            f"# Feature Lifecycle Context\n\n"
            f"Phase pipeline: design → plan → implement → validate → release\n"
            f"State artifacts: .feature/state/<phase>/\n"
            f"Knowledge: .feature/context/ (what we know) + .feature/meta/ (how we work)\n\n"
            f"## Active Features\n\n"
            f"- {feature_name}: design phase\n"
        )

    # Create L1 context summaries
    for phase in PHASES:
        l1_file = feature_dir / "context" / f"{phase.upper()}.md"
        if not l1_file.exists():
            l1_file.write_text(
                f"# {phase.title()} Context\n\n"
                f"Summary of {phase} knowledge for this project.\n\n"
                f"## Conventions\n\n(populated by retro loop)\n\n"
                f"## Decisions\n\n(populated by retro loop)\n"
            )

    # Create initial state
    state = FeatureState(
        name=feature_name,
        current_phase="design",
        created=datetime.now().isoformat(),
        updated=datetime.now().isoformat(),
        branch=f"feature/{feature_name}",
        gates=dict(DEFAULT_GATES),
    )
    save_state(feature_dir, state)

    output_json(
        {
            "action": "init",
            "feature": feature_name,
            "phase": "design",
            "feature_dir": str(feature_dir),
            "branch": state.branch,
        },
        args,
    )
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show status of active features."""
    root = find_project_root()
    feature_dir = root / FEATURE_DIR
    state_dir = feature_dir / "state"

    if not state_dir.exists():
        output_json({"features": [], "message": "No .feature/ directory found"}, args)
        return 0

    features = []
    for state_file in sorted(state_dir.glob("*.json")):
        state = load_state(feature_dir, state_file.stem)
        if state:
            features.append(
                {
                    "name": state.name,
                    "phase": state.current_phase,
                    "completed": state.phases_completed,
                    "branch": state.branch,
                    "updated": state.updated,
                    "worktree": state.worktree_path,
                }
            )

    if args.feature_name:
        features = [f for f in features if f["name"] == slugify(args.feature_name)]

    output_json({"features": features}, args)
    return 0


def cmd_checkpoint(args: argparse.Namespace) -> int:
    """Save a phase checkpoint artifact."""
    root = find_project_root()
    feature_dir = root / FEATURE_DIR
    feature = slugify(args.feature)
    phase = args.phase.lower()

    if phase not in PHASES:
        output_error(f"Invalid phase: {phase}. Must be one of: {', '.join(PHASES)}")
        return 1

    state = load_state(feature_dir, feature)
    if not state:
        output_error(f"Feature '{feature}' not found")
        return 1

    # Read checkpoint content from stdin
    content = sys.stdin.read() if not sys.stdin.isatty() else ""

    today = date.today().isoformat()
    checkpoint_file = feature_dir / "state" / phase / f"{today}-{feature}.md"
    checkpoint_file.parent.mkdir(parents=True, exist_ok=True)

    if content:
        checkpoint_file.write_text(content)
    else:
        # Create empty checkpoint marker
        checkpoint_file.write_text(
            f"# {phase.title()} Checkpoint: {feature}\n\n**Date**: {today}\n**Status**: completed\n"
        )

    output_json(
        {
            "action": "checkpoint",
            "feature": feature,
            "phase": phase,
            "artifact": str(checkpoint_file),
        },
        args,
    )
    return 0


def cmd_advance(args: argparse.Namespace) -> int:
    """Mark current phase complete and advance to next."""
    root = find_project_root()
    feature_dir = root / FEATURE_DIR
    feature = slugify(args.feature)

    state = load_state(feature_dir, feature)
    if not state:
        output_error(f"Feature '{feature}' not found")
        return 1

    current_idx = PHASES.index(state.current_phase)
    if current_idx >= len(PHASES) - 1:
        output_error(f"Feature '{feature}' is already in final phase (release)")
        return 1

    # Check that checkpoint exists for current phase
    today = date.today().isoformat()
    checkpoint_dir = feature_dir / "state" / state.current_phase
    checkpoints = list(checkpoint_dir.glob(f"*-{feature}.md"))
    if not checkpoints:
        output_error(
            f"No checkpoint found for phase '{state.current_phase}'. "
            f"Run 'checkpoint {feature} {state.current_phase}' first."
        )
        return 1

    state.phases_completed.append(state.current_phase)
    state.current_phase = PHASES[current_idx + 1]
    save_state(feature_dir, state)

    output_json(
        {
            "action": "advance",
            "feature": feature,
            "from_phase": PHASES[current_idx],
            "to_phase": state.current_phase,
            "completed": state.phases_completed,
        },
        args,
    )
    return 0


def cmd_gate(args: argparse.Namespace) -> int:
    """Check gate status and determine if human input is needed."""
    root = find_project_root()
    feature_dir = root / FEATURE_DIR
    feature = slugify(args.feature)
    gate_id = args.gate_id

    state = load_state(feature_dir, feature)
    if not state:
        output_error(f"Feature '{feature}' not found")
        return 1

    mode = state.gates.get(gate_id, "human")

    # Check env override for retro gates (e.g., CLAUDE_RETRO_GATE_L2_CONTEXT=human)
    if gate_id.startswith("retro."):
        env_key = "CLAUDE_RETRO_GATE_" + gate_id.split(".")[-1].upper().replace("-", "_")
        env_val = os.environ.get(env_key)
        if env_val in ("human", "auto"):
            mode = env_val

    # Check if confidence-based auto-flip applies
    confidence = _get_gate_confidence(gate_id)
    auto_flipped = False
    if mode == "human" and confidence >= CONFIDENCE_THRESHOLD:
        mode = "auto"
        auto_flipped = True
        state.gates[gate_id] = "auto"
        save_state(feature_dir, state)

    result = {
        "gate_id": gate_id,
        "mode": mode,
        "confidence": confidence,
        "auto_flipped": auto_flipped,
        "requires_human": mode == "human",
    }

    output_json(result, args)
    return 2 if mode == "human" else 0


def _get_gate_confidence(gate_id: str) -> float:
    """Query learning database for gate-related confidence."""
    try:
        db_path = Path.home() / ".claude" / "learning" / "patterns.db"
        if not db_path.exists():
            return 0.0

        import sqlite3

        conn = sqlite3.connect(str(db_path), timeout=2)
        cursor = conn.cursor()

        # Look for patterns related to this gate's domain
        phase = gate_id.split(".")[0] if "." in gate_id else gate_id
        cursor.execute(
            "SELECT AVG(confidence) FROM patterns WHERE project_path LIKE ? AND confidence > 0",
            (f"%{phase}%",),
        )
        row = cursor.fetchone()
        conn.close()

        return row[0] if row and row[0] else 0.0
    except Exception:
        return 0.0


def cmd_retro_record(args: argparse.Namespace) -> int:
    """Write a retro record (L3) for a feature."""
    root = find_project_root()
    feature_dir = root / FEATURE_DIR
    feature = slugify(args.feature)

    state = load_state(feature_dir, feature)
    if not state:
        output_error(f"Feature '{feature}' not found")
        return 1

    key = args.key
    value = args.value
    confidence = getattr(args, "confidence", "low")

    # Reload fresh state to avoid overwriting concurrent changes (e.g., advance)
    fresh_state = load_state(feature_dir, feature)
    if fresh_state:
        state = fresh_state

    # Observation tracking + frequency-gated auto-promotion
    existing_record = state.retro_records.get(key)
    observations = 1
    auto_promoted = False
    if existing_record:
        observations = existing_record.get("observations", 1) + 1
        # Keep the highest confidence seen
        prev_conf = existing_record.get("confidence", "low")
        conf_rank = {"low": 0, "medium": 1, "high": 2}
        if conf_rank.get(prev_conf, 0) > conf_rank.get(confidence, 0):
            confidence = prev_conf
        # Frequency-gated auto-promotion (LOW→MEDIUM at 3, MEDIUM→HIGH at 6)
        if confidence == "low" and observations >= 3:
            confidence = "medium"
            auto_promoted = True
        elif confidence == "medium" and observations >= 6:
            confidence = "high"
            auto_promoted = True

    state.retro_records[key] = {
        "value": value,
        "confidence": confidence,
        "observations": observations,
        "recorded": datetime.now().isoformat(),
        "phase": state.current_phase,
    }
    save_state(feature_dir, state)

    # Write L3 record file
    meta_dir = feature_dir / "meta" / state.current_phase
    meta_dir.mkdir(parents=True, exist_ok=True)
    record_file = meta_dir / f"{key}.md"

    # Append or create (include observation count)
    count_tag = f" ({observations}x)" if observations > 1 else ""
    entry = f"\n## {key} [{confidence.upper()}]{count_tag}\n\n{value}\n\n*Recorded: {datetime.now().isoformat()}*\n"
    with open(record_file, "a") as f:
        f.write(entry)

    output_json(
        {
            "action": "retro-record",
            "feature": feature,
            "key": key,
            "confidence": confidence,
            "observations": observations,
            "auto_promoted": auto_promoted,
            "file": str(record_file),
        },
        args,
    )
    return 0


def cmd_retro_record_adhoc(args: argparse.Namespace) -> int:
    """Write a retro record directly to retro/L2/ without a feature context.

    Used by /do's learning phase for ad-hoc knowledge capture from any task.
    Writes directly to retro/L2/<topic>.md with observation clustering and
    L1 regeneration — same as feature complete archival but without requiring
    .feature/ state.
    """
    root = find_project_root()
    retro_dir = root / "retro"
    l2_dir = retro_dir / "L2"
    l2_dir.mkdir(parents=True, exist_ok=True)

    topic = slugify(args.topic)
    key = args.key
    value = args.value
    confidence = args.confidence

    heading = key.replace("-", " ").title()
    dest_file = l2_dir / f"{topic}.md"

    clustered = False
    if dest_file.exists():
        existing = dest_file.read_text()
        updated, clustered = _increment_observation(existing, heading)
        if clustered:
            dest_file.write_text(updated)
        elif f"### {heading}" not in existing:
            existing += f"\n### {heading}\n{value}\n"
            dest_file.write_text(existing)
    else:
        # Create new L2 topic file with proper metadata
        lines = [
            f"# Retro: {topic.replace('-', ' ').title()}",
            "**Source**: adhoc",
            f"**Confidence**: {confidence.upper()}",
            f"**Tags**: {topic.replace('-', ', ')}",
            "**Languages**: ",
            "",
            f"### {heading}",
            value,
            "",
        ]
        dest_file.write_text("\n".join(lines))

    # Regenerate L1 summary
    _regenerate_l1(retro_dir)

    # Bridge: also write to learning.db if available
    try:
        _script_dir = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(_script_dir / "hooks" / "lib"))
        _home_lib = Path.home() / ".claude" / "hooks" / "lib"
        if _home_lib.is_dir():
            sys.path.insert(0, str(_home_lib))
        from learning_db_v2 import record_learning

        conf_map = {"HIGH": 0.85, "MEDIUM": 0.65, "LOW": 0.45}
        record_learning(
            topic=topic,
            key=key.lower().replace(" ", "-"),
            value=value,
            category="design",
            confidence=conf_map.get(confidence.upper(), 0.65),
            tags=topic.replace("-", ",").split(","),
            source="manual:retro-record-adhoc",
            project_path=str(root),
        )
    except ImportError:
        pass  # learning_db_v2 not available yet

    output_json(
        {
            "action": "retro-record-adhoc",
            "topic": topic,
            "key": key,
            "confidence": confidence,
            "clustered": clustered,
            "file": str(dest_file),
        },
        args,
    )
    return 0


def cmd_retro_promote(args: argparse.Namespace) -> int:
    """Promote a retro record from L3 to L2 if confidence threshold met."""
    root = find_project_root()
    feature_dir = root / FEATURE_DIR
    feature = slugify(args.feature)

    state = load_state(feature_dir, feature)
    if not state:
        output_error(f"Feature '{feature}' not found")
        return 1

    key = args.key
    record = state.retro_records.get(key)
    if not record:
        output_error(f"No retro record found for key '{key}'")
        return 1

    confidence = record.get("confidence", "low")
    if confidence not in ("medium", "high"):
        output_json(
            {
                "action": "retro-promote",
                "promoted": False,
                "reason": f"Confidence '{confidence}' below threshold (need medium or high)",
            },
            args,
        )
        return 0

    # Promote to L2 context
    phase = record.get("phase", state.current_phase)
    context_dir = feature_dir / "context" / phase
    context_dir.mkdir(parents=True, exist_ok=True)
    context_file = context_dir / f"{key}.md"

    content = f"# {key.replace('-', ' ').title()}\n\n{record['value']}\n\n*Promoted from retro [{confidence}]*\n"
    context_file.write_text(content)

    # Update L1 summary
    l1_file = feature_dir / "context" / f"{phase.upper()}.md"
    if l1_file.exists():
        l1_content = l1_file.read_text()
        if key not in l1_content:
            l1_content += f"\n- **{key}**: {record['value'][:80]}... (see {phase}/{key}.md)\n"
            l1_file.write_text(l1_content)

    output_json(
        {
            "action": "retro-promote",
            "promoted": True,
            "key": key,
            "from": f"meta/{phase}/{key}.md",
            "to": f"context/{phase}/{key}.md",
            "l1_updated": str(l1_file),
        },
        args,
    )
    return 0


def cmd_context_read(args: argparse.Namespace) -> int:
    """Read context at specified level."""
    root = find_project_root()
    feature_dir = root / FEATURE_DIR
    level = args.level.upper()
    feature = slugify(args.feature) if args.feature else None

    if level == "L0":
        l0_file = feature_dir / "FEATURE.md"
        content = l0_file.read_text() if l0_file.exists() else "(no L0 file)"
    elif level == "L1":
        phase = args.phase or "design"
        l1_file = feature_dir / "context" / f"{phase.upper()}.md"
        content = l1_file.read_text() if l1_file.exists() else f"(no L1 for {phase})"
    elif level == "L2":
        phase = args.phase or "design"
        l2_dir = feature_dir / "context" / phase
        if l2_dir.exists():
            files = sorted(l2_dir.glob("*.md"))
            content = "\n---\n".join(f.read_text() for f in files) if files else f"(no L2 files for {phase})"
        else:
            content = f"(no L2 directory for {phase})"
    else:
        output_error(f"Invalid level: {level}. Must be L0, L1, or L2")
        return 1

    output_json({"level": level, "content": content}, args)
    return 0


def cmd_worktree(args: argparse.Namespace) -> int:
    """Manage git worktrees for features."""
    root = find_project_root()
    feature_dir = root / FEATURE_DIR
    feature = slugify(args.feature)
    action = args.action

    state = load_state(feature_dir, feature)
    if not state:
        output_error(f"Feature '{feature}' not found")
        return 1

    if action == "create":
        worktree_path = root / FEATURE_DIR / "worktrees" / feature
        branch = f"feature/{feature}"

        # Create branch if it doesn't exist
        result = subprocess.run(
            ["git", "branch", "--list", branch],
            capture_output=True,
            text=True,
            cwd=str(root),
        )
        if not result.stdout.strip():
            subprocess.run(
                ["git", "branch", branch],
                capture_output=True,
                text=True,
                cwd=str(root),
            )

        # Create worktree
        worktree_path.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "worktree", "add", str(worktree_path), branch],
            capture_output=True,
            text=True,
            cwd=str(root),
        )
        if result.returncode != 0:
            output_error(f"Failed to create worktree: {result.stderr}")
            return 1

        state.worktree_path = str(worktree_path)
        save_state(feature_dir, state)

        output_json(
            {"action": "worktree-create", "path": str(worktree_path), "branch": branch},
            args,
        )

    elif action == "path":
        output_json(
            {"action": "worktree-path", "path": state.worktree_path or "(none)"},
            args,
        )

    elif action == "cleanup":
        if state.worktree_path and Path(state.worktree_path).exists():
            subprocess.run(
                ["git", "worktree", "remove", state.worktree_path, "--force"],
                capture_output=True,
                text=True,
                cwd=str(root),
            )
        state.worktree_path = ""
        save_state(feature_dir, state)
        output_json({"action": "worktree-cleanup", "feature": feature}, args)

    return 0


def cmd_complete(args: argparse.Namespace) -> int:
    """Mark feature as complete, archive, and cleanup."""
    root = find_project_root()
    feature_dir = root / FEATURE_DIR
    feature = slugify(args.feature)

    state = load_state(feature_dir, feature)
    if not state:
        output_error(f"Feature '{feature}' not found")
        return 1

    # Archive retro knowledge BEFORE moving state (archival reads state file)
    retro_archived = _archive_retro_knowledge(root, feature_dir, feature)

    # Move state to completed
    completed_dir = feature_dir / "state" / "completed"
    completed_dir.mkdir(parents=True, exist_ok=True)
    state_file = feature_dir / "state" / f"{feature}.json"
    if state_file.exists():
        dest = completed_dir / f"{date.today().isoformat()}-{feature}.json"
        state_file.rename(dest)

    # Cleanup worktree
    if state.worktree_path and Path(state.worktree_path).exists():
        subprocess.run(
            ["git", "worktree", "remove", state.worktree_path, "--force"],
            capture_output=True,
            text=True,
            cwd=str(root),
        )

    output_json({"action": "complete", "feature": feature, "archived": True, "retro_archived": retro_archived}, args)
    return 0


def _expand_tags(tags: set[str]) -> set[str]:
    """Expand a set of tags with common synonyms from TAG_SYNONYMS."""
    expanded = set(tags)
    for tag in tags:
        if tag in TAG_SYNONYMS:
            expanded.update(TAG_SYNONYMS[tag])
    return expanded


def _detect_languages(feature_dir: Path, feature: str) -> list[str]:
    """Detect programming languages from feature checkpoint files.

    Scans .feature/state/ checkpoint .md files for file extension patterns
    like .go, .py, .ts to infer which languages the feature touched.
    """
    languages: set[str] = set()
    extension_map = {
        r"\.go\b": "go",
        r"\.py\b": "python",
        r"\.ts\b": "typescript",
        r"\.tsx\b": "typescript",
    }

    state_dir = feature_dir / "state"
    if not state_dir.is_dir():
        return ["*"]

    for md_file in state_dir.rglob("*.md"):
        try:
            content = md_file.read_text()
            for pattern, lang in extension_map.items():
                if re.search(pattern, content):
                    languages.add(lang)
        except OSError:
            continue

    return sorted(languages) if languages else ["*"]


def _increment_observation(content: str, heading: str) -> tuple[str, bool]:
    """Increment [Nx] counter for an existing ### heading in L2 content.

    If heading exists, bump its observation count. If no count tag exists,
    assumes 1x and increments to [2x].

    Returns (updated_content, was_incremented).
    """
    escaped = re.escape(heading)
    pattern = re.compile(rf"(### {escaped})\s*(?:\[(\d+)x\])?")
    match = pattern.search(content)
    if match:
        count = int(match.group(2) or 1) + 1
        replacement = f"{match.group(1)} [{count}x]"
        return content[: match.start()] + replacement + content[match.end() :], True
    return content, False


def _regenerate_l1(retro_dir: Path) -> None:
    """Regenerate retro/L1.md from all retro/L2/*.md files.

    Reads all L2 files, groups learnings by tags, and writes a compact
    ~20 line summary to retro/L1.md.
    """
    l2_dir = retro_dir / "L2"
    if not l2_dir.is_dir():
        return

    l2_files = sorted(l2_dir.glob("*.md"))
    if not l2_files:
        return

    # Parse each L2 file: extract tags and ### headings with first paragraph
    topic_groups: dict[str, list[str]] = {}  # tag_group -> list of learnings

    for l2_file in l2_files:
        try:
            content = l2_file.read_text()
        except OSError:
            continue

        # Extract tags and build a readable section heading
        tags_match = re.search(r"\*\*Tags\*\*:\s*(.+)", content)
        if tags_match:
            raw_tags = [t.strip() for t in tags_match.group(1).split(",")]
            # Use first 2-3 distinctive tags as section heading
            heading_tags = [t for t in raw_tags if t not in ("go", "python", "typescript")][:3]
            if not heading_tags:
                heading_tags = raw_tags[:2]
            tag_key = " / ".join(t.replace("-", " ").title() for t in heading_tags) + " Patterns"
        else:
            tag_key = l2_file.stem.replace("-", " ").title() + " Patterns"

        # Extract ### headings with first paragraph
        sections = re.findall(r"###\s+(.+?)(?:\n\n|\n)(.+?)(?:\n\n|\n---|$)", content, re.DOTALL)
        learnings = []
        for heading, body in sections:
            # Take first sentence or first 100 chars
            first_line = body.strip().split("\n")[0][:100]
            learnings.append(f"{heading.strip()}: {first_line}")

        if not learnings:
            # Fallback: use ## headings
            h2_sections = re.findall(r"##\s+(.+)", content)
            learnings = [h.strip() for h in h2_sections if not h.startswith("#")]

        if learnings:
            if tag_key not in topic_groups:
                topic_groups[tag_key] = []
            topic_groups[tag_key].extend(learnings)

    # Build L1 with ~20 line budget
    lines = ["# Accumulated Knowledge (L1 Summary)", ""]
    line_budget = 20
    lines_used = 2  # header + blank

    for group_name, learnings in topic_groups.items():
        if lines_used >= line_budget:
            break
        lines.append(f"## {group_name}")
        lines_used += 1
        for learning in learnings:
            if lines_used >= line_budget:
                break
            lines.append(f"- {learning}")
            lines_used += 1
        lines.append("")
        lines_used += 1

    l1_path = retro_dir / "L1.md"
    l1_path.write_text("\n".join(lines) + "\n")
    print(f"[retro-archive] Regenerated L1 from {len(l2_files)} L2 files", file=sys.stderr)


def _archive_retro_knowledge(root: Path, feature_dir: Path, feature: str) -> bool:
    """Archive L2 retro knowledge from .feature/ to retro/L2/ on completion.

    Copies promoted L2 context files to the persistent retro store so they
    are available for future features via the retro-knowledge-injector hook.
    Also regenerates the L1 summary from all L2 files.

    Returns True if any knowledge was archived.
    """
    retro_dir = root / "retro"
    l2_dest = retro_dir / "L2"

    archived = False

    # Primary path: build enriched L2 file from retro_records (has tags + languages)
    if hasattr(feature_dir, "exists"):
        state = load_state(feature_dir, feature)
        if state and state.retro_records:
            promoted = {
                k: v for k, v in state.retro_records.items() if v.get("confidence", "low").upper() in ("MEDIUM", "HIGH")
            }
            if promoted:
                l2_dest.mkdir(parents=True, exist_ok=True)
                dest_file = l2_dest / f"{feature}.md"
                lines = [f"# Retro: {feature.replace('-', ' ').title()}"]
                lines.append(f"**Source**: feature/{feature}")
                lines.append("**Confidence**: MEDIUM")

                # Collect tags from record keys and expand with synonyms
                tags: set[str] = set()
                for key in promoted:
                    tags.update(key.replace("-", " ").split())
                tags = _expand_tags(tags)
                lines.append(f"**Tags**: {', '.join(sorted(tags))}")

                # Detect languages from feature state files
                languages = _detect_languages(feature_dir, feature)
                lines.append(f"**Languages**: {', '.join(languages)}")
                lines.append("")

                for key, record in promoted.items():
                    heading = key.replace("-", " ").title()
                    obs_count = record.get("observations", 1)
                    count_tag = f" [{obs_count}x]" if obs_count > 1 else ""
                    lines.append(f"### {heading}{count_tag}")
                    lines.append(record.get("value", ""))
                    lines.append("")

                content = "\n".join(lines)
                if dest_file.exists():
                    existing = dest_file.read_text()
                    # Observation clustering: increment counts for existing headings
                    for key, record in promoted.items():
                        heading = key.replace("-", " ").title()
                        updated, clustered = _increment_observation(existing, heading)
                        if clustered:
                            existing = updated
                        elif f"### {heading}" not in existing:
                            obs = record.get("observations", 1)
                            tag = f" [{obs}x]" if obs > 1 else ""
                            existing += f"\n### {heading}{tag}\n{record.get('value', '')}\n"
                    dest_file.write_text(existing)
                else:
                    dest_file.write_text(content)
                archived = True

    # Fallback path: copy any L2 context files not already captured via retro_records
    for phase in PHASES:
        l2_src = feature_dir / "context" / phase
        if not l2_src.is_dir():
            continue

        for f in l2_src.glob("*.md"):
            try:
                content = f.read_text().strip()
                if not content or "(populated by retro loop)" in content:
                    continue

                l2_dest.mkdir(parents=True, exist_ok=True)
                dest_file = l2_dest / f"{feature}.md"

                if dest_file.exists():
                    existing = dest_file.read_text()
                    if content not in existing:
                        dest_file.write_text(existing + "\n\n---\n\n" + content)
                else:
                    dest_file.write_text(content)
                archived = True
            except OSError:
                continue

    # Regenerate L1 summary from all L2 files
    if archived:
        _regenerate_l1(retro_dir)

    return archived


def cmd_retro_audit(args: argparse.Namespace) -> int:
    """Audit retro/L2 files for staleness, orphans, and quality issues."""
    root = find_project_root()
    retro_dir = root / "retro"
    l2_dir = retro_dir / "L2"

    if not l2_dir.is_dir():
        output_json({"audit": "retro-l2", "total_files": 0, "issues": [], "message": "No retro/L2/ directory"}, args)
        return 0

    issues = []
    all_headings: dict[str, list[str]] = {}  # heading -> [file1, file2]
    l2_files = sorted(l2_dir.glob("*.md"))

    for f in l2_files:
        try:
            content = f.read_text()
        except OSError:
            issues.append({"file": f.name, "type": "unreadable", "severity": "high"})
            continue

        file_issues = []

        # Check for missing Tags line
        if "**Tags**:" not in content:
            file_issues.append(
                {"type": "missing_tags", "severity": "high", "hint": "Add **Tags**: line for relevance matching"}
            )

        # Check for missing Languages line
        if "**Languages**:" not in content:
            file_issues.append(
                {
                    "type": "missing_languages",
                    "severity": "medium",
                    "hint": "Add **Languages**: line for cross-language gating",
                }
            )

        # Check for empty content (no ### headings = no learnings)
        headings = re.findall(r"^### (.+?)(?:\s*\[\d+x\])?$", content, re.MULTILINE)
        if not headings:
            file_issues.append(
                {"type": "no_learnings", "severity": "high", "hint": "No ### headings found; no actionable learnings"}
            )

        # Track headings for cross-file duplicate detection
        for h in headings:
            normalized = h.strip().lower()
            all_headings.setdefault(normalized, []).append(f.name)

        if file_issues:
            issues.append({"file": f.name, "issues": file_issues})

    # Report cross-file duplicates
    duplicates = {h: files for h, files in all_headings.items() if len(files) > 1}
    for heading, files in duplicates.items():
        issues.append(
            {
                "type": "cross_file_duplicate",
                "heading": heading,
                "files": files,
                "severity": "low",
                "hint": "Same learning in multiple files; consider consolidating",
            }
        )

    summary = {
        "audit": "retro-l2",
        "total_files": len(l2_files),
        "files_with_issues": sum(1 for i in issues if "file" in i and "issues" in i),
        "cross_file_duplicates": len(duplicates),
        "issues": issues,
    }

    output_json(summary, args)
    return 0


def cmd_retro_candidates(args: argparse.Namespace) -> int:
    """Identify L2 entries mature enough for graduation into agents/skills.

    Graduation criteria (ALL must be met):
    - Confidence: HIGH
    - Observation count: >= 3 (clustered [Nx] >= 3)
    - Content is specific and actionable (not generic advice) — left to AI reviewer

    This command does the deterministic pre-filtering. The AI skill
    (/retro graduate) evaluates the candidates for actual graduation.
    """
    root = find_project_root()
    retro_dir = root / "retro"
    l2_dir = retro_dir / "L2"
    agents_dir = root / "agents"

    if not l2_dir.is_dir():
        output_json({"candidates": [], "message": "No retro/L2/ directory"}, args)
        return 0

    min_observations = getattr(args, "min_observations", 3)
    candidates = []

    for f in sorted(l2_dir.glob("*.md")):
        try:
            content = f.read_text()
        except OSError:
            continue

        # Extract confidence
        conf_match = re.search(r"\*\*Confidence\*\*:\s*(\w+)", content)
        confidence = conf_match.group(1).upper() if conf_match else "LOW"

        # Extract tags
        tags_match = re.search(r"\*\*Tags\*\*:\s*(.+)", content)
        tags = [t.strip() for t in tags_match.group(1).split(",")] if tags_match else []

        # Parse each ### heading with observation count
        for match in re.finditer(
            r"^### (.+?)(?:\s*\[(\d+)x\])?\s*$\n(.*?)(?=\n### |\Z)",
            content,
            re.MULTILINE | re.DOTALL,
        ):
            heading = match.group(1).strip()
            obs_count = int(match.group(2) or 1)
            value = match.group(3).strip()

            # Filter: HIGH confidence + enough observations
            if confidence == "HIGH" and obs_count >= min_observations:
                candidates.append(
                    {
                        "topic": f.stem,
                        "key": heading,
                        "value": value,
                        "confidence": confidence,
                        "observations": obs_count,
                        "tags": tags,
                        "source_file": str(f.relative_to(root)),
                    }
                )

    # Find matching agents by reading retro-topics from frontmatter
    agent_matches = {}
    if agents_dir.is_dir():
        for agent_file in sorted(agents_dir.glob("*.md")):
            try:
                agent_content = agent_file.read_text()
            except OSError:
                continue

            # Parse YAML frontmatter for retro-topics
            fm_match = re.match(r"^---\n(.*?)\n---", agent_content, re.DOTALL)
            if not fm_match:
                continue

            # Simple YAML extraction for retro-topics list
            topics_match = re.search(
                r"retro-topics:\s*\n((?:\s+-\s+.+\n)*)",
                fm_match.group(1),
            )
            if topics_match:
                topics = [t.strip().lstrip("- ") for t in topics_match.group(1).strip().split("\n") if t.strip()]
                for topic in topics:
                    agent_matches.setdefault(topic, []).append(agent_file.stem)

    # Annotate candidates with matching agents
    for c in candidates:
        c["matching_agents"] = agent_matches.get(c["topic"], [])

    output_json(
        {
            "candidates": candidates,
            "total_l2_files": len(list(l2_dir.glob("*.md"))),
            "graduation_criteria": {
                "min_confidence": "HIGH",
                "min_observations": min_observations,
            },
            "agent_topic_map": agent_matches,
        },
        args,
    )
    return 0


def cmd_abandon(args: argparse.Namespace) -> int:
    """Abandon a feature with reason."""
    root = find_project_root()
    feature_dir = root / FEATURE_DIR
    feature = slugify(args.feature)

    state = load_state(feature_dir, feature)
    if not state:
        output_error(f"Feature '{feature}' not found")
        return 1

    # Move state to abandoned
    abandoned_dir = feature_dir / "state" / "abandoned"
    abandoned_dir.mkdir(parents=True, exist_ok=True)
    state_file = feature_dir / "state" / f"{feature}.json"
    if state_file.exists():
        dest = abandoned_dir / f"{date.today().isoformat()}-{feature}.json"
        state_file.rename(dest)

    # Cleanup worktree
    if state.worktree_path and Path(state.worktree_path).exists():
        subprocess.run(
            ["git", "worktree", "remove", state.worktree_path, "--force"],
            capture_output=True,
            text=True,
            cwd=str(root),
        )

    reason = args.reason or "No reason given"
    output_json({"action": "abandon", "feature": feature, "reason": reason}, args)
    return 0


def output_json(data: dict, args: argparse.Namespace | None = None) -> None:
    """Output structured JSON."""
    human = getattr(args, "human", False) if args else False
    if human:
        for k, v in data.items():
            if isinstance(v, list):
                print(f"{k}:")
                for item in v:
                    if isinstance(item, dict):
                        print(f"  - {item.get('name', item)}: {item.get('phase', '')}")
                    else:
                        print(f"  - {item}")
            elif isinstance(v, dict):
                print(f"{k}:")
                for sk, sv in v.items():
                    print(f"  {sk}: {sv}")
            else:
                print(f"{k}: {v}")
    else:
        print(json.dumps(data, indent=2))


def output_error(message: str) -> None:
    """Output error message."""
    print(json.dumps({"error": message}), file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Feature lifecycle state management CLI")
    parser.add_argument("--human", action="store_true", help="Human-readable output")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # init
    p_init = subparsers.add_parser("init", help="Initialize a new feature")
    p_init.add_argument("feature_name", help="Feature name (will be slugified)")

    # status
    p_status = subparsers.add_parser("status", help="Show feature status")
    p_status.add_argument("feature_name", nargs="?", help="Specific feature name")

    # checkpoint
    p_cp = subparsers.add_parser("checkpoint", help="Save phase checkpoint")
    p_cp.add_argument("feature", help="Feature name")
    p_cp.add_argument("phase", help="Phase name")

    # advance
    p_adv = subparsers.add_parser("advance", help="Advance to next phase")
    p_adv.add_argument("feature", help="Feature name")

    # gate
    p_gate = subparsers.add_parser("gate", help="Check gate status")
    p_gate.add_argument("feature", help="Feature name")
    p_gate.add_argument("gate_id", help="Gate identifier (e.g., design.approach-selection)")

    # retro-record
    p_rr = subparsers.add_parser("retro-record", help="Write retro record")
    p_rr.add_argument("feature", help="Feature name")
    p_rr.add_argument("key", help="Record key")
    p_rr.add_argument("value", help="Record value")
    p_rr.add_argument("--confidence", default="low", choices=["low", "medium", "high"])

    # retro-record-adhoc
    p_rra = subparsers.add_parser("retro-record-adhoc", help="Write retro record directly to L2 (no feature needed)")
    p_rra.add_argument("topic", help="L2 topic file name (e.g., go-patterns, testing)")
    p_rra.add_argument("key", help="Record key (becomes ### heading)")
    p_rra.add_argument("value", help="Record value")
    p_rra.add_argument(
        "--confidence",
        default="medium",
        choices=["low", "medium", "high"],
        help="Confidence level (default: medium). Use 'high' for valuable single findings.",
    )

    # retro-promote
    p_rp = subparsers.add_parser("retro-promote", help="Promote retro record L3→L2")
    p_rp.add_argument("feature", help="Feature name")
    p_rp.add_argument("key", help="Record key to promote")

    # context-read
    p_cr = subparsers.add_parser("context-read", help="Read context at level")
    p_cr.add_argument("feature", nargs="?", help="Feature name")
    p_cr.add_argument("level", help="Context level: L0, L1, L2")
    p_cr.add_argument("--phase", help="Phase for L1/L2 reads")

    # worktree
    p_wt = subparsers.add_parser("worktree", help="Manage worktrees")
    p_wt.add_argument("feature", help="Feature name")
    p_wt.add_argument("action", choices=["create", "path", "cleanup"])

    # complete
    p_done = subparsers.add_parser("complete", help="Complete and archive feature")
    p_done.add_argument("feature", help="Feature name")

    # retro-audit
    subparsers.add_parser("retro-audit", help="Audit retro/L2 for stale/orphan files")

    # retro-candidates
    p_rc = subparsers.add_parser("retro-candidates", help="Identify L2 entries mature enough for graduation")
    p_rc.add_argument("--min-observations", type=int, default=3, help="Minimum observation count (default: 3)")

    # abandon
    p_abn = subparsers.add_parser("abandon", help="Abandon feature")
    p_abn.add_argument("feature", help="Feature name")
    p_abn.add_argument("--reason", help="Reason for abandoning")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "init": cmd_init,
        "status": cmd_status,
        "checkpoint": cmd_checkpoint,
        "advance": cmd_advance,
        "gate": cmd_gate,
        "retro-record": cmd_retro_record,
        "retro-record-adhoc": cmd_retro_record_adhoc,
        "retro-promote": cmd_retro_promote,
        "context-read": cmd_context_read,
        "worktree": cmd_worktree,
        "complete": cmd_complete,
        "retro-audit": cmd_retro_audit,
        "retro-candidates": cmd_retro_candidates,
        "abandon": cmd_abandon,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
