#!/usr/bin/env python3
# hook-version: 1.0.0
"""
SessionStart hook: Sync agents repo to ~/.claude and ~/.toolkit

Runs when Claude Code starts in the agents repo.
Syncs hooks, retro, and scripts to ~/.claude/.
Syncs /do skill to ~/.claude/skills/do/ (harness entry point).
Syncs domain skills, private voices, and agents to ~/.toolkit/ (ADR-195 Phase 2).
Cleans up stale ~/.claude/commands/ and ~/.claude/agents/ contents on each sync.
Uses additive file-by-file sync (never rmtree) so interrupted syncs
don't leave ~/.claude/hooks/ empty. Stale files are cleaned up for
repo-owned components; additive-only components (retro) preserve files
from other sources.
Retro files are merged at the entry level (### headings) rather than
overwritten, so knowledge accumulated from other repos is preserved.
L1.md is regenerated from merged L2 files at the destination.
Settings.json hooks use repo as source-of-truth (replace, not merge)
to prevent phantom hook errors when switching branches.
Unchanged files are skipped via content comparison.
"""

import filecmp
import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path


def _atomic_json_write(path: Path, data: dict) -> None:
    """Write JSON atomically via temp file + rename."""
    tmp_path = path.with_suffix(".json.tmp")
    try:
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.rename(str(tmp_path), str(path))
    except Exception:
        # Clean up temp file on failure
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


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


# NOTE: Hook sync uses repo-as-source-of-truth (replace, not merge) to prevent
# phantom hook errors when switching branches. User hooks added manually or from
# other repos will be overwritten. Non-hook keys are preserved. See ADR-104.
def sync_settings(repo_settings: dict, global_settings: dict) -> dict:
    """Sync repo settings as source-of-truth for hooks and attribution.

    The repo's hook list is authoritative: hooks that no longer exist in the
    repo settings are removed from global settings.  This prevents phantom
    hook errors when switching branches (hook registered from branch A,
    file cleaned up on branch B, but settings still reference it).

    Attribution is enforced: if the repo settings define attribution,
    it is synced. If neither repo nor global settings define attribution,
    empty attribution is set to disable Claude Code's default attribution
    (per CLAUDE.md: no "Generated with Claude Code" or "Co-Authored-By").

    Non-hook keys in global settings are preserved.
    """
    result = global_settings.copy()

    # Repo hooks are the authoritative set — replace entirely
    repo_hooks = repo_settings.get("hooks", {})
    result["hooks"] = repo_hooks

    # Ensure attribution is disabled (CLAUDE.md requirement).
    # Repo setting wins if present; otherwise ensure empty attribution exists.
    if "attribution" in repo_settings:
        result["attribution"] = repo_settings["attribution"]
    elif "attribution" not in result:
        result["attribution"] = {"commit": "", "pr": ""}

    return result


def _backup_settings_json(settings_path: Path, keep: int = 3) -> None:
    """Write a timestamped backup of settings.json before overwriting.

    Matches the CLAUDE.md backup pattern: timestamped file, capped at N,
    skipped when content is identical to the most recent backup.
    """
    import datetime

    if not settings_path.exists():
        return

    user_claude = settings_path.parent
    existing_backups = sorted(user_claude.glob("settings.json.backup.*"))

    # Skip backup when content is identical to the most recent backup
    if existing_backups:
        try:
            if filecmp.cmp(settings_path, existing_backups[-1], shallow=False):
                return
        except OSError:
            pass

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = user_claude / f"settings.json.backup.{timestamp}"
    try:
        shutil.copy2(settings_path, backup_path)
    except OSError:
        pass

    # Cap at keep most recent backups
    all_backups = sorted(user_claude.glob("settings.json.backup.*"))
    if len(all_backups) > keep:
        for old_backup in all_backups[:-keep]:
            try:
                old_backup.unlink()
            except OSError:
                pass


def _sync_dir(src: Path, dst: Path, src_relative_paths: set, use_merge: bool, errors: list) -> tuple[int, int]:
    """Copy files from src to dst, returning (count, merge_count).

    Skips unchanged files via content comparison. Merges retro markdown files
    at the ### heading level when use_merge is True.
    """
    count = 0
    merge_count = 0
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
    return count, merge_count


