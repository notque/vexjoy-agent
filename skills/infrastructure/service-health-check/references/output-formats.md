# Output Formats

The script writes two reports per run:

- `cve-source-report-{service}-{YYYYMMDD}.json` — machine-readable.
- `cve-source-report-{service}-{YYYYMMDD}.md` — human-readable / audit-ready.

Both live in `--out-dir` (defaults to cwd). The service name is sanitized to `[A-Za-z0-9_.-]`.

## JSON schema

```json
{
  "service": "my-service",
  "generated_at": "2026-05-26T14:32:11Z",
  "summary": {
    "components": 5,
    "mapped": 5,
    "unmapped": 0,
    "monitored": 3,
    "coverage_pct": 60.0,
    "gaps": 2,
    "unreachable": 0
  },
  "components": [
    {
      "name": "postgres",
      "version": "16.2",
      "type": "container",
      "status": "mapped",
      "sources": [
        {
          "url": "https://www.postgresql.org/support/security/",
          "kind": "advisory-list",
          "priority": "primary",
          "monitored": true,
          "reachable": true
        }
      ]
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `summary.coverage_pct` | `monitored / components × 100`, one decimal. |
| `summary.gaps` | Count of components either unmapped, or mapped but with zero monitored sources. |
| `summary.unreachable` | Count of source URLs that returned a definitive HTTP failure (only with `--check-urls`). |
| `components[].status` | `"mapped"` (in registry) or `"unmapped"` (registry has no entry). |
| `components[].sources[].monitored` | `true` if `--current-sources` listed this URL. |
| `components[].sources[].reachable` | `true` / `false` / `null`; see `source-verification.md`. |

## Markdown report

Sections in order:

1. **H1 header** with the service name.
2. **Generated timestamp** (UTC, ISO-8601).
3. **Summary table** — component / mapped / unmapped / monitored / coverage / gaps / unreachable.
4. **Legend** — ✅ mapped+monitored, ⚠️ mapped not monitored, ❌ unmapped.
5. **Components table** — one row per component with status marker, name, version, type, and sources.
6. **Gaps section** — per-component primary/secondary sources to add. Only present when gaps exist.
7. **Unmapped section** — registry-extension TODO list. Only present when unmapped components exist.

## Source-cell format

Each source in the components table renders as:

```
{flag} {priority}/{kind}{reach}
```

| Token | Meaning |
|---|---|
| `flag` | `✓` if monitored, `·` if not. |
| `priority` | `primary` / `secondary`. |
| `kind` | One of the registry's allowed kinds. |
| `reach` | `[ok]`, `[DOWN]`, or `[—]`; only present when `--check-urls` was set. |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Full coverage: every mapped component has at least one monitored source, and there are no unmapped components. |
| 1 | Gaps exist (unmapped components and/or mapped components with no monitored sources). |
| 2 | At least one source URL returned a definitive HTTP failure. Only emitted when `--check-urls` is set. Implies 1 too — gaps are still reported. |
| 3 | Input error (registry/inventory missing or malformed, or empty inventory). |

CI consumers should treat 1 and 2 as actionable and 3 as a configuration bug.
