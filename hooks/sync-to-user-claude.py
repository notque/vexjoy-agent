#!/usr/bin/env python3
"""
SessionStart hook: Sync agents repo to ~/.claude

Runs when Claude Code starts in the agents repo.
Syncs agents, skills, hooks, commands, retro, and scripts to ~/.claude/.
Uses additive file-by-file sync (never rmtree) so interrupted syncs
don't leave ~/.claude/hooks/ empty. Stale files are cleaned up for
repo-owned components; additive-only components (commands, retro)
preserve files from other sources.
Retro files are merged at the entry level (### headings) rather than
overwritten, so knowledge accumulated from other repos is preserved.
L1.md is regenerated from merged L2 files at the destination.
Settings.json hooks use repo as source-of-truth (replace, not merge)
to prevent phantom hook errors when switching branches.
Unchanged files are skipped via content comparison.
CLAUDE.md backups are capped at 3; identical content skips backup.
"""

import filecmp
import json
import re
import shutil
import sys
from pathlib import Path


def _parse_retro_entries(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Parse a retro markdown file into header (everything before first ###) and entries.

    Returns (header_text, [(entry_name, entry_block), ...]).
    Each entry_block includes the ### line and all content until the next ### or EOF.
    """
    # Split on ### headings while keeping the delimiter
    parts = re.split(r"(?=^### )", text, flags=re.MULTILINE)

    header = parts[0] if parts else ""
    entries = []
    for part in parts[1:] if len(parts) > 1 else []:
        # Extract the entry name from the ### line
        match = re.match(r"### (.+?)(?:\n|$)", part)
        if match:
            name = match.group(1).strip()
            entries.append((name, part))

    return header, entries


def merge_retro_file(src_path: Path, dst_path: Path) -> None:
    """Merge a retro markdown file: union of ### entries from both src and dst.

    Entries are identified by their ### heading name. If both files have an
    entry with the same name, the source (repo) version wins. Entries that
    exist only in the destination are preserved.
    """
    src_text = src_path.read_text()

    if not dst_path.exists():
        dst_path.write_text(src_text)
        return

    dst_text = dst_path.read_text()

    src_header, src_entries = _parse_retro_entries(src_text)
    _, dst_entries = _parse_retro_entries(dst_text)

    # Build merged entry list: src entries first, then dst-only entries
    src_names = {name for name, _ in src_entries}
    merged_entries = list(src_entries)
    for name, block in dst_entries:
        if name not in src_names:
            merged_entries.append((name, block))

    # Reassemble: use src header (repo is authoritative for metadata)
    result = src_header
    for _, block in merged_entries:
        result += block

    # Ensure single trailing newline
    result = result.rstrip("\n") + "\n"
    dst_path.write_text(result)


def regenerate_l1_at_dst(dst_retro: Path) -> None:
    """Regenerate L1.md at the destination from merged L2 files.

    Mirrors the logic in feature-state.py _regenerate_l1() but runs
    at sync time against ~/.claude/retro/.
    """
    l2_dir = dst_retro / "L2"
    if not l2_dir.is_dir():
        return

    l2_files = sorted(l2_dir.glob("*.md"))
    if not l2_files:
        return

    topic_groups: dict[str, list[str]] = {}

    for l2_file in l2_files:
        try:
            content = l2_file.read_text()
        except OSError:
            continue

        tags_match = re.search(r"\*\*Tags\*\*:\s*(.+)", content)
        if tags_match:
            raw_tags = [t.strip() for t in tags_match.group(1).split(",")]
            heading_tags = [t for t in raw_tags if t not in ("go", "python", "typescript")][:3]
            if not heading_tags:
                heading_tags = raw_tags[:2]
            tag_key = " / ".join(t.replace("-", " ").title() for t in heading_tags) + " Patterns"
        else:
            tag_key = l2_file.stem.replace("-", " ").title() + " Patterns"

        sections = re.findall(r"###\s+(.+?)(?:\n\n|\n)(.+?)(?:\n\n|\n---|$)", content, re.DOTALL)
        learnings = []
        for heading, body in sections:
            first_line = body.strip().split("\n")[0][:100]
            learnings.append(f"{heading.strip()}: {first_line}")

        if not learnings:
            h2_sections = re.findall(r"##\s+(.+)", content)
            learnings = [h.strip() for h in h2_sections if not h.startswith("#")]

        if learnings:
            if tag_key not in topic_groups:
                topic_groups[tag_key] = []
            topic_groups[tag_key].extend(learnings)

    lines = ["# Accumulated Knowledge (L1 Summary)", ""]
    line_budget = 20
    lines_used = 2

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

    l1_path = dst_retro / "L1.md"
    l1_path.write_text("\n".join(lines) + "\n")


def sync_settings(repo_settings: dict, global_settings: dict) -> dict:
    """Sync repo settings as source-of-truth for hooks.

    The repo's hook list is authoritative: hooks that no longer exist in the
    repo settings are removed from global settings.  This prevents phantom
    hook errors when switching branches (hook registered from branch A,
    file cleaned up on branch B, but settings still reference it).

    Non-hook keys in global settings are preserved.
    """
    result = global_settings.copy()

    # Repo hooks are the authoritative set — replace entirely
    repo_hooks = repo_settings.get("hooks", {})
    result["hooks"] = repo_hooks

    return result


def sync_soul_document(repo_root: Path, user_claude: Path) -> tuple[str | None, str | None]:
    """
    Sync soul document (CLAUDE-soul-template.md) to ~/.claude/CLAUDE.md.

    Behavior:
    - If CLAUDE.md doesn't exist: copy template directly
    - If CLAUDE.md exists and content identical: skip (no backup churn)
    - If CLAUDE.md exists and content differs: backup, then copy template
    - Keeps only the 3 most recent backups, deletes older ones

    Returns:
        Tuple of (success_message, error_message) - one will be None
    """
    import datetime

    template_path = repo_root / "CLAUDE-soul-template.md"
    target_path = user_claude / "CLAUDE.md"

    if not template_path.exists():
        return None, None  # No template to sync, silent skip

    try:
        if target_path.exists():
            # Skip if content is identical — no backup needed
            if filecmp.cmp(template_path, target_path, shallow=False):
                _cleanup_old_backups(user_claude, keep=3)
                return "CLAUDE.md(unchanged)", None

            # Content differs — create backup then overwrite
            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = user_claude / f"CLAUDE.md.backup.{timestamp}"
            shutil.copy2(target_path, backup_path)
            shutil.copy2(template_path, target_path)
            _cleanup_old_backups(user_claude, keep=3)
            return f"CLAUDE.md(updated, backup: {backup_path.name})", None
        else:
            # No existing file, copy directly
            shutil.copy2(template_path, target_path)
            return "CLAUDE.md(created)", None

    except Exception as e:
        return None, f"CLAUDE.md: {e}"


def _cleanup_old_backups(user_claude: Path, keep: int = 3) -> None:
    """Keep only the N most recent CLAUDE.md.backup.* files, delete the rest."""
    backups = sorted(user_claude.glob("CLAUDE.md.backup.*"))
    if len(backups) <= keep:
        return
    for old_backup in backups[:-keep]:
        try:
            old_backup.unlink()
        except OSError:
            pass


def main():
    # Only run when in the agents repo
    cwd = Path.cwd()

    # Check if CWD is the agents repo (has skills/, agents/, and hooks/ dirs)
    is_agents_repo = (cwd / "skills").is_dir() and (cwd / "agents").is_dir() and (cwd / "hooks").is_dir()
    if not is_agents_repo:
        return

    # Paths - use CWD as repo root (not script location, since script may be in ~/.claude/hooks/)
    repo_root = cwd
    user_claude = Path.home() / ".claude"

    # Components to sync (directories)
    components = [
        ("agents", "agents"),
        ("skills", "skills"),
        ("hooks", "hooks"),
        ("commands", "commands"),  # Still needed for slash menu discovery
        ("retro", "retro"),  # Knowledge store for retro-knowledge-injector hook
        ("scripts", "scripts"),  # Deterministic CLI tools (learning-db.py, classify-repo.py, etc.)
    ]

    # Components that only ADD files (never remove stale ones from dst).
    # Commands can come from skills auto-generation or other sources;
    # retro entries accumulate from multiple repos.
    additive_only = {"commands", "retro"}

    # Components that need entry-level merge (not file-level overwrite).
    # Retro L2 files use ### headings as entries; merging preserves
    # knowledge accumulated from other repos in ~/.claude/retro/.
    merge_components = {"retro"}

    synced = []
    errors = []

    for src_name, dst_name in components:
        src = repo_root / src_name
        dst = user_claude / dst_name

        if not src.exists():
            continue

        try:
            # Resolve symlinks to a real directory before syncing
            if dst.is_symlink():
                dst.unlink()

            dst.mkdir(parents=True, exist_ok=True)

            # Additive sync: copy individual files, never nuke the directory.
            # This is safe even if interrupted — each file copy is independent.
            # Files with identical content are skipped to reduce I/O.
            count = 0
            merge_count = 0
            src_relative_paths = set()
            use_merge = src_name in merge_components
            for item in src.rglob("*"):
                if item.is_file():
                    rel = item.relative_to(src)
                    src_relative_paths.add(rel)
                    target = dst / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if use_merge and item.suffix == ".md" and item.name != "L1.md":
                        merge_retro_file(item, target)
                        merge_count += 1
                    elif use_merge and item.name == "L1.md":
                        pass  # Skip L1 — regenerated below
                    elif target.exists() and filecmp.cmp(item, target, shallow=False):
                        pass  # Unchanged — skip copy
                    else:
                        shutil.copy2(item, target)
                    count += 1

            # For repo-owned components, remove stale files that no longer
            # exist in the repo. Skip this for additive-only components
            # (commands, retro) where dst may have files from other sources.
            if src_name not in additive_only:
                for item in dst.rglob("*"):
                    if item.is_file():
                        rel = item.relative_to(dst)
                        if rel not in src_relative_paths:
                            item.unlink()

                # Clean up empty directories left behind
                for dirpath in sorted(dst.rglob("*"), reverse=True):
                    if dirpath.is_dir() and not any(dirpath.iterdir()):
                        dirpath.rmdir()

            # For merge components, regenerate L1 from merged L2 files
            if use_merge and merge_count > 0:
                regenerate_l1_at_dst(dst)
                synced.append(f"{dst_name}({count}, {merge_count} merged)")
            else:
                synced.append(f"{dst_name}({count})")
        except Exception as e:
            errors.append(f"{dst_name}: {e}")

    # Sync settings.json — repo hooks replace global hooks
    repo_settings_path = repo_root / ".claude" / "settings.json"
    global_settings_path = user_claude / "settings.json"

    if repo_settings_path.exists():
        try:
            with open(repo_settings_path) as f:
                repo_settings = json.load(f)

            global_settings = {}
            if global_settings_path.exists():
                try:
                    content = global_settings_path.read_text().strip()
                    if content:  # Only parse if not empty
                        global_settings = json.loads(content)
                except json.JSONDecodeError:
                    pass  # Invalid JSON, start fresh

            merged = sync_settings(repo_settings, global_settings)

            with open(global_settings_path, "w") as f:
                json.dump(merged, f, indent=2)

            hook_count = sum(len(v) for v in merged.get("hooks", {}).values())
            synced.append(f"settings({hook_count} hook events)")
        except Exception as e:
            errors.append(f"settings.json: {e}")

    # Merge .mcp.json (MCP server config)
    repo_mcp_path = repo_root / ".mcp.json"
    global_mcp_path = user_claude.parent / ".mcp.json"  # ~/.mcp.json (not inside .claude/)

    if repo_mcp_path.exists():
        try:
            with open(repo_mcp_path) as f:
                repo_mcp = json.load(f)

            global_mcp = {}
            if global_mcp_path.exists():
                try:
                    content = global_mcp_path.read_text().strip()
                    if content:
                        global_mcp = json.loads(content)
                except json.JSONDecodeError:
                    pass  # Invalid JSON, start fresh

            # Merge: add repo MCP servers without overwriting existing ones
            repo_servers = repo_mcp.get("mcpServers", {})
            global_servers = global_mcp.get("mcpServers", {})
            merged_servers = {**global_servers}  # Start with existing
            for name, config in repo_servers.items():
                if name not in merged_servers:
                    merged_servers[name] = config

            global_mcp["mcpServers"] = merged_servers

            with open(global_mcp_path, "w") as f:
                json.dump(global_mcp, f, indent=2)
                f.write("\n")

            new_servers = [n for n in repo_servers if n not in global_servers]
            if new_servers:
                synced.append(f"mcp(+{', '.join(new_servers)})")
            else:
                synced.append(f"mcp({len(merged_servers)} servers)")
        except Exception as e:
            errors.append(f".mcp.json: {e}")

    # Sync soul document (CLAUDE-soul-template.md -> CLAUDE.md)
    soul_result, soul_error = sync_soul_document(repo_root, user_claude)
    if soul_result:
        synced.append(soul_result)
    if soul_error:
        errors.append(soul_error)

    # Output for hook feedback
    if synced:
        print(f"[sync] Updated ~/.claude: {', '.join(synced)}")
    if errors:
        print(f"[sync] Errors: {', '.join(errors)}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    finally:
        sys.exit(0)
