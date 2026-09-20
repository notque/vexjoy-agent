# Toolkit install and health contract

Run and show the raw deterministic output:

```bash
python3 ~/.claude/scripts/install-doctor.py check
python3 ~/.claude/scripts/toolkit-health.py --json
```

Fall back to repository `scripts/` paths when not installed. `toolkit-health.py` exits 1 when `has_warnings` is true; report its `flags` as advisory WARNs, not installation failure.

| Finding | Maintained repair path |
|---|---|
| Missing installation/hooks/components | `./install.sh --dry-run`, then approved `./install.sh --symlink` |
| Canonical Codex skill drift | `./install.sh --sync` |
| Broken symlinks | approved `./install.sh --symlink --force` |
| Missing Python dependencies | approved `pip install -r requirements.txt` from repo |

Installation changes `~/.claude`; show the repair and obtain approval before applying it. Re-run the check afterward. For inventory, run `install-doctor.py inventory` and `mcp-registry.py list`; use live output rather than hardcoded counts or synthesized MCP status.
