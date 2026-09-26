#!/usr/bin/env python3
"""Manage multiple Claude Code accounts via isolated CLAUDE_CONFIG_DIR directories.

Each account gets its own config directory under ~/.claude-accounts/<name>/.
The script generates shell aliases (Fish or Bash/Zsh) so the user launches
any account by typing its short alias. install.sh installs the toolkit once
into ~/.claude; each account symlinks skills/, agents/, and commands/ to it.

Usage:
    python3 scripts/manage-accounts.py add <name> [--alias <alias>]
    python3 scripts/manage-accounts.py list
    python3 scripts/manage-accounts.py check
    python3 scripts/manage-accounts.py launch <name>
    python3 scripts/manage-accounts.py link [<name>]
    python3 scripts/manage-accounts.py install-aliases [--shell fish|bash|zsh] [--dry-run]
    python3 scripts/manage-accounts.py remove <name>

Examples:
    python3 scripts/manage-accounts.py add work --alias cwork
    python3 scripts/manage-accounts.py add personal --alias cpersonal
    python3 scripts/manage-accounts.py list
    python3 scripts/manage-accounts.py check
    python3 scripts/manage-accounts.py install-aliases --shell fish
    python3 scripts/manage-accounts.py install-aliases --dry-run
    python3 scripts/manage-accounts.py launch work
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ACCOUNTS_ROOT = Path.home() / ".claude-accounts"
REGISTRY = ACCOUNTS_ROOT / "accounts.json"
DEFAULT_CONFIG = Path.home() / ".claude"
# install.sh writes these into ~/.claude; every account links to them.
SHARED_ENTRIES = ("skills", "agents", "commands")
# Flags every account launch passes to claude, before any user args.
DEFAULT_CLAUDE_ARGS = ("--dangerously-skip-permissions", '--system-prompt="."')


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------


def load_registry() -> dict[str, dict]:
    """Return the accounts registry, creating it if absent."""
    ACCOUNTS_ROOT.mkdir(parents=True, exist_ok=True)
    if not REGISTRY.exists():
        return {}
    try:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as exc:
        print(f"warning: could not read {REGISTRY}: {exc}", file=sys.stderr)
        return {}


def save_registry(accounts: dict[str, dict]) -> None:
    """Persist the registry to disk."""
    ACCOUNTS_ROOT.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(accounts, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def config_dir(name: str) -> Path:
    """Return the CLAUDE_CONFIG_DIR path for an account."""
    return ACCOUNTS_ROOT / name


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_add(args: argparse.Namespace) -> int:
    """Register a new account and create its config directory."""
    name = args.name.strip()
    if not name or "/" in name or name.startswith("."):
        print(f"error: invalid account name '{name}'", file=sys.stderr)
        return 1

    accounts = load_registry()
    if name in accounts:
        print(f"error: account '{name}' already exists", file=sys.stderr)
        return 1

    # Validate alias uniqueness
    alias = args.alias or _default_alias(accounts)
    existing_aliases = {v.get("alias") for v in accounts.values()}
    if alias in existing_aliases:
        print(f"error: alias '{alias}' is already used by another account", file=sys.stderr)
        return 1

    cfg = config_dir(name)
    cfg.mkdir(parents=True, exist_ok=True)
    cfg.chmod(0o700)

    accounts[name] = {"alias": alias, "config_dir": str(cfg)}
    save_registry(accounts)

    print(f"✓ account '{name}' added")
    print(f"  config dir : {cfg}")
    print(f"  alias      : {alias}")
    print()

    # Auto-install aliases so the alias is live immediately after add.
    _do_install_aliases(shell=None, dry_run=False)

    # The toolkit installs once into ~/.claude; the account shares it by symlink.
    _link_shared(cfg)

    print()
    print("Next step — log in:")
    print(f"  CLAUDE_CONFIG_DIR={cfg} claude")
    print("  Then run /login inside Claude Code.")
    return 0


def _link_shared(cfg: Path) -> list[str]:
    """Symlink each SHARED_ENTRIES dir in cfg to ~/.claude; returns problems.

    A missing entry or an empty real dir becomes a link. A non-empty real dir
    or a link elsewhere is left alone and reported.
    """
    problems: list[str] = []
    for entry in SHARED_ENTRIES:
        src = DEFAULT_CONFIG / entry
        dest = cfg / entry
        if dest.is_symlink():
            if Path(os.readlink(dest)) == src:
                continue
            problems.append(f"{dest} links to {os.readlink(dest)}, not {src}")
            continue
        if dest.is_dir():
            # Claude Code writes skills/synced/<account-uuid>/ per account; fold
            # such content into the shared dir when nothing there conflicts.
            _merge_into(dest, src)
            if any(dest.iterdir()):
                problems.append(f"{dest} has entries that conflict with {src}; move them aside, then rerun link")
                continue
            dest.rmdir()
        elif dest.exists():
            problems.append(f"{dest} is a file; move it aside, then rerun link")
            continue
        dest.symlink_to(src)
        print(f"✓ linked {dest} → {src}")
    for p in problems:
        print(f"⚠ {p}", file=sys.stderr)
    return problems


def _merge_into(dest: Path, src: Path) -> None:
    """Move each child of dest into src; recurse where both hold a dir; leave conflicts."""
    src.mkdir(parents=True, exist_ok=True)
    for child in list(dest.iterdir()):
        target = src / child.name
        if not os.path.lexists(target):
            child.rename(target)
        elif child.is_dir() and not child.is_symlink() and target.is_dir() and not target.is_symlink():
            _merge_into(child, target)
            if not any(child.iterdir()):
                child.rmdir()


def cmd_link(args: argparse.Namespace) -> int:
    """Symlink shared toolkit dirs from ~/.claude into one or all accounts."""
    accounts = load_registry()
    names = [args.name] if args.name else sorted(accounts)
    problems = 0
    for name in names:
        if name not in accounts:
            print(f"error: account '{name}' not found", file=sys.stderr)
            return 1
        cfg = Path(accounts[name].get("config_dir", str(config_dir(name))))
        cfg.mkdir(parents=True, exist_ok=True)
        problems += len(_link_shared(cfg))
    if problems:
        return 1
    print(f"✓ {len(names)} account(s) share {', '.join(SHARED_ENTRIES)} from {DEFAULT_CONFIG}")
    return 0


def _default_alias(accounts: dict[str, dict]) -> str:
    """Generate the next sequential alias c1, c2, … cN."""
    used = {v.get("alias", "") for v in accounts.values()}
    i = 1
    while True:
        candidate = f"c{i}"
        if candidate not in used:
            return candidate
        i += 1


def cmd_list(args: argparse.Namespace) -> int:
    """Print all registered accounts, including the default ~/.claude account."""
    accounts = load_registry()

    print(f"{'ALIAS':<12} {'NAME':<20} {'CONFIG DIR'}")
    print("-" * 76)

    # Default account is always shown first.
    default_cfg = Path.home() / ".claude"
    exists_marker = "✓" if default_cfg.exists() else "✗ missing"
    print(f"{'claude':<12} {'(default)':<20} {default_cfg}  {exists_marker}")

    if not accounts:
        print()
        print("No managed accounts yet. Add one:")
        print("  python3 scripts/manage-accounts.py add <name>")
        return 0

    for name, info in sorted(accounts.items(), key=lambda kv: kv[1].get("alias", kv[0])):
        alias = info.get("alias", "—")
        cfg = info.get("config_dir", str(config_dir(name)))
        exists = "✓" if Path(cfg).exists() else "✗ missing"
        print(f"{alias:<12} {name:<20} {cfg}  {exists}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Validate that all registered alias targets exist and have credentials."""
    accounts = load_registry()
    if not accounts:
        print("no managed accounts registered")
        return 0

    issues: list[str] = []
    for name, info in sorted(accounts.items(), key=lambda kv: kv[1].get("alias", kv[0])):
        alias = info.get("alias", f"c_{name}")
        cfg = Path(info.get("config_dir", str(config_dir(name))))
        if not cfg.exists():
            issues.append(f"  {alias} ({name}): config dir missing — {cfg}")
            continue
        # Claude Code stores auth in the system keychain (OAuth) or credentials.json (API key).
        # Use history.jsonl as a proxy: if it has content the account was successfully used.
        creds = cfg / "credentials.json"
        history = cfg / "history.jsonl"
        logged_in = creds.exists() or (history.exists() and history.stat().st_size > 0)
        if not logged_in:
            issues.append(f"  {alias} ({name}): logged out — run: CLAUDE_CONFIG_DIR={cfg} claude, then /login")
        unlinked = [e for e in SHARED_ENTRIES if not (cfg / e).is_symlink()]
        if unlinked:
            issues.append(f"  {alias} ({name}): {', '.join(unlinked)} not shared — run: manage-accounts.py link {name}")

    if issues:
        print(f"⚠ {len(issues)} issue(s) found:")
        for issue in issues:
            print(issue)
        return 1
    print(f"✓ all {len(accounts)} account(s) look healthy")
    return 0


