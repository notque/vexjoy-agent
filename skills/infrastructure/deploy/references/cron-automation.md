# Cron audit contract

Audit the installed entry and wrapper, not only a repository template. Toolkit-managed entries carry `# claude-cron: <tag>` and are changed only through `~/.claude/scripts/crontab-manager.py`.

Check absolute command/workdir/interpreter/log paths, atomic overlap prevention, real exit-status propagation (including `PIPESTATUS[0]` through `tee`), bounded logs, protected secret loading, and execution/budget bounds. Prefer a safe dry-run path for mutating jobs.

Use `crontab-manager.py add --dry-run` before installation and obtain explicit confirmation before repeating without `--dry-run`. Verify by tag afterward. Never pipe generated content directly to `crontab -`: a broken pipe can replace the whole crontab, while the manager creates timestamped backups in `~/.claude/crontab-backups/`.