def _stale_cleanup(dst: Path, all_paths: set, errors: list, label: str) -> None:
    """Remove files from dst that are no longer in all_paths, then prune empty dirs."""
    if not dst.is_dir():
        return
    try:
        for item in dst.rglob("*"):
            if item.is_file():
                rel = item.relative_to(dst)
                if rel not in all_paths:
                    try:
                        item.unlink()
                    except OSError:
                        pass
        for dirpath in sorted(dst.rglob("*"), reverse=True):
            if dirpath.is_dir() and not any(dirpath.iterdir()):
                dirpath.rmdir()
    except Exception as e:
        errors.append(f"stale-cleanup-{label}: {e}")


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

    # Self-update: if the repo has a newer version of this hook, copy it to
    # the installed location and run the new version instead. This eliminates
    # the two-restart bootstrap problem during upgrades.
    try:
        repo_sync = repo_root / "hooks" / "sync-to-user-claude.py"
        installed_sync = user_claude / "hooks" / "sync-to-user-claude.py"
        if repo_sync.exists() and installed_sync.exists() and not filecmp.cmp(installed_sync, repo_sync, shallow=False):
            shutil.copy2(repo_sync, installed_sync)
            spec = importlib.util.spec_from_file_location("updated_sync", str(installed_sync))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.main()
            return
    except Exception:
        pass  # Fall through to current version on any failure

    # ~/.toolkit/ is the router-managed namespace for domain skills and agents.
    # Neither the Claude Code harness nor the Codex CLI auto-scan this path.
    # Only /do and dispatched agents read from it (ADR-195).
    user_toolkit = Path.home() / ".toolkit"

    # Non-skill/agent components sync to ~/.claude/ as before
    components = [
        ("hooks", "hooks"),
        ("retro", "retro"),  # Knowledge store for retro-knowledge-injector hook
        ("scripts", "scripts"),  # Deterministic CLI tools (learning-db.py, classify-repo.py, etc.)
    ]

    # Components that only ADD files (never remove stale ones from dst).
    # Retro entries accumulate from multiple repos.
    additive_only = {"retro"}

    # Components that need entry-level merge (not file-level overwrite).
    # Retro L2 files use ### headings as entries; merging preserves
    # knowledge accumulated from other repos in ~/.claude/retro/.
    merge_components = {"retro"}

    synced = []
    errors = []

    # Track all source-relative paths per destination for deferred stale cleanup.
    dst_all_paths: dict[str, set] = {}

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

            src_relative_paths: set = set()
            use_merge = src_name in merge_components
            count, merge_count = _sync_dir(src, dst, src_relative_paths, use_merge, errors)

            # Accumulate paths per destination for deferred stale cleanup
            if src_name not in additive_only:
                if dst_name not in dst_all_paths:
                    dst_all_paths[dst_name] = set()
                dst_all_paths[dst_name].update(src_relative_paths)

            # For merge components, regenerate L1 from merged L2 files
            if use_merge and merge_count > 0:
                regenerate_l1_at_dst(dst)
                synced.append(f"{dst_name}({count}, {merge_count} merged)")
            else:
                synced.append(f"{dst_name}({count})")
        except Exception as e:
            errors.append(f"{dst_name}: {e}")

    # Deferred stale cleanup for ~/.claude/ non-skill/agent components
    for dst_name, all_paths in dst_all_paths.items():
        _stale_cleanup(user_claude / dst_name, all_paths, errors, dst_name)

    # Remove stale ~/.claude/commands/ — commands/ directory was eliminated (ADR-195 Phase 2).
    # Agents use skills via /do; slash-command discovery is no longer via commands/.
    stale_commands_dir = user_claude / "commands"
    if stale_commands_dir.is_dir():
        try:
            shutil.rmtree(stale_commands_dir)
            synced.append("cleanup(~/.claude/commands removed)")
        except OSError as e:
            errors.append(f"cleanup-commands: {e}")

    # -------------------------------------------------------------------------
    # Skills: two-layer model (ADR-195 Phase 2)
    #
    # ~/.claude/skills/do/    — orchestration entry point (harness discovers)
    # ~/.toolkit/skills/      — all domain skills + private voices (router-managed)
    #
    # The harness auto-scans ~/.claude/skills/ for SKILL.md files. Domain skills
    # and private voices must NOT live there — they would be injected into every
    # session's context, costing ~4k tokens per turn. Only /do needs harness visibility.
    # -------------------------------------------------------------------------
    repo_skills = repo_root / "skills"
    claude_skills = user_claude / "skills"
    toolkit_skills = user_toolkit / "skills"
    do_src = repo_skills / "do"  # defined here for use in both skills and Codex sections

    if repo_skills.is_dir():
        # 1. Sync /do to ~/.claude/skills/do/ (orchestration entry point)
        do_dst = claude_skills / "do"
        if do_src.is_dir():
            try:
                do_dst.mkdir(parents=True, exist_ok=True)
                do_paths: set = set()
                count, _ = _sync_dir(do_src, do_dst, do_paths, False, errors)
                synced.append(f"skills/do({count})")
                _stale_cleanup(do_dst, do_paths, errors, "skills/do")
            except Exception as e:
                errors.append(f"skills/do: {e}")

        # 2. Sync all domain skills (everything except do/) to ~/.toolkit/skills/
        #    This includes skills like go-patterns, publish, planning, etc.
        try:
            toolkit_skills.mkdir(parents=True, exist_ok=True)
            toolkit_paths: set = set()
            toolkit_count = 0
            for skill_dir in sorted(repo_skills.iterdir()):
                if not skill_dir.is_dir():
                    continue
                if skill_dir.name == "do":
                    continue  # Already handled above
                dst_skill = toolkit_skills / skill_dir.name
                dst_skill.mkdir(parents=True, exist_ok=True)
                skill_paths: set = set()
                count, _ = _sync_dir(skill_dir, dst_skill, skill_paths, False, errors)
                # Remap relative paths to be under the skill subdirectory
                for p in skill_paths:
                    toolkit_paths.add(Path(skill_dir.name) / p)
                toolkit_count += count
            synced.append(f"~/.toolkit/skills({toolkit_count})")
            _stale_cleanup(toolkit_skills, toolkit_paths, errors, "toolkit/skills")
        except Exception as e:
            errors.append(f"toolkit/skills: {e}")

        # 3. Remove stale domain skills from ~/.claude/skills/ (keep only do/).
        #    Domain skills now live in ~/.toolkit/skills/ (ADR-195).
        #    Private voices moved to ~/.toolkit/skills/voice-* (ADR-195 Phase 2).
        try:
            if claude_skills.is_dir():
                for item in sorted(claude_skills.iterdir()):
                    if not item.is_dir():
                        continue
                    if item.name == "do":
                        continue  # Orchestration entry point — keep
                    # Domain skill or voice skill that now lives in ~/.toolkit/skills/ — remove
                    try:
                        shutil.rmtree(item)
                    except OSError:
                        pass
        except Exception as e:
            errors.append(f"stale-cleanup-claude-skills: {e}")

    # -------------------------------------------------------------------------
    # Agents: toolkit-only model (ADR-195 Phase 2)
    #
    # ~/.toolkit/agents/  — canonical location (router-managed)
    #
    # /do reads agents directly from ~/.toolkit/agents/. ~/.claude/agents/ is
    # cleaned on every sync — no symlinks, no copies. Agents are never injected
    # into the orchestrator's session context.
    # -------------------------------------------------------------------------
    repo_agents = repo_root / "agents"
    claude_agents = user_claude / "agents"
    toolkit_agents = user_toolkit / "agents"

    if repo_agents.is_dir():
        try:
            toolkit_agents.mkdir(parents=True, exist_ok=True)
            toolkit_agent_paths: set = set()
            count, _ = _sync_dir(repo_agents, toolkit_agents, toolkit_agent_paths, False, errors)
            synced.append(f"~/.toolkit/agents({count})")
        except Exception as e:
            errors.append(f"toolkit/agents: {e}")

        # Private agents: sync to ~/.toolkit/agents/ alongside public agents
        private_agents_dir = repo_root / "private-agents"
        if private_agents_dir.is_dir():
            try:
                priv_paths: set = set()
                count, _ = _sync_dir(private_agents_dir, toolkit_agents, priv_paths, False, errors)
                if count:
                    synced.append(f"~/.toolkit/agents/private({count})")
                toolkit_agent_paths.update(priv_paths)
            except Exception as e:
                errors.append(f"toolkit/agents/private: {e}")

        try:
            _stale_cleanup(toolkit_agents, toolkit_agent_paths, errors, "toolkit/agents")
        except Exception as e:
            errors.append(f"toolkit/agents/stale: {e}")

        # Clean up ~/.claude/agents/ — agents now live exclusively in ~/.toolkit/agents/.
        # Remove all symlinks, regular files, and subdirectories from ~/.claude/agents/
        # that were created by previous sync runs. The Claude Code harness no longer
        # discovers agents from ~/.claude/agents/; /do reads from ~/.toolkit/agents/ directly.
        try:
            if claude_agents.is_dir():
                removed_count = 0
                for item in list(claude_agents.iterdir()):
                    try:
                        if item.is_symlink() or item.is_file():
                            item.unlink()
                            removed_count += 1
                        elif item.is_dir():
                            shutil.rmtree(item)
                            removed_count += 1
                    except OSError:
                        pass
                if removed_count:
                    synced.append(f"cleanup(~/.claude/agents removed {removed_count} items)")
        except Exception as e:
            errors.append(f"cleanup-claude-agents: {e}")

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

            _backup_settings_json(global_settings_path)
            _atomic_json_write(Path(global_settings_path), merged)
            # Harden permissions after write (ADR-122)
            try:
                os.chmod(global_settings_path, 0o600)
            except OSError:
                pass

            hook_count = sum(len(v) for v in merged.get("hooks", {}).values())
            synced.append(f"settings({hook_count} hook events)")

            # Validate: every hook command's .py file must exist in ~/.claude/hooks/.
            # When a branch adds a hook + settings entry, then the branch is merged
            # and a new session starts on main, settings.json may reference a hook
            # file that hasn't been synced yet (stale settings from prior branch
            # session). Detect and warn about missing files.
            hooks_dir = user_claude / "hooks"
            missing_hooks = []
            for _evt, hook_list in merged.get("hooks", {}).items():
                for entry in hook_list:
                    for hook_item in entry.get("hooks", [entry]):
                        cmd = hook_item.get("command", "")
                        # Extract .py file path from command string
                        if ".claude/hooks/" in cmd:
                            # Handle both "$HOME/.claude/hooks/X.py" and quoted variants
                            py_file = cmd.split(".claude/hooks/")[-1].strip().strip('"').strip("'")
                            hook_path = hooks_dir / py_file
                            if py_file and not hook_path.exists():
                                missing_hooks.append(py_file)
            if missing_hooks:
                print(
                    f"[sync] WARNING: {len(missing_hooks)} hook(s) registered in settings.json "
                    f"but missing from ~/.claude/hooks/: {', '.join(missing_hooks)}",
                    file=sys.stderr,
                )
                # Attempt emergency copy from repo hooks/ for any missing files
                for py_file in missing_hooks:
                    repo_hook = repo_root / "hooks" / py_file
                    if repo_hook.exists():
                        target = hooks_dir / py_file
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(repo_hook, target)
                        print(f"[sync] Emergency copy: hooks/{py_file} -> {target}", file=sys.stderr)
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

            _atomic_json_write(Path(global_mcp_path), global_mcp)
            # Harden permissions after write (ADR-122)
            try:
                os.chmod(global_mcp_path, 0o600)
            except OSError:
                pass

            new_servers = [n for n in repo_servers if n not in global_servers]
            if new_servers:
                synced.append(f"mcp(+{', '.join(new_servers)})")
            else:
                synced.append(f"mcp({len(merged_servers)} servers)")
        except Exception as e:
            errors.append(f".mcp.json: {e}")

    # Sync private voices: private-voices/{name}/skill/ -> ~/.toolkit/skills/voice-{name}/
    # Private voices are gitignored — they contain personal writing patterns.
    # Each voice dir may contain: samples/, profile.json, config.json, skill/SKILL.md
    # Only the skill/ subdirectory is synced to ~/.toolkit/skills/ (ADR-195 Phase 2).
    # /do reads voice skills from ~/.toolkit/skills/ during voice routing.
    private_voices_dir = repo_root / "private-voices"
    if private_voices_dir.is_dir():
        voice_count = 0
        for voice_dir in sorted(private_voices_dir.iterdir()):
            if not voice_dir.is_dir():
                continue
            skill_src = voice_dir / "skill"
            if not skill_src.is_dir():
                continue
            # Map private-voices/{name}/skill/ -> ~/.toolkit/skills/voice-{name}/
            voice_name = voice_dir.name
            skill_dst = user_toolkit / "skills" / f"voice-{voice_name}"
            try:
                skill_dst.mkdir(parents=True, exist_ok=True)
                voice_paths: set = set()
                count, _ = _sync_dir(skill_src, skill_dst, voice_paths, False, errors)
                voice_count += 1
            except Exception as e:
                errors.append(f"voice-{voice_name}: {e}")
        if voice_count > 0:
            synced.append(f"private-voices({voice_count})")

    # -------------------------------------------------------------------------
    # Codex CLI sync (ADR-195 updated)
    #
    # Codex gets only /do (orchestration entry point).
    # Domain skills and private voices now live in ~/.toolkit/, which neither harness scans.
    # Stale domain skills and voice-* dirs are removed from ~/.codex/skills/ (keep only do/).
    # Codex agents mirror the same copy that went to ~/.toolkit/agents/.
    # -------------------------------------------------------------------------
    codex_skills_dst = Path.home() / ".codex" / "skills"

    # Sync /do to ~/.codex/skills/do/
    if do_src.is_dir():
        codex_do_dst = codex_skills_dst / "do"
        try:
            codex_do_dst.mkdir(parents=True, exist_ok=True)
            codex_do_paths: set = set()
            count, _ = _sync_dir(do_src, codex_do_dst, codex_do_paths, False, errors)
            synced.append(f".codex/skills/do({count})")
            _stale_cleanup(codex_do_dst, codex_do_paths, errors, "codex/skills/do")
        except Exception as e:
            errors.append(f"codex-skills/do: {e}")

    # Remove stale domain skills and voice-* dirs from ~/.codex/skills/ (keep only do/).
    # Private voices now live in ~/.toolkit/skills/voice-* (ADR-195 Phase 2).
    try:
        if codex_skills_dst.is_dir():
            for item in sorted(codex_skills_dst.iterdir()):
                if not item.is_dir():
                    continue
                if item.name == "do":
                    continue
                # Domain skill or stale voice dir — remove
                try:
                    shutil.rmtree(item)
                except OSError:
                    pass
    except Exception as e:
        errors.append(f"stale-cleanup-codex-skills: {e}")

    # Sync agents to ~/.codex/agents/ — Codex can Read domain expertise even
    # though it has no native subagent_type dispatch. Mirror from ~/.toolkit/agents/.
    codex_agents_dst = Path.home() / ".codex" / "agents"
    if toolkit_agents.is_dir():
        try:
            codex_agents_dst.mkdir(parents=True, exist_ok=True)
            codex_agent_paths: set = set()
            count, _ = _sync_dir(toolkit_agents, codex_agents_dst, codex_agent_paths, False, errors)
            if count:
                synced.append(f".codex/agents({count} updated)")
            elif codex_agents_dst.is_dir():
                total = sum(1 for _ in codex_agents_dst.rglob("*") if _.is_file())
                synced.append(f".codex/agents({total} current)")
            _stale_cleanup(codex_agents_dst, codex_agent_paths, errors, "codex/agents")
        except Exception as e:
            errors.append(f"codex-agents: {e}")

    # Output for hook feedback
    if synced:
        print(f"[sync] Updated ~/.claude + ~/.toolkit: {', '.join(synced)}")
    if errors:
        print(f"[sync] Errors: {', '.join(errors)}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(f"[sync-to-user-claude] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    finally:
        sys.exit(0)