def cmd_launch(args: argparse.Namespace) -> int:
    """Launch Claude Code for a named account."""
    accounts = load_registry()
    name = args.name
    if name not in accounts:
        # Allow launching by alias too
        alias_map = {v.get("alias"): k for k, v in accounts.items()}
        if name in alias_map:
            name = alias_map[name]
        else:
            print(f"error: account '{name}' not found", file=sys.stderr)
            print("Registered accounts:", ", ".join(sorted(accounts)) or "none")
            return 1

    cfg = Path(accounts[name].get("config_dir", str(config_dir(name))))
    cfg.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "CLAUDE_CONFIG_DIR": str(cfg)}
    extra = args.extra or []
    print(f"launching claude for account '{name}' (config: {cfg})")
    # Strip the shell quoting from DEFAULT_CLAUDE_ARGS; execvpe passes argv as-is.
    defaults = [a.replace('"', "") for a in DEFAULT_CLAUDE_ARGS]
    os.execvpe("claude", ["claude", *defaults, *extra], env)
    return 0  # unreachable; execvpe replaces the process


def cmd_remove(args: argparse.Namespace) -> int:
    """Unregister an account (config directory is preserved)."""
    accounts = load_registry()
    name = args.name
    if name not in accounts:
        print(f"error: account '{name}' not found", file=sys.stderr)
        return 1

    cfg = accounts[name].get("config_dir", str(config_dir(name)))
    del accounts[name]
    save_registry(accounts)
    print(f"✓ account '{name}' removed from registry")
    print(f"  config dir preserved: {cfg}")
    print("  delete it manually if you want to remove credentials.")
    return 0


