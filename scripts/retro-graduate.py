#!/usr/bin/env python3
"""
Deterministic retro graduation CLI with value-based scoring.

Scores L2 retro entries and graduation queue items for readiness to be
embedded permanently into agent/skill files. Uses heuristic scoring
(actionability, specificity, target clarity, confidence) instead of
frequency-only filtering.

Subcommands:
    python3 scripts/retro-graduate.py scan                 # Score all L2 entries + queue items, output JSON
    python3 scripts/retro-graduate.py scan --human          # Human-readable output
    python3 scripts/retro-graduate.py scan --threshold 7    # Override score threshold (default: 6)

    python3 scripts/retro-graduate.py queue-add TOPIC KEY VALUE          # Add finding to graduation queue
    python3 scripts/retro-graduate.py queue-add TOPIC KEY VALUE --confidence HIGH
    python3 scripts/retro-graduate.py queue-add TOPIC KEY VALUE --source-repo /path

    python3 scripts/retro-graduate.py mark TOPIC KEY TARGET  # Mark L2 entry as graduated
    python3 scripts/retro-graduate.py mark debugging "Worktree Branch Cleanup" "pr-cleanup,pr-pipeline"

Exit codes:
    0 = success
    1 = error
"""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_THRESHOLD = 6
GRADUATION_QUEUE_PATH = Path.home() / ".claude" / "retro" / "graduation-queue.md"

# Tokens that suggest code-level specificity (actionability scoring)
CODE_TOKENS_PATTERN = re.compile(
    r"""
    \b(?:
        sync\.Mutex|sync\.WaitGroup|sync\.Once|sync\.Map|
        atomic\.\w+|context\.With\w+|
        fmt\.Errorf|errors\.Is|errors\.As|errors\.New|
        http\.RoundTripper|http\.Handler|http\.Client|
        json\.Marshal|json\.Unmarshal|
        os\.Getenv|os\.Open|os\.ReadFile|
        filepath\.\w+|path\.\w+|
        io\.Reader|io\.Writer|io\.Closer|
        regexp\.Compile|regexp\.MustCompile|
        strings\.\w+|bytes\.\w+|
        time\.Duration|time\.Timer|time\.Ticker|
        chan\s+\w+|select\s*\{|
        go\s+func|goroutine|
        subprocess\.\w+|pathlib\.Path|
        pytest\.\w+|unittest\.\w+|
        argparse\.\w+|dataclass|
        async\s+def|await\s+|asyncio\.\w+|
        import\s+\w+|from\s+\w+|
        def\s+\w+|func\s+\w+|class\s+\w+|
        git\s+\w+|gh\s+\w+|
        \.go\b|\.py\b|\.ts\b|\.js\b|\.md\b|
        --\w[\w-]+|                # CLI flags like --delete-branch
        \w+\.\w+\(\)               # method calls like obj.method()
    )\b
    """,
    re.VERBOSE,
)

# Generic / vague phrases that reduce specificity
GENERIC_PHRASES = [
    "be careful",
    "use proper",
    "follow best practices",
    "write good code",
    "handle errors properly",
    "use appropriate",
    "consider using",
    "make sure to",
    "always remember",
    "keep in mind",
]

