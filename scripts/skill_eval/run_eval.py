#!/usr/bin/env python3
"""Run trigger evaluation for a skill description.

Tests whether a skill's description causes Claude to trigger (read the skill)
for a set of queries. Outputs results as JSON.
"""

import argparse
import contextlib
import json
import os
import select
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from scripts.skill_eval.utils import parse_skill_md


def find_project_root() -> Path:
    """Find the project root by walking up from cwd looking for .claude/.

    Mimics how Claude Code discovers its project root, so the command file
    we create ends up where claude -p will look for it.
    """
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / ".claude").is_dir():
            return parent
    return current


def resolve_registered_skill_relpath(skill_path: Path, project_root: Path) -> Path | None:
    """Return repo-relative SKILL.md path when `skill_path` is a registered repo skill."""
    skill_md = (skill_path / "SKILL.md").resolve()
    try:
        rel = skill_md.relative_to(project_root.resolve())
    except ValueError:
        return None
    if len(rel.parts) >= 3 and rel.parts[0] == "skills" and rel.parts[-1] == "SKILL.md":
        return rel
    return None


def replace_description_in_skill_md(content: str, new_description: str) -> str:
    """Replace the top-level frontmatter description field in SKILL.md content."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md missing frontmatter (no opening ---)")

    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        raise ValueError("SKILL.md missing frontmatter (no closing ---)")

    frontmatter_lines = lines[1:end_idx]
    body_lines = lines[end_idx + 1 :]
    updated_frontmatter: list[str] = []
    replaced = False
    i = 0
    while i < len(frontmatter_lines):
        line = frontmatter_lines[i]
        if not replaced and line.startswith("description:"):
            updated_frontmatter.append("description: |")
            updated_frontmatter.extend(f"  {desc_line}" for desc_line in new_description.splitlines())
            replaced = True
            i += 1
            while i < len(frontmatter_lines) and (
                frontmatter_lines[i].startswith("  ") or frontmatter_lines[i].startswith("\t")
            ):
                i += 1
            continue
        updated_frontmatter.append(line)
        i += 1

    if not replaced:
        raise ValueError("SKILL.md frontmatter missing description field")

    rebuilt = ["---", *updated_frontmatter, "---", *body_lines]
    return "\n".join(rebuilt) + ("\n" if content.endswith("\n") else "")


def load_eval_set(path: Path) -> list[dict]:
    """Load eval tasks from list or common wrapped JSON shapes."""
    payload = json.loads(path.read_text())
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if "tasks" in payload and isinstance(payload["tasks"], list):
            return payload["tasks"]
        if "queries" in payload and isinstance(payload["queries"], list):
            return payload["queries"]
        train = payload.get("train")
        test = payload.get("test")
        if isinstance(train, list) or isinstance(test, list):
            return [*(train or []), *(test or [])]
    raise ValueError(
        "Unsupported eval set format; expected list, {tasks:[...]}, {queries:[...]}, or {train:[...], test:[...]}"
    )


@contextlib.contextmanager
def candidate_worktree(project_root: Path, registered_skill_relpath: Path, candidate_content: str | None):
    """Create a temporary git worktree and optionally patch the target skill content."""
    wt_path_str = tempfile.mkdtemp(prefix="skill-eval-wt-", dir="/tmp")
    wt_path = Path(wt_path_str)
    wt_path.rmdir()
    try:
        subprocess.run(
            ["git", "worktree", "add", wt_path_str, "HEAD"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            check=True,
        )
        if candidate_content is not None:
            (wt_path / registered_skill_relpath).write_text(candidate_content)
        yield wt_path
    finally:
        try:
            subprocess.run(
                ["git", "worktree", "remove", "--force", wt_path_str],
                cwd=str(project_root),
                capture_output=True,
                text=True,
            )
        except Exception:
            pass
        shutil.rmtree(wt_path_str, ignore_errors=True)


def run_single_query(
    query: str,
    skill_name: str,
    skill_description: str,
    timeout: int,
    project_root: str,
    eval_mode: str = "alias",
    model: str | None = None,
) -> bool:
    """Run a single query and return whether the skill was triggered.

    In alias mode, creates a command file in .claude/commands/ so it appears in
    Claude's available skills list. In registered mode, assumes the real skill
    is already present in the isolated worktree and detects only the real name.

    Uses --include-partial-messages to detect triggering early from
    stream events (content_block_start) rather than waiting for the
    full assistant message, which only arrives after tool execution.
    """
    unique_id = uuid.uuid4().hex[:8]
    clean_name = f"{skill_name}-skill-{unique_id}"
    accepted_skill_ids = {clean_name} if eval_mode == "alias" else {skill_name}
    project_commands_dir = Path(project_root) / ".claude" / "commands"
    command_file = project_commands_dir / f"{clean_name}.md"

    try:
        if eval_mode == "alias":
            project_commands_dir.mkdir(parents=True, exist_ok=True)
            # Use YAML block scalar to avoid breaking on quotes in description
            indented_desc = "\n  ".join(skill_description.split("\n"))
            command_content = (
                f"---\n"
                f"description: |\n"
                f"  {indented_desc}\n"
                f"---\n\n"
                f"# {skill_name}\n\n"
                f"This skill handles: {skill_description}\n"
            )
            command_file.write_text(command_content)

        cmd = [
            "claude",
            "-p",
            query,
            "--output-format",
            "stream-json",
            "--verbose",
            "--include-partial-messages",
        ]
        if model:
            cmd.extend(["--model", model])

        # Remove CLAUDECODE env var to allow nesting claude -p inside a
        # Claude Code session. The guard is for interactive terminal conflicts;
        # programmatic subprocess usage is safe.
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=project_root,
            env=env,
        )

        triggered = False
        start_time = time.time()
        buffer = ""
        # Track state for stream event detection
        pending_tool_name = None
        accumulated_json = ""

        try:
            while time.time() - start_time < timeout:
                if process.poll() is not None:
                    remaining = process.stdout.read()
                    if remaining:
                        buffer += remaining.decode("utf-8", errors="replace")
                    break

                ready, _, _ = select.select([process.stdout], [], [], 1.0)
                if not ready:
                    continue

                chunk = os.read(process.stdout.fileno(), 8192)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Early detection via stream events
                    if event.get("type") == "stream_event":
                        se = event.get("event", {})
                        se_type = se.get("type", "")

                        if se_type == "content_block_start":
                            cb = se.get("content_block", {})
                            if cb.get("type") == "tool_use":
                                tool_name = cb.get("name", "")
                                if tool_name in ("Skill", "Read"):
                                    pending_tool_name = tool_name
                                    accumulated_json = ""
                                else:
                                    pending_tool_name = None
                                    accumulated_json = ""

                        elif se_type == "content_block_delta" and pending_tool_name:
                            delta = se.get("delta", {})
                            if delta.get("type") == "input_json_delta":
                                accumulated_json += delta.get("partial_json", "")
                                if any(skill_id in accumulated_json for skill_id in accepted_skill_ids):
                                    triggered = True

                        elif se_type in ("content_block_stop", "message_stop"):
                            if pending_tool_name:
                                if any(skill_id in accumulated_json for skill_id in accepted_skill_ids):
                                    triggered = True
                                pending_tool_name = None
                                accumulated_json = ""
                            if se_type == "message_stop":
                                return triggered

                    # Fallback: full assistant message
                    elif event.get("type") == "assistant":
                        message = event.get("message", {})
                        for content_item in message.get("content", []):
                            if content_item.get("type") != "tool_use":
                                continue
                            tool_name = content_item.get("name", "")
                            tool_input = content_item.get("input", {})
                            if (
                                tool_name == "Skill"
                                and any(skill_id in tool_input.get("skill", "") for skill_id in accepted_skill_ids)
                            ) or (
                                tool_name == "Read"
                                and any(skill_id in tool_input.get("file_path", "") for skill_id in accepted_skill_ids)
                            ):
                                triggered = True
                        if triggered:
                            return True

                    elif event.get("type") == "result":
                        return triggered
        finally:
            # Clean up process on any exit path (return, exception, timeout)
            if process.poll() is None:
                process.kill()
                process.wait()

        return triggered
    finally:
        if eval_mode == "alias" and command_file.exists():
            command_file.unlink()


def run_eval(
    eval_set: list[dict],
    skill_name: str,
    description: str,
    num_workers: int,
    timeout: int,
    project_root: Path,
    runs_per_query: int = 1,
    trigger_threshold: float = 0.5,
    eval_mode: str = "auto",
    skill_path: Path | None = None,
    candidate_content: str | None = None,
    model: str | None = None,
) -> dict:
    """Run the full eval set and return results."""
    results = []

    effective_mode = eval_mode
    effective_project_root = project_root
    worktree_cm = contextlib.nullcontext(project_root)

    if effective_mode == "auto":
        if skill_path is not None and resolve_registered_skill_relpath(skill_path, project_root) is not None:
            effective_mode = "registered"
        else:
            effective_mode = "alias"

    if effective_mode == "registered":
        if skill_path is None:
            raise ValueError("registered eval mode requires skill_path")
        relpath = resolve_registered_skill_relpath(skill_path, project_root)
        if relpath is None:
            raise ValueError("registered eval mode requires skill_path under project_root/skills/*/SKILL.md")
        _name, original_description, original_content = parse_skill_md(skill_path)
        if candidate_content is None:
            if description != original_description:
                candidate_content = replace_description_in_skill_md(original_content, description)
            else:
                candidate_content = original_content
        worktree_cm = candidate_worktree(project_root, relpath, candidate_content)

    with worktree_cm as active_project_root:
        effective_project_root = active_project_root
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            future_to_info = {}
            for item in eval_set:
                for run_idx in range(runs_per_query):
                    future = executor.submit(
                        run_single_query,
                        item["query"],
                        skill_name,
                        description,
                        timeout,
                        str(effective_project_root),
                        effective_mode,
                        model,
                    )
                    future_to_info[future] = (item, run_idx)

            query_triggers: dict[str, list[bool]] = {}
            query_items: dict[str, dict] = {}
            for future in as_completed(future_to_info):
                item, _ = future_to_info[future]
                query = item["query"]
                query_items[query] = item
                if query not in query_triggers:
                    query_triggers[query] = []
                try:
                    query_triggers[query].append(future.result())
                except Exception as e:
                    print(f"Warning: query failed: {e}", file=sys.stderr)
                    query_triggers[query].append(False)

    for query, triggers in query_triggers.items():
        item = query_items[query]
        trigger_rate = sum(triggers) / len(triggers)
        should_trigger = item["should_trigger"]
        if should_trigger:
            did_pass = trigger_rate >= trigger_threshold
        else:
            did_pass = trigger_rate < trigger_threshold
        results.append(
            {
                "query": query,
                "should_trigger": should_trigger,
                "trigger_rate": trigger_rate,
                "triggers": sum(triggers),
                "runs": len(triggers),
                "run_vector": triggers,
                "pass": did_pass,
            }
        )

    passed = sum(1 for r in results if r["pass"])
    total = len(results)

    return {
        "skill_name": skill_name,
        "description": description,
        "results": results,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Run trigger evaluation for a skill description")
    parser.add_argument("--eval-set", required=True, help="Path to eval set JSON file")
    parser.add_argument("--skill-path", required=True, help="Path to skill directory")
    parser.add_argument("--description", default=None, help="Override description to test")
    parser.add_argument("--candidate-content-file", default=None, help="Optional full SKILL.md content to evaluate")
    parser.add_argument("--eval-mode", choices=["auto", "registered", "alias"], default="auto", help="Evaluator mode")
    parser.add_argument("--num-workers", type=int, default=1, help="Number of parallel workers")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout per query in seconds")
    parser.add_argument("--runs-per-query", type=int, default=1, help="Number of runs per query")
    parser.add_argument("--trigger-threshold", type=float, default=0.5, help="Trigger rate threshold")
    parser.add_argument("--model", default=None, help="Model to use for claude -p (default: user's configured model)")
    parser.add_argument("--verbose", action="store_true", help="Print progress to stderr")
    args = parser.parse_args()

    eval_set = load_eval_set(Path(args.eval_set))
    skill_path = Path(args.skill_path)

    if not (skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md found at {skill_path}", file=sys.stderr)
        sys.exit(1)

    name, original_description, _content = parse_skill_md(skill_path)
    description = args.description or original_description
    project_root = find_project_root()
    candidate_content = Path(args.candidate_content_file).read_text() if args.candidate_content_file else None

    if args.verbose:
        print(f"Evaluating: {description}", file=sys.stderr)
        print(f"Eval mode: {args.eval_mode}", file=sys.stderr)

    output = run_eval(
        eval_set=eval_set,
        skill_name=name,
        description=description,
        num_workers=args.num_workers,
        timeout=args.timeout,
        project_root=project_root,
        runs_per_query=args.runs_per_query,
        trigger_threshold=args.trigger_threshold,
        eval_mode=args.eval_mode,
        skill_path=skill_path,
        candidate_content=candidate_content,
        model=args.model,
    )

    if args.verbose:
        summary = output["summary"]
        print(f"Results: {summary['passed']}/{summary['total']} passed", file=sys.stderr)
        for r in output["results"]:
            status = "PASS" if r["pass"] else "FAIL"
            rate_str = f"{r['triggers']}/{r['runs']}"
            print(f"  [{status}] rate={rate_str} expected={r['should_trigger']}: {r['query'][:70]}", file=sys.stderr)

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