# ---------------------------------------------------------------------------
# Alias installation
# ---------------------------------------------------------------------------

_FISH_ALIAS_HEADER = "# managed by vexjoy-agent manage-accounts.py — do not edit this block manually"
_FISH_ALIAS_FOOTER = "# end managed block"

_BASH_ALIAS_HEADER = "# managed by vexjoy-agent manage-accounts.py — do not edit this block manually"
_BASH_ALIAS_FOOTER = "# end managed block"


def _fish_alias_block(accounts: dict[str, dict]) -> str:
    lines = [_FISH_ALIAS_HEADER]
    for name, info in sorted(accounts.items(), key=lambda kv: kv[1].get("alias", kv[0])):
        alias = info.get("alias", f"c_{name}")
        cfg = info.get("config_dir", str(config_dir(name)))
        # Fish: function-based alias so CLAUDE_CONFIG_DIR is set for the subprocess
        lines.append(f"function {alias}")
        lines.append(f'    set -lx CLAUDE_CONFIG_DIR "{cfg}"')
        lines.append(f"    claude {' '.join(DEFAULT_CLAUDE_ARGS)} $argv")
        lines.append("end")
    lines.append(_FISH_ALIAS_FOOTER)
    return "\n".join(lines) + "\n"


def _bash_alias_block(accounts: dict[str, dict]) -> str:
    lines = [_BASH_ALIAS_HEADER]
    for name, info in sorted(accounts.items(), key=lambda kv: kv[1].get("alias", kv[0])):
        alias = info.get("alias", f"c_{name}")
        cfg = info.get("config_dir", str(config_dir(name)))
        lines.append(f"alias {alias}='CLAUDE_CONFIG_DIR=\"{cfg}\" claude {' '.join(DEFAULT_CLAUDE_ARGS)}'")
    lines.append(_BASH_ALIAS_FOOTER)
    return "\n".join(lines) + "\n"


def _upsert_managed_block(filepath: Path, block: str, header: str, footer: str) -> bool:
    """Replace the managed block in filepath, or append it if absent. Returns True if changed."""
    original = filepath.read_text(encoding="utf-8") if filepath.exists() else ""
    h_idx = original.find(header)
    f_idx = original.find(footer)

    if h_idx != -1 and f_idx != -1 and f_idx > h_idx:
        new_content = original[:h_idx] + block + original[f_idx + len(footer) :].lstrip("\n")
    else:
        separator = "\n\n" if original and not original.endswith("\n\n") else ("\n" if original else "")
        new_content = original + separator + block

    if new_content == original:
        return False
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(new_content, encoding="utf-8")
    return True


