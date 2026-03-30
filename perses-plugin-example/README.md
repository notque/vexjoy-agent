# ExamplePanel Plugin

A minimal Perses Panel plugin scaffold demonstrating the CUE schema and React component conventions.

## Plugin Details

| Field | Value |
|-------|-------|
| Type | Panel |
| Kind | `ExamplePanel` |
| Package | `@perses-dev/example-panel-plugin` |

The panel renders a configured query string and optional display unit. It is intended as a starting point — replace the component body with your visualization logic.

## Spec Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | Data query executed against the datasource |
| `unit` | string | No | Display unit appended to values (e.g. `ms`, `%`) |

## Development

### Test Schemas

Validate the CUE schema against the JSON example before building:

```bash
percli plugin test-schemas
```

All schema tests must pass before proceeding to build.

### Build

Create the distributable archive:

```bash
percli plugin build
```

The archive will contain `package.json`, `schemas/`, `__mf/`, and `mf-manifest.json`.

### Hot-Reload Dev Server

Run against a local Perses instance for live development:

```bash
percli plugin start
```

## Deploy to Perses

1. Build the plugin archive with `percli plugin build`.
2. Copy the resulting `.tar.gz` (or `.zip`) into the `plugins-archive/` directory of your Perses server installation.
3. Restart the Perses server — it will unpack and register the plugin automatically.
4. Reference the plugin in a dashboard panel definition using `kind: "ExamplePanel"`.

## Example Dashboard Panel Definition

```yaml
kind: Panel
metadata:
  name: my-example-panel
spec:
  display:
    name: My Example Panel
  plugin:
    kind: ExamplePanel
    spec:
      query: 'up{job="prometheus"}'
      unit: short
```
