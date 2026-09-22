# Scripts

Utility scripts for the VexJoy Agent.

## Index Generators

`generate-skill-index.py` and `generate-agent-index.py` walk `skills/` and
`agents/` and produce `INDEX.json` files consumed by the `/do` router.

By default the generators skip symlinked directories, so the tracked index
files reflect only directly-committed content.

### Local development workflow

Indexes that include private overlay skills are written only to the installed
runtime (`~/.claude/vexjoy/index/`) by the installer engine, never to the repo:

```bash
PYTHONPATH=scripts python3 -m vexinstall sync --index-only
```

The router (`scripts/routing-manifest.py`) prefers the local file when present,
so local runs see all entries while the tracked index stays public. The
`*.local.json` files are gitignored and never committed.