# Domain-narrowing technical terms (specificity scoring)
DOMAIN_TERMS_PATTERN = re.compile(
    r"""
    \b(?:
        circuit.?breaker|state.?machine|round.?tripper|
        health.?endpoint|health.?check|liveness|readiness|
        worktree|frontmatter|retro.?topic|
        middleware|interceptor|rate.?limit|
        serialization|deserialization|marshal|unmarshal|
        mutex|semaphore|deadlock|race.?condition|
        dependency.?injection|inversion.?of.?control|
        backpressure|fan.?out|fan.?in|
        idempoten|eventual.?consistency|
        YAML|TOML|JSON.?schema|protobuf|
        ORM|migration|schema|
        webhook|callback|polling|
        sharding|partitioning|replication|
        TLS|mTLS|RBAC|OAuth|JWT|
        gRPC|REST|GraphQL|WebSocket
    )\b
    """,
    re.VERBOSE | re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Project root detection
# ---------------------------------------------------------------------------


def find_project_root() -> Path:
    """Find project root by looking for .git directory."""
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists() or (current / ".git").is_file():
            return current
        current = current.parent
    return Path.cwd()


# ---------------------------------------------------------------------------
# Agent retro-topics loading
# ---------------------------------------------------------------------------


def load_agent_retro_topics(agents_dir: Path) -> dict[str, list[str]]:
    """Load retro-topics from agent YAML frontmatter.

    Returns:
        Mapping of topic name to list of agent stems that subscribe to it.
    """
    topic_map: dict[str, list[str]] = {}
    if not agents_dir.is_dir():
        return topic_map

    for agent_file in sorted(agents_dir.glob("*.md")):
        try:
            content = agent_file.read_text()
        except OSError:
            continue

        fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not fm_match:
            continue

        topics_match = re.search(
            r"retro-topics:\s*\n((?:\s+-\s+.+\n)*)",
            fm_match.group(1),
        )
        if topics_match:
            topics = [t.strip().lstrip("- ") for t in topics_match.group(1).strip().split("\n") if t.strip()]
            for topic in topics:
                topic_map.setdefault(topic, []).append(agent_file.stem)

    return topic_map


# ---------------------------------------------------------------------------
# L2 file parsing
# ---------------------------------------------------------------------------


def parse_l2_file(filepath: Path) -> list[dict[str, Any]]:
    """Parse an L2 retro markdown file into a list of entries.

    Each entry dict contains: topic, key, value, confidence, observations,
    graduated (bool), graduated_target (str or None), source, source_file.
    """
    try:
        content = filepath.read_text()
    except OSError:
        return []

    # Extract file-level metadata
    conf_match = re.search(r"\*\*Confidence\*\*:\s*(\w+)", content)
    confidence = conf_match.group(1).upper() if conf_match else "LOW"

    topic = filepath.stem
    entries: list[dict[str, Any]] = []

    # Match ### headings with optional [Nx] and optional [GRADUATED -> target]
    pattern = re.compile(
        r"^### (.+?)(?:\s*\[(\d+)x\])?\s*(?:\[GRADUATED\s*(?:→|->)\s*(.+?)\])?\s*$\n(.*?)(?=\n### |\Z)",
        re.MULTILINE | re.DOTALL,
    )

    for match in pattern.finditer(content):
        heading = match.group(1).strip()
        obs_count = int(match.group(2) or 1)
        grad_target = match.group(3)
        value = match.group(4).strip()

        entries.append(
            {
                "topic": topic,
                "key": heading,
                "value": value,
                "confidence": confidence,
                "observations": obs_count,
                "graduated": grad_target is not None,
                "graduated_target": grad_target.strip() if grad_target else None,
                "source": "l2",
                "source_file": str(filepath),
            }
        )

    return entries


# ---------------------------------------------------------------------------
# Graduation queue parsing
# ---------------------------------------------------------------------------


def parse_graduation_queue(queue_path: Path) -> list[dict[str, Any]]:
    """Parse graduation-queue.md YAML-like blocks into entry dicts.

    Each block is delimited by --- fences. Fields are key: value pairs.
    """
    if not queue_path.is_file():
        return []

    try:
        content = queue_path.read_text()
    except OSError:
        return []

    entries: list[dict[str, Any]] = []

    # Extract blocks between --- delimiters
    blocks = re.findall(r"---\n(.*?)\n---", content, re.DOTALL)
    for block in blocks:
        entry: dict[str, Any] = {}
        for line in block.strip().split("\n"):
            line = line.strip().lstrip("- ")
            kv_match = re.match(r"^(\w[\w_]*):\s*(.+)$", line)
            if kv_match:
                key = kv_match.group(1)
                val = kv_match.group(2).strip().strip('"').strip("'")
                entry[key] = val

        if "key" in entry and "value" in entry:
            entries.append(
                {
                    "topic": entry.get("topic", "unknown"),
                    "key": entry["key"],
                    "value": entry["value"],
                    "confidence": entry.get("confidence", "MEDIUM").upper(),
                    "observations": 1,
                    "graduated": False,
                    "graduated_target": None,
                    "source": "queue",
                    "source_file": str(queue_path),
                    "source_repo": entry.get("source_repo", ""),
                    "queued_at": entry.get("queued_at", ""),
                }
            )

    return entries


# ---------------------------------------------------------------------------
# Scoring heuristics
# ---------------------------------------------------------------------------


def score_actionability(value: str) -> int:
    """Score actionability 0-3 based on code-level specificity.

    0: No action / vague statement
    1: Vague action (generic advice)
    2: Specific category (mentions a concrete tool/pattern)
    3: Exact pattern with code-level specificity
    """
    # Check for generic phrases first
    lower_value = value.lower()
    generic_count = sum(1 for phrase in GENERIC_PHRASES if phrase in lower_value)
    if generic_count >= 2:
        return 0

    # Count code-like tokens
    code_tokens = CODE_TOKENS_PATTERN.findall(value)
    token_count = len(code_tokens)

    if token_count >= 4:
        return 3
    if token_count >= 2:
        return 2
    if token_count >= 1:
        return 1
    return 0


def score_specificity(value: str, key: str) -> int:
    """Score specificity 0-3 based on domain narrowness.

    0: Universal advice
    1: Language-level (mentions a language but nothing narrow)
    2: Pattern-level (mentions a specific pattern or tool)
    3: Exact scenario (highly specific technical scenario)
    """
    combined = f"{key} {value}"

    # Count domain-narrowing terms
    domain_terms = DOMAIN_TERMS_PATTERN.findall(combined)
    domain_count = len(domain_terms)

    # Count code tokens for additional signal
    code_tokens = CODE_TOKENS_PATTERN.findall(combined)
    code_count = len(code_tokens)

    # Check total word count — very short entries are likely generic
    word_count = len(combined.split())

    if domain_count >= 2 and code_count >= 3:
        return 3
    if domain_count >= 1 and code_count >= 2:
        return 2
    if code_count >= 1 or domain_count >= 1 or word_count >= 20:
        return 1
    return 0


def score_target_clarity(topic: str, value: str, key: str, agent_topic_map: dict[str, list[str]]) -> int:
    """Score target clarity 0-2 based on whether a clear embedding target exists.

    0: No obvious target
    1: Domain is clear but multiple possible targets
    2: Exact target identified (single agent match or explicit mention)
    """
    # Direct match: topic matches an agent's retro-topics
    matching_agents = agent_topic_map.get(topic, [])

    if len(matching_agents) == 1:
        return 2
    if len(matching_agents) > 1:
        return 1

    # Check if the value or key explicitly mentions an agent/skill name
    combined = f"{key} {value}"
    # Look for patterns like "agent-name" or "skill-name" in the text
    for agent_topic, agents in agent_topic_map.items():
        if agent_topic in combined.lower():
            if len(agents) == 1:
                return 2
            return 1

    return 0


def score_confidence_boost(confidence: str) -> int:
    """Score confidence boost 0-2.

    HIGH: 2, MEDIUM: 1, LOW: 0
    """
    return {"HIGH": 2, "MEDIUM": 1, "LOW": 0}.get(confidence.upper(), 0)


def score_entry(entry: dict[str, Any], agent_topic_map: dict[str, list[str]]) -> dict[str, Any]:
    """Score a single entry and return it with score data attached.

    Returns the entry dict with added fields: score, score_breakdown, matching_agents.
    """
    value = entry["value"]
    key = entry["key"]
    topic = entry["topic"]
    confidence = entry["confidence"]

    actionability = score_actionability(value)
    specificity = score_specificity(value, key)
    target_clarity = score_target_clarity(topic, value, key, agent_topic_map)
    confidence_boost = score_confidence_boost(confidence)

    total = actionability + specificity + target_clarity + confidence_boost

    matching_agents = agent_topic_map.get(topic, [])

    entry["score"] = total
    entry["score_breakdown"] = {
        "actionability": actionability,
        "specificity": specificity,
        "target_clarity": target_clarity,
        "confidence_boost": confidence_boost,
    }
    entry["matching_agents"] = matching_agents
    return entry


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def output_json(data: dict[str, Any], human: bool = False) -> None:
    """Output structured JSON or human-readable format."""
    if human:
        _output_human(data)
    else:
        print(json.dumps(data, indent=2))


def _output_human(data: dict[str, Any]) -> None:
    """Output human-readable scan results."""
    candidates = data.get("candidates", [])
    below = data.get("below_threshold", [])
    graduated = data.get("graduated", [])
    threshold = data.get("scoring", {}).get("threshold", DEFAULT_THRESHOLD)

    print(f"=== Retro Graduation Scan (threshold: {threshold}) ===\n")

    if candidates:
        print(f"CANDIDATES ({len(candidates)}):")
        for c in candidates:
            bd = c.get("score_breakdown", {})
            agents = ", ".join(c.get("matching_agents", [])) or "none"
            print(f"  [{c['score']:2d}] {c['topic']}/{c['key']}")
            print(
                f"       A={bd.get('actionability', 0)} S={bd.get('specificity', 0)} "
                f"T={bd.get('target_clarity', 0)} C={bd.get('confidence_boost', 0)}  "
                f"agents=[{agents}]"
            )
            # Truncate value for display
            val = c["value"][:100] + "..." if len(c["value"]) > 100 else c["value"]
            print(f"       {val}")
            print()
    else:
        print("CANDIDATES: none\n")

    if below:
        print(f"BELOW THRESHOLD ({len(below)}):")
        for b in below:
            print(f"  [{b['score']:2d}] {b['topic']}/{b['key']}")
        print()

    if graduated:
        print(f"ALREADY GRADUATED ({len(graduated)}):")
        for g in graduated:
            print(f"  {g['topic']}/{g['key']} -> {g.get('graduated_target', '?')}")
        print()

    queue_count = data.get("queue_items_processed", 0)
    if queue_count:
        print(f"Queue items processed: {queue_count}")


def output_error(message: str) -> None:
    """Output error message to stderr as JSON."""
    print(json.dumps({"error": message}), file=sys.stderr)


# ---------------------------------------------------------------------------
# Subcommand: scan
# ---------------------------------------------------------------------------


def cmd_scan(args: argparse.Namespace) -> int:
    """Scan L2 entries and graduation queue, score each, output results."""
    root = find_project_root()
    l2_dir = root / "retro" / "L2"
    agents_dir = root / "agents"
    threshold: int = args.threshold
    human: bool = args.human

    # Load agent retro-topics mapping
    agent_topic_map = load_agent_retro_topics(agents_dir)

    # Collect all entries
    all_entries: list[dict[str, Any]] = []

    # Parse L2 files
    if l2_dir.is_dir():
        for f in sorted(l2_dir.glob("*.md")):
            entries = parse_l2_file(f)
            # Make source_file relative to project root
            for e in entries:
                with contextlib.suppress(ValueError):
                    e["source_file"] = str(Path(e["source_file"]).relative_to(root))
            all_entries.extend(entries)

    # Parse graduation queue
    queue_entries = parse_graduation_queue(GRADUATION_QUEUE_PATH)
    all_entries.extend(queue_entries)

    # Separate graduated from active
    graduated: list[dict[str, Any]] = []
    active: list[dict[str, Any]] = []
    for entry in all_entries:
        if entry.get("graduated"):
            graduated.append(
                {
                    "topic": entry["topic"],
                    "key": entry["key"],
                    "graduated_target": entry.get("graduated_target"),
                    "source": entry["source"],
                    "source_file": entry["source_file"],
                }
            )
        else:
            active.append(entry)

    # Score active entries
    for entry in active:
        score_entry(entry, agent_topic_map)

    # Split into candidates vs below threshold
    candidates = sorted(
        [e for e in active if e["score"] >= threshold],
        key=lambda e: e["score"],
        reverse=True,
    )
    below_threshold = sorted(
        [e for e in active if e["score"] < threshold],
        key=lambda e: e["score"],
        reverse=True,
    )

    # Clean up internal fields before output
    for entry in candidates + below_threshold:
        entry.pop("graduated", None)
        entry.pop("graduated_target", None)

    result = {
        "candidates": candidates,
        "below_threshold": below_threshold,
        "graduated": graduated,
        "queue_items_processed": len(queue_entries),
        "scoring": {
            "threshold": threshold,
            "model": "actionability(0-3) + specificity(0-3) + target_clarity(0-2) + confidence(0-2)",
        },
    }

    output_json(result, human=human)
    return 0


# ---------------------------------------------------------------------------
# Subcommand: queue-add
# ---------------------------------------------------------------------------


def cmd_queue_add(args: argparse.Namespace) -> int:
    """Append a finding to the graduation queue file."""
    queue_path = GRADUATION_QUEUE_PATH
    queue_dir = queue_path.parent
    queue_dir.mkdir(parents=True, exist_ok=True)

    confidence: str = args.confidence.upper()
    source_repo: str = args.source_repo or str(Path.cwd())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    # Create file with header if it doesn't exist
    if not queue_path.is_file():
        queue_path.write_text("# Graduation Queue\nEntries queued from other repos for graduation processing.\n\n")

    # Append the new entry
    block = (
        f"---\n"
        f"- key: {args.key}\n"
        f"  topic: {args.topic}\n"
        f'  value: "{args.value}"\n'
        f"  confidence: {confidence}\n"
        f"  source_repo: {source_repo}\n"
        f"  queued_at: {now}\n"
        f"---\n"
    )

    with queue_path.open("a") as f:
        f.write("\n" + block)

    human: bool = args.human
    output_json(
        {
            "action": "queue-add",
            "topic": args.topic,
            "key": args.key,
            "confidence": confidence,
            "source_repo": source_repo,
            "queue_file": str(queue_path),
        },
        human=human,
    )
    return 0


# ---------------------------------------------------------------------------
# Subcommand: mark
# ---------------------------------------------------------------------------


def cmd_mark(args: argparse.Namespace) -> int:
    """Mark an L2 entry as graduated by modifying its heading."""
    root = find_project_root()
    l2_dir = root / "retro" / "L2"

    if not l2_dir.is_dir():
        output_error(
            "retro/L2/ directory not found. Run this command from the agents repo, "
            "or navigate to a directory containing retro/L2/."
        )
        return 1

    topic: str = args.topic
    key: str = args.key
    target: str = args.target

    l2_file = l2_dir / f"{topic}.md"
    if not l2_file.is_file():
        output_error(f"L2 file not found: {l2_file.relative_to(root)}")
        return 1

    try:
        content = l2_file.read_text()
    except OSError as e:
        output_error(f"Cannot read {l2_file}: {e}")
        return 1

    # Find the heading and append [GRADUATED -> target]
    # Match heading with optional [Nx] but without existing GRADUATED marker
    pattern = re.compile(
        r"^(### " + re.escape(key) + r"(?:\s*\[\d+x\])?)\s*$",
        re.MULTILINE,
    )

    match = pattern.search(content)
    if not match:
        output_error(f"Entry heading not found in {topic}.md: '{key}'")
        return 1

    original_heading = match.group(0)
    new_heading = f"{match.group(1)} [GRADUATED → {target}]"
    new_content = content.replace(original_heading, new_heading, 1)

    try:
        l2_file.write_text(new_content)
    except OSError as e:
        output_error(f"Cannot write {l2_file}: {e}")
        return 1

    human: bool = args.human
    output_json(
        {
            "action": "mark",
            "topic": topic,
            "key": key,
            "target": target,
            "file": str(l2_file.relative_to(root)),
        },
        human=human,
    )
    return 0


# ---------------------------------------------------------------------------
# Main / CLI
# ---------------------------------------------------------------------------


def main() -> int:
    """Parse arguments and dispatch to subcommand handler."""
    parser = argparse.ArgumentParser(description="Retro graduation CLI with value-based scoring")
    parser.add_argument("--human", action="store_true", help="Human-readable output (default: JSON)")
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run")

    # scan
    p_scan = subparsers.add_parser("scan", help="Score all L2 entries and queue items")
    p_scan.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_THRESHOLD,
        help=f"Minimum score for candidacy (default: {DEFAULT_THRESHOLD})",
    )

    # queue-add
    p_qa = subparsers.add_parser("queue-add", help="Add finding to graduation queue")
    p_qa.add_argument("topic", help="Domain category (e.g., go-patterns, debugging)")
    p_qa.add_argument("key", help="Short kebab-case identifier")
    p_qa.add_argument("value", help="The finding text")
    p_qa.add_argument(
        "--confidence", default="MEDIUM", choices=["HIGH", "MEDIUM", "LOW"], help="Confidence level (default: MEDIUM)"
    )
    p_qa.add_argument("--source-repo", help="Override detected source repo path")

    # mark
    p_mark = subparsers.add_parser("mark", help="Mark L2 entry as graduated")
    p_mark.add_argument("topic", help="L2 file stem (e.g., debugging)")
    p_mark.add_argument("key", help="Entry heading to mark")
    p_mark.add_argument("target", help="Target agent/skill name(s), comma-separated")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands: dict[str, Any] = {
        "scan": cmd_scan,
        "queue-add": cmd_queue_add,
        "mark": cmd_mark,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
