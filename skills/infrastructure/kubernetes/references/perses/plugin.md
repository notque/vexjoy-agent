# Perses Plugin Development Reference

> **Scope**: Plugin scaffolding, CUE schema authoring, React component patterns, archive packaging, and percli plugin commands. Does not cover dashboard consumption of plugins.
> **Version range**: Perses v0.45+ (Module Federation plugin architecture)
> **Generated**: 2026-05-09 — verify against https://github.com/perses/perses/tree/main/docs/plugins

---

## Overview

Perses plugins are independently deployable modules that extend the platform with new panel types, datasources, query types, or variable resolvers. Each plugin has three layers: a CUE schema (defines the spec shape), a Go backend (optional — only for datasource/query plugins), and a React/TypeScript frontend component. The most common failure mode is a mismatch between the CUE schema field names and the TypeScript prop names — the backend validates schema but the frontend silently ignores unknown fields.

---

## Pattern Table

| Plugin Type | Has Backend | Frontend Component | CUE Schema Required |
|------------|-------------|-------------------|---------------------|
| Panel | No | Yes — renders data | Yes |
| Datasource | Yes — handles HTTP proxying | Yes — editor UI | Yes |
| Query | Yes — transforms raw data | Yes — query editor | Yes |
| Variable | Yes (optional) | Yes — variable editor | Yes |
| Explore | No | Yes — explore view | Yes |

---

## Plugin Scaffolding: percli

### Generate a new plugin

```bash
# Scaffold a panel plugin
percli plugin generate --type panel --name my-chart --output ./plugins/my-chart

# Scaffold a datasource plugin
percli plugin generate --type datasource --name my-datasource --output ./plugins/my-datasource

# Build plugin archive for distribution
percli plugin build --dir ./plugins/my-chart --output ./dist/my-chart.tar.gz
```

### Plugin directory structure (panel example)

```
plugins/my-chart/
├── plugin.json          # Plugin manifest — name, version, type
├── cue/
│   └── schemas/
│       └── my-chart.cue # CUE schema for panel spec
├── src/
│   ├── index.tsx        # Plugin entry point — exports PanelPlugin
│   ├── MyChart.tsx      # React component
│   └── types.ts         # TypeScript types matching CUE schema
├── package.json
└── webpack.config.js    # Module Federation config
```

---

## CUE Schema Authoring

### Minimal panel spec schema

```cue
// cue/schemas/my-chart.cue
package schemas

// MyChartSpec defines the configuration for the MyChart panel.
#MyChartSpec: {
    // query is required — references a query variable or inline query
    query: string

    // thresholds are optional visual thresholds
    thresholds?: [...{
        value: number
        color: string
    }]

    // legend controls display; defaults to true
    showLegend?: bool | *true
}
```

**Why**: Field names in CUE must exactly match the JSON keys sent by the frontend. A field named `showLegend` in CUE but `show_legend` in TypeScript will validate but never populate — the JSON key mismatch is silent.

---

### CUE schema validation

```bash
# Validate a dashboard JSON against Perses CUE schemas
cue vet -d '#Dashboard' ./schemas/ dashboard.json

# Validate a plugin spec specifically
cue vet -d '#MyChartSpec' ./plugins/my-chart/cue/schemas/ spec.json

# Export CUE schema as JSON Schema for editor tooling
cue export --out json ./plugins/my-chart/cue/schemas/
```

---

## React/TypeScript Frontend Patterns

### Plugin entry point (index.tsx)

```tsx
import { PanelPlugin } from '@perses-dev/plugin-system';
import { MyChart } from './MyChart';
import { MyChartEditor } from './MyChartEditor';
import type { MyChartSpec } from './types';

export const MyChartPanel: PanelPlugin<MyChartSpec> = {
    PanelComponent: MyChart,
    spec: {
        // Default spec used when panel is first added
        initSpec: (): MyChartSpec => ({
            query: '',
            showLegend: true,
        }),
    },
    editor: {
        EditorComponent: MyChartEditor,
    },
};
```

**Why**: The `initSpec` function must return a valid default that matches the CUE schema. A missing required field in `initSpec` causes the panel editor to open with a validation error before the user touches anything.

---

### Accessing query data in a panel component

```tsx
import { useDataQueries } from '@perses-dev/plugin-system';
import type { TimeSeriesData } from '@perses-dev/core';

export function MyChart({ spec }: PanelProps<MyChartSpec>) {
    const { queryResults, isFetching, error } = useDataQueries('TimeSeriesQuery');

    if (isFetching) return <LoadingOverlay />;
    if (error) return <ErrorAlert error={error} />;

    const data = queryResults[0]?.data as TimeSeriesData | undefined;
    if (!data) return <NoDataOverlay />;

    return <canvas>{/* render data.series */}</canvas>;
}
```

**Why**: Always handle all three states (`isFetching`, `error`, `!data`). A panel that only handles the happy path shows a blank panel during loading and crashes on query errors, degrading the whole dashboard view.

---

### Plugin manifest (plugin.json)

```json
{
    "name": "my-chart",
    "displayName": "My Chart",
    "version": "0.1.0",
    "pluginType": "Panel",
    "components": [
        {
            "kind": "MyChart",
            "display": {
                "name": "My Chart",
                "description": "A custom chart panel"
            }
        }
    ]
}
```