def _do_install_aliases(shell: str | None, dry_run: bool) -> int:
    """Core logic for installing aliases. Called by cmd_add and cmd_install_aliases."""
    accounts = load_registry()
    if not accounts:
        print("no accounts registered — add some first:")
        print("  python3 scripts/manage-accounts.py add <name>")
        return 0

    resolved_shell = shell or _detect_shell()
    if resolved_shell == "fish":
        cfg_file = Path.home() / ".config" / "fish" / "config.fish"
        block = _fish_alias_block(accounts)
        header, footer = _FISH_ALIAS_HEADER, _FISH_ALIAS_FOOTER
    elif resolved_shell in ("bash", "zsh"):
        rc = ".bashrc" if resolved_shell == "bash" else ".zshrc"
        cfg_file = Path.home() / rc
        block = _bash_alias_block(accounts)
        header, footer = _BASH_ALIAS_HEADER, _BASH_ALIAS_FOOTER
    else:
        print(f"error: unsupported shell '{resolved_shell}' — use fish, bash, or zsh", file=sys.stderr)
        return 1

    if dry_run:
        print(f"[dry-run] would write to: {cfg_file}")
        print()
        print(block)
        return 0

    changed = _upsert_managed_block(cfg_file, block, header, footer)
    if changed:
        print(f"✓ aliases written to {cfg_file}")
    else:
        print(f"✓ aliases already up to date in {cfg_file}")

    print()
    print("Aliases:")
    for name, info in sorted(accounts.items(), key=lambda kv: kv[1].get("alias", kv[0])):
        alias = info.get("alias", f"c_{name}")
        print(f"  {alias:12}  →  {name}")

    if resolved_shell == "fish":
        print()
        print("Reload: source ~/.config/fish/config.fish")
    else:
        print()
        print(f"Reload: source ~/{'.bashrc' if resolved_shell == 'bash' else '.zshrc'}")
    return 0


def cmd_install_aliases(args: argparse.Namespace) -> int:
    """Write shell aliases to the user's shell config file."""
    return _do_install_aliases(shell=args.shell, dry_run=args.dry_run)


def _detect_shell() -> str:
    """Detect the current shell from $SHELL or process name."""
    shell_env = os.environ.get("SHELL", "")
    if "fish" in shell_env:
        return "fish"
    if "zsh" in shell_env:
        return "zsh"
    if "bash" in shell_env:
        return "bash"
    # Fallback: check parent process name
    try:
        ppid = os.getppid()
        result = subprocess.run(["ps", "-p", str(ppid), "-o", "comm="], capture_output=True, text=True, timeout=3)
        name = result.stdout.strip()
        if "fish" in name:
            return "fish"
        if "zsh" in name:
            return "zsh"
        if "bash" in name:
            return "bash"
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "bash"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manage multiple Claude Code accounts via isolated CLAUDE_CONFIG_DIR directories.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Usage:")[1] if "Usage:" in __doc__ else "",
    )
    sub = parser.add_subparsers(dest="command", metavar="command")
    sub.required = True

    # add
    p_add = sub.add_parser("add", help="Register a new account and create its config directory.")
    p_add.add_argument("name", help="Account name (e.g. work, personal, max1).")
    p_add.add_argument("--alias", help="Shell alias (default: next available c1, c2, …).")
    p_add.set_defaults(func=cmd_add)

    # check
    p_check = sub.add_parser("check", help="Validate all registered accounts have config dirs and credentials.")
    p_check.set_defaults(func=cmd_check)

    # list
    p_list = sub.add_parser("list", help="List all registered accounts.")
    p_list.set_defaults(func=cmd_list)

    # launch
    p_launch = sub.add_parser("launch", help="Launch Claude Code for a named account.")
    p_launch.add_argument("name", help="Account name or alias.")
    p_launch.add_argument("extra", nargs="*", help="Extra arguments passed to claude.")
    p_launch.set_defaults(func=cmd_launch)

    # remove
    p_remove = sub.add_parser("remove", help="Unregister an account (config dir is preserved).")
    p_remove.add_argument("name", help="Account name to remove.")
    p_remove.set_defaults(func=cmd_remove)

    # link
    p_link = sub.add_parser("link", help="Symlink skills, agents, commands from ~/.claude into accounts.")
    p_link.add_argument("name", nargs="?", help="Account name (default: all accounts).")
    p_link.set_defaults(func=cmd_link)

    # install-aliases
    p_aliases = sub.add_parser("install-aliases", help="Write shell aliases for all accounts.")
    p_aliases.add_argument("--shell", choices=["fish", "bash", "zsh"], help="Shell type (auto-detected if omitted).")
    p_aliases.add_argument("--dry-run", action="store_true", help="Print what would be written; do not modify files.")
    p_aliases.set_defaults(func=cmd_install_aliases)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
