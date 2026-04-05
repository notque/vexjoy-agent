<!-- scope: Helm chart authoring patterns, template gotchas, values design, Helm 3.x features -->
<!-- versions: Helm 3.0+ (OCI registry: Helm 3.8+) -->
<!-- date: 2026-04-05 -->

# Helm Chart Patterns Reference

## Overview

Covers template whitespace control, values file design, Helm 3.x features (library charts, post-renderer, OCI registries), dry-run validation workflow, and error-fix mappings for common `helm install` failures. Load this file when authoring charts, debugging installs, or reviewing chart structure.

---

## Template Pattern Table

| Pattern | When to use | Key directive |
|---|---|---|
| `{{ }}` | Output with surrounding whitespace preserved | Default; use in most inline values |
| `{{- }}` | Strip whitespace before the tag | Prevent blank lines before blocks |
| `{{ -}}` | Strip whitespace after the tag | Prevent blank lines after blocks |
| `{{- -}}` | Strip both sides | Use around `if`/`range`/`define` blocks |
| `toYaml \| nindent N` | Embed a values subtree as YAML at indent N | Required for `resources`, `affinity`, `tolerations` |
| `required "msg" .Values.x` | Fail fast if a critical value is absent | Use for values with no sane default |
| `default "val" .Values.x` | Provide fallback for optional values | Use everywhere a missing value would produce invalid YAML |

---

## Correct Template Patterns

### Whitespace control with `{{- -}}`

Without control, each `if` block adds blank lines to rendered output, breaking YAML validation:

```yaml
# BAD — produces extra blank lines
{{ if .Values.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
{{ end }}

# GOOD — clean output
{{- if .Values.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
{{- end }}
```

### `toYaml | nindent` for nested structures

```yaml
# In templates/deployment.yaml
containers:
  - name: {{ .Chart.Name }}
    image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
    resources:
      {{- toYaml .Values.resources | nindent 12 }}
    {{- with .Values.nodeSelector }}
    nodeSelector:
      {{- toYaml . | nindent 8 }}
    {{- end }}
    {{- with .Values.affinity }}
    affinity:
      {{- toYaml . | nindent 8 }}
    {{- end }}
```

### `required` for critical values

```yaml
# Fails install immediately with a clear message if image.repository is unset
image:
  repository: {{ required "image.repository is required" .Values.image.repository }}
  tag: {{ default "latest" .Values.image.tag }}
```

### Release.Namespace for namespace references

```yaml
# BAD — hardcoded namespace breaks multi-tenant installs
namespace: production

# GOOD — use the release namespace
namespace: {{ .Release.Namespace }}
```

---

## Values File Design

### Correct: flat, overridable structure

```yaml
# values.yaml — prefer flat keys with clear defaults
replicaCount: 1

image:
  repository: myapp
  tag: ""           # intentionally empty; set at install time
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 80

resources:
  limits:
    memory: 256Mi
  requests:
    cpu: 100m
    memory: 128Mi
```

### Anti-pattern: deeply nested values

Deeply nested values require verbose `--set` overrides and are easy to mistype:

```yaml
# BAD — requires: --set app.config.server.http.port=9090
app:
  config:
    server:
      http:
        port: 8080
        timeout: 30s

# GOOD — one level of grouping max for overridable keys
server:
  port: 8080
  timeout: 30s
```

---

## Helm 3.x Features

### Library charts (Helm 3.0+)

Library charts provide shared template helpers with `type: library` in `Chart.yaml`. They cannot be installed directly.

```yaml
# Chart.yaml for a library chart
apiVersion: v2
name: mycompany-common
type: library
version: 1.2.0
```

```yaml
# Chart.yaml for a chart consuming the library
dependencies:
  - name: mycompany-common
    version: "~1.2.0"
    repository: "oci://registry.example.com/charts"
```

Use `define` in the library and `include` in consumers:

```yaml
# In library: templates/_labels.tpl
{{- define "mycompany-common.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}

# In consumer template
metadata:
  labels:
    {{- include "mycompany-common.labels" . | nindent 4 }}
```

### Post-renderer (Helm 3.1+)

Post-renderers allow patching rendered manifests without modifying the chart. Useful for injecting Kustomize patches or company-wide annotations:

```bash
helm install myapp ./chart --post-renderer ./scripts/kustomize-wrapper.sh
```