**Why**: The `kind` field in `plugin.json` must match the `kind` string used in dashboard JSON panel specs. A mismatch causes the panel to render as "Unknown Panel Type" with no useful error.

---

## Pattern Catalog: Detection and Fixes

### CUE/TypeScript field name mismatch

**Detection**:
```bash
# Extract CUE field names
grep -rn '^\s*\w\+?:' --include="*.cue" | sed 's/:.*//' | tr -d ' '

# Compare against TypeScript interface fields
grep -rn '^\s*\w\+\?:' --include="*.ts" | sed 's/:.*//' | tr -d ' '
```

**Signal**:
```cue
// CUE schema:
#Spec: { showLegend?: bool }
```
```typescript
// TypeScript type:
interface Spec { show_legend?: boolean }  // snake_case mismatch
```

**Why it matters**: The Perses backend validates the CUE schema against the stored JSON. The frontend reads from the same JSON. If the TypeScript uses `show_legend` but CUE expects `showLegend`, the frontend sends `show_legend` in JSON, which fails CUE validation. The panel saves but won't load.

**Preferred action**: Use camelCase in both CUE and TypeScript. Run `cue vet` against real panel JSON in tests.

---

### Missing `initSpec` required fields

**Detection**:
```bash
grep -rn 'initSpec' --include="*.tsx" --include="*.ts" -A 5
# Then check CUE for required (non-optional) fields
grep -rn '^\s*\w\+:' --include="*.cue" | grep -v '?'
```

**Signal**:
```typescript
initSpec: (): MyChartSpec => ({
    // Missing required 'query' field defined as non-optional in CUE
    showLegend: true,
}),
```

**Why it matters**: When a user adds the panel to a dashboard, Perses immediately validates the initSpec against the CUE schema. A missing required field causes a validation error on first render before any user interaction.

**Preferred action**: Every non-optional field in the CUE schema must have a default in `initSpec`. Add integration test that validates `initSpec()` output against CUE schema.

---

### Webpack Module Federation missing shared dependencies

**Detection**:
```bash
grep -rn 'shared:' --include="webpack.config.js" | grep -v 'react\|@perses-dev'
```

**Signal**:
```javascript
// webpack.config.js
new ModuleFederationPlugin({
    shared: {
        react: { singleton: true },
        // Missing '@perses-dev/plugin-system' as shared singleton
    }
})
```

**Why it matters**: If `@perses-dev/plugin-system` is not declared as a shared singleton, the plugin bundles its own copy. Two versions of the plugin system running simultaneously causes `useDataQueries` to silently return empty results because it's reading from a different React context instance.

**Preferred action**:
```javascript
shared: {
    react: { singleton: true, requiredVersion: deps.react },
    'react-dom': { singleton: true },
    '@perses-dev/plugin-system': { singleton: true },
    '@perses-dev/core': { singleton: true },
}
```

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|-------|------------|-----|
| Panel renders as "Unknown Panel Type" | `kind` in `plugin.json` doesn't match `kind` in dashboard spec | Align `kind` across `plugin.json`, CUE schema, and TypeScript `PanelPlugin` export |
| `cue vet` fails on panel spec | CUE field names don't match JSON keys from frontend | Use camelCase consistently in both CUE and TypeScript |
| `useDataQueries` always returns empty | `@perses-dev/plugin-system` not shared as singleton in Webpack config | Add `singleton: true` to shared config |
| Panel editor opens with validation error | `initSpec()` returns object missing required CUE field | Add all non-optional CUE fields to `initSpec()` return value |
| `percli plugin build` fails | `plugin.json` missing required fields or `src/index.tsx` not found | Verify directory structure matches scaffold output |
| Plugin not visible in panel picker | Plugin archive not loaded in Perses server config | Add plugin path to `plugins` array in `perses.yaml` server config |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| `v0.45` | Module Federation replaced legacy plugin loading | Plugins must export via `index.tsx` with `PanelPlugin` type |
| `v0.44` | `@perses-dev/plugin-system` package split from `@perses-dev/core` | Update imports from `@perses-dev/core` to `@perses-dev/plugin-system` |
| `v0.43` | CUE schemas moved from `cue/schemas/` to `schemas/` in archive | Update `percli plugin build` path configuration |
| `v0.40` | `PanelPlugin.spec.initSpec` changed from object to function | Convert `initSpec: { ... }` to `initSpec: () => ({ ... })` |

---

## Detection Commands Reference

```bash
# CUE required fields (non-optional — must be in initSpec)
grep -rn '^\s*\w\+:' --include="*.cue" | grep -v '?' | grep -v '//'

# Webpack shared singleton check
grep -rn 'singleton' --include="webpack.config.js"

# Plugin manifest kind fields
grep -rn '"kind"' --include="plugin.json"

# TypeScript type vs CUE schema field comparison
diff <(grep -h '^\s*\w' plugins/*/src/types.ts | tr -d ' ?: ') \
     <(grep -h '^\s*\w' plugins/*/cue/schemas/*.cue | tr -d ' ?:')
```

---

## See Also

- `dashboard.md` — Consuming panel plugins in dashboards
- `core.md` — Perses React/TypeScript frontend architecture and build system
