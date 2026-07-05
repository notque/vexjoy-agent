# Registry Schema

`tech-source-registry.json` is the canonical mapping from technology to authoritative
CVE/security feeds. Edits are additive: new entries grow coverage without breaking
existing ones.

## Top-level shape

```json
{
  "$schema_version": "1.0",
  "description": "...",
  "kinds": [...],
  "priorities": [...],
  "technologies": [ ... ]
}
```

| Field | Type | Purpose |
|---|---|---|
| `$schema_version` | string | Bump on breaking shape change. |
| `kinds` | string[] | Allowed values for each source's `kind`. |
| `priorities` | string[] | Allowed values for each source's `priority`. |
| `technologies` | object[] | One entry per technology. |

## Technology entry

```json
{
  "name": "postgres",
  "aliases": ["postgresql", "pg"],
  "type": "container",
  "sources": [
    {"url": "https://www.postgresql.org/support/security/", "kind": "advisory-list", "priority": "primary"}
  ]
}
```

| Field | Required | Description |
|---|---|---|
| `name` | yes | Canonical name. Lowercase, no spaces. Used as primary lookup key. |
| `aliases` | yes (may be empty) | Alternate names users put in inventories. Lowercased on load. |
| `type` | yes | One of `runtime`, `base-image`, `container`, `library`. Free-form additions allowed. |
| `sources` | yes | One or more authoritative feeds. |

## Source entry

| Field | Allowed values | Notes |
|---|---|---|
| `url` | full https URL | Stable feed URL. Avoid links that 30x to login pages. |
| `kind` | `advisory-list`, `github-security`, `mailing-list`, `distro-tracker`, `vendor-page`, `mitre` | Drives reader expectations. |
| `priority` | `primary`, `secondary` | At least one `primary` per technology. Secondary feeds add depth. |

## Adding a new technology

1. Pick a canonical `name` (lowercase). Search the registry first to avoid duplicates.
2. List likely user-typed aliases.
3. Pick `type` from the existing set when possible.
4. Add 1–3 sources. Lead with the vendor's own advisory page or GHSA when present.
5. Re-run the script against a sample inventory to confirm the entry resolves.

## Adding a new `kind`

Edit the top-level `kinds` array first, then use it in source entries. Keep the set
small; `kind` is for filtering and explanation, not categorization theatre.

## Versioning

The registry is additive. Breaking changes (renaming `kinds`, removing entries with
existing usage) bump `$schema_version`. The script reads the registry permissively;
unknown fields are ignored.