```bash
# kustomize-wrapper.sh
#!/bin/bash
cat > /tmp/helm-output.yaml
kustomize build /tmp/overlay >> /tmp/helm-output.yaml
cat /tmp/helm-output.yaml
```

### OCI registry support (Helm 3.8+)

```bash
# Login
helm registry login registry.example.com --username myuser

# Push chart to OCI registry
helm push mychart-1.0.0.tgz oci://registry.example.com/charts

# Install directly from OCI
helm install myapp oci://registry.example.com/charts/mychart --version 1.0.0

# Pull without install
helm pull oci://registry.example.com/charts/mychart --version 1.0.0
```

> **Version note:** OCI support was experimental in Helm 3.0–3.7. It became stable (GA) in Helm 3.8. Prior to 3.8, the `HELM_EXPERIMENTAL_OCI=1` environment variable was required.

---

## Validation Workflow

### Lint before templating

```bash
# Strict lint — fails on warnings as well as errors
helm lint ./mychart --strict

# Lint with custom values
helm lint ./mychart --strict -f values-prod.yaml
```

### Server-side dry run catches missing CRDs and RBAC

```bash
# Template and dry-run in one pipeline — catches schema errors and cluster policy violations
helm template myapp ./mychart -f values-prod.yaml | \
  kubectl apply --dry-run=server -f -

# For upgrade validation
helm template myapp ./mychart --is-upgrade -f values-prod.yaml | \
  kubectl apply --dry-run=server -f -
```

### Diff before upgrade (requires helm-diff plugin)

```bash
helm diff upgrade myapp ./mychart -f values-prod.yaml
```

---

## Error-Fix Mappings

| Error | Cause | Fix |
|---|---|---|
| `Error: rendered manifests contain a resource that already exists` | Resource exists outside Helm or from a previous failed install | Run `helm install` with `--force` or adopt with `kubectl annotate` + `kubectl label` to add Helm annotations |
| `Error: INSTALLATION FAILED: cannot re-use a name that is still in use` | Release name already deployed | Use `helm upgrade --install` instead of `helm install` |
| `Error: chart requires kubeVersion: >=1.24.0` | Cluster version too old | Upgrade cluster or pin older chart version |
| `Error: values don't meet the specifications of the schema` | `values.schema.json` validation failure | Fix the values file or update the schema; run `helm lint` to see field details |
| `Error: execution error at template ... required value ... is required` | `required` call hit a nil value | Supply the missing value via `-f values.yaml` or `--set key=value` |
| `Error: unable to build kubernetes objects from release manifest: error validating data` | API version removed or CRD missing | Update `apiVersion` in template or install the CRD first |
| `Error: post-renderer failed` | Post-renderer script error or non-zero exit | Check script is executable (`chmod +x`), test independently |
| `context deadline exceeded` during install/upgrade | Hooks or jobs taking too long | Increase `--timeout` (default 5m) or debug the failing hook with `kubectl logs` |

---

## Anti-Pattern Catalog

### Anti-pattern: hardcoding namespace in templates

Hardcoded namespaces break multi-environment installs and multi-tenant patterns.

**Detection:**

```bash
grep -r 'namespace:' ./templates/ | grep -v 'Release.Namespace' | grep -v '{{-'
```

**Fix:** Replace all hardcoded namespace strings with `{{ .Release.Namespace }}`.

---

### Anti-pattern: missing `default` on optional values

A missing value produces `<nil>` in the rendered YAML or crashes the template engine.

**Detection:**

```bash
# Find .Values references with no default or required guard
grep -r '\.Values\.' ./templates/ | grep -v 'default\|required\|with\|if'
```

**Fix:** Wrap every optional value reference:

```yaml
# BAD
replicas: {{ .Values.replicaCount }}

# GOOD
replicas: {{ default 1 .Values.replicaCount }}
```

---

### Anti-pattern: `helm install` instead of `helm upgrade --install` in CI

Pure `helm install` fails if the release already exists, breaking idempotent pipelines.

**Fix:**

```bash
# Idempotent: installs on first run, upgrades on subsequent runs
helm upgrade --install myapp ./mychart \
  --namespace myapp \
  --create-namespace \
  -f values-prod.yaml \
  --atomic \
  --timeout 5m
```
