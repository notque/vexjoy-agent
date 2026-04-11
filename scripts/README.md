# Scripts

Utility scripts for the Claude Code Toolkit.

## Index Generators

`generate-skill-index.py` and `generate-agent-index.py` walk `skills/` and
`agents/` and produce `INDEX.json` files consumed by the `/do` router.

By default the generators skip symlinked directories, so the tracked index
files reflect only directly-committed content.

### Local development workflow

To index symlinked entries for local workflows, use `--include-private` with
a separate output target:

```bash
python3 scripts/generate-skill-index.py --include-private --output skills/INDEX.local.json
python3 scripts/generate-agent-index.py --include-private --output agents/INDEX.local.json
```

The router (`scripts/routing-manifest.py`) prefers the local file when present,
so local runs see all entries while the tracked index stays public. The
`*.local.json` files are gitignored and never committed.
