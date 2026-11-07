# Perses Operator Reference

> **Scope**: Kubernetes CRDs (v1alpha2), Helm chart deployment, RBAC, cert-manager TLS, monitoring, and multi-instance management. Does not cover dashboard content or plugin development.
> **Version range**: Perses Operator v0.4+ (CRD v1alpha2); Helm chart `perses-dev/perses`
> **Generated**: 2026-05-09 — verify against https://github.com/perses/perses-operator

---

## Overview

The Perses Operator manages Perses server instances and their associated resources (dashboards, datasources, variables) as Kubernetes CRDs. The operator reconciles `PersesDashboard`, `PersesProject`, `PersesGlobalDatasource`, and `PersesGlobalVariable` objects against the Perses API. The most common failure mode is deploying a `PersesDashboard` before the `PersesProject` it references exists — the operator queues retries silently.

---

## Pattern Table

| CRD Kind | Scope | Purpose | Requires |
|----------|-------|---------|---------|
| `Perses` | Namespaced | Manages a Perses server instance | cert-manager (if TLS) |
| `PersesProject` | Namespaced | Creates a project in the Perses API | `Perses` instance |
| `PersesDashboard` | Namespaced | Syncs a dashboard to a project | `PersesProject` |
| `PersesGlobalDatasource` | Namespaced | Registers a global datasource | `Perses` instance |
| `PersesGlobalVariable` | Namespaced | Registers a global variable | `Perses` instance |
| `PersesDatasource` | Namespaced | Project-scoped datasource | `PersesProject` |

---

## CRD Examples

### Perses instance (server deployment)

```yaml
apiVersion: perses.dev/v1alpha2
kind: Perses
metadata:
  name: perses
  namespace: monitoring
spec:
  # Use StatefulSet when using filesystem storage (default)
  # Use Deployment when using database/etcd storage
  containerPort: 8080
  config:
    database:
      # file-based storage — use PVC for persistence
      file:
        folder: /etc/perses/storage
        extension: json
  security:
    # Enable auth — requires OIDC or native user config
    enableAuth: false
  # TLS via cert-manager
  # tls:
  #   enabled: true
  #   caSecretName: perses-ca
```

**Why**: `file` storage requires a PVC; without one, pod restarts lose all dashboards. For production use either a PVC or configure etcd.

---

### PersesProject

```yaml
apiVersion: perses.dev/v1alpha2
kind: PersesProject
metadata:
  name: my-team
  namespace: monitoring
spec:
  # instanceRef points to the Perses CR in the same namespace
  instanceRef:
    name: perses
```

---

### PersesDashboard

```yaml
apiVersion: perses.dev/v1alpha2
kind: PersesDashboard
metadata:
  name: cluster-overview
  namespace: monitoring
spec:
  instanceRef:
    name: perses
  # project must match an existing PersesProject .metadata.name
  project: my-team
  # dashboard is the full Perses dashboard spec (same as percli export output)
  dashboard:
    display:
      name: "Cluster Overview"
    duration: "1h"
    refreshInterval: "30s"
    variables: []
    panels: {}
    layouts: []
```

**Why**: `spec.project` is the Perses project name (from `PersesProject.metadata.name`), not the Kubernetes namespace. Confusing these is the most common misconfiguration.

---

### PersesGlobalDatasource

```yaml
apiVersion: perses.dev/v1alpha2
kind: PersesGlobalDatasource
metadata:
  name: prometheus
  namespace: monitoring
spec:
  instanceRef:
    name: perses
  datasource:
    display:
      name: "Prometheus"
    default: true
    plugin:
      kind: PrometheusDatasource
      spec:
        # directUrl proxies through the Perses backend
        directUrl: "http://prometheus.monitoring.svc:9090"
```

---

## Helm Chart Deployment

### Add the Perses Helm repo

```bash
helm repo add perses-dev https://perses-dev.github.io/helm-charts
helm repo update
helm search repo perses-dev/perses --versions | head -5
```

### Minimal values.yaml

```yaml
# values.yaml
perses:
  config:
    database:
      file:
        folder: /etc/perses/storage
        extension: json
  persistence:
    enabled: true
    size: 5Gi

# Expose via Ingress
ingress:
  enabled: true
  className: nginx
  hosts:
    - host: perses.example.com
      paths:
        - path: /
          pathType: Prefix

# ServiceMonitor for Prometheus scraping
serviceMonitor:
  enabled: true
  interval: 30s
```

```bash
helm upgrade --install perses perses-dev/perses \
  --namespace monitoring \
  --create-namespace \
  --values values.yaml
```

---

### Operator installation

```bash
# Install the CRDs and operator
helm upgrade --install perses-operator perses-dev/perses-operator \
  --namespace perses-operator \
  --create-namespace

# Verify operator is running
kubectl get pods -n perses-operator
kubectl get crds | grep perses.dev
```

---

## Pattern Catalog: Detection and Fixes

### PersesDashboard deployed before PersesProject

**Detection**:
```bash
kubectl get persesdashboard -A -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name}: project={.spec.project}{"\n"}{end}'
kubectl get persesproject -A -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name}{"\n"}{end}'
# Compare: every .spec.project in dashboards must have a matching PersesProject .metadata.name
```

**Signal**:
```
kubectl get persesdashboard cluster-overview -n monitoring
# STATUS: Pending (retrying)
```

**Why it matters**: The operator queues the dashboard sync for retry but doesn't surface a clear error. The dashboard never appears in Perses UI and the operator log shows `project "my-team" not found` at debug level only.

**Preferred action**: Apply `PersesProject` in the same manifest before `PersesDashboard`. Use Helm hooks or Argo CD sync waves to enforce ordering.

---

### Using `Deployment` with file-based storage

**Detection**:
```bash
kubectl get perses -A -o jsonpath='{range .items[*]}{.metadata.name}: {.spec.config.database}{"\n"}{end}'
kubectl get perses -A -o yaml | grep -A3 'database:' | grep -v StatefulSet
```

**Signal**:
```yaml
spec:
  config:
    database:
      file:
        folder: /etc/perses/storage
# But workload is a Deployment, not StatefulSet — no stable pod identity/PVC
```

**Why it matters**: Deployments may run multiple replicas or reschedule pods, causing multiple instances to write to the same file-based storage without locking. This corrupts dashboard JSON files silently.

**Preferred action**: Use `StatefulSet` with file-based storage (operator default). Set `replicas: 1` for file storage. For HA, switch to etcd or database storage.

---

### Missing RBAC for operator to manage CRDs

**Detection**:
```bash
kubectl auth can-i list persesdashboards --as=system:serviceaccount:perses-operator:perses-operator -A
kubectl get clusterrolebinding | grep perses-operator
```

**Signal**:
```
Error from server (Forbidden): persesdashboards.perses.dev is forbidden:
User "system:serviceaccount:perses-operator:perses-operator" cannot list resource
```

**Why it matters**: If the operator's ServiceAccount lacks permissions to list/watch/update its own CRDs, it silently stops reconciling. No error surfaces to the user's dashboard objects.

**Preferred action**: Reinstall the operator Helm chart — RBAC is managed by the chart. If using custom RBAC, ensure `ClusterRole` includes verbs `get,list,watch,create,update,patch,delete` on all `perses.dev` API groups.

---

### TLS cert-manager not installed before Perses TLS enabled

**Detection**:
```bash
kubectl get crds | grep cert-manager.io
kubectl get issuer,clusterissuer -A 2>/dev/null | head -5
```

**Signal**:
```yaml
spec:
  tls:
    enabled: true
    caSecretName: perses-ca
# cert-manager CRDs not present
```

**Why it matters**: Perses with TLS enabled requires cert-manager to issue certificates. Without cert-manager, the Perses pod stays in `Init:0/1` indefinitely with no clear error message in pod events.

**Preferred action**:
```bash
# Install cert-manager first
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml
kubectl wait --for=condition=Ready pod -l app=cert-manager -n cert-manager --timeout=120s
# Then install Perses with TLS
```

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|-------|------------|-----|
| `project "X" not found` in operator logs | `PersesDashboard.spec.project` references non-existent `PersesProject` | Apply `PersesProject` first; use sync waves in GitOps |
| Pod stuck in `Init:0/1` | TLS enabled but cert-manager not installed | Install cert-manager before deploying Perses with TLS |
| Operator not reconciling CRDs | ServiceAccount lacks RBAC for `perses.dev` API group | Reinstall operator Helm chart or fix ClusterRole |
| Dashboards lost after pod restart | File storage without PVC | Add `persistence.enabled: true` in Helm values |
| `unknown field "X"` in CRD status | Deploying v1alpha1 manifest to v1alpha2 CRD | Update `apiVersion: perses.dev/v1alpha2` in all CRD manifests |
| `PersesDashboard` stuck in `Pending` | Perses API unreachable from operator pod | Check NetworkPolicy; operator needs egress to Perses service on port 8080 |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| `v0.4` (operator) | CRD `v1alpha2` became default | Change all `apiVersion: perses.dev/v1alpha1` to `v1alpha2` |
| `v0.3` (operator) | `PersesGlobalDatasource` added | Global datasources now manageable via CRD (was API-only) |
| `v0.2` (operator) | `instanceRef` field added to all CRDs | Enables multiple Perses instances in the same namespace |

---

## Detection Commands Reference

```bash
# List all Perses CRDs installed
kubectl get crds | grep perses.dev

# Check reconciliation status of all PersesDashboards
kubectl get persesdashboard -A

# Verify project-dashboard alignment
kubectl get persesdashboard -A -o jsonpath='{range .items[*]}{.spec.project}{"\n"}{end}' | sort -u

# Check operator logs for reconciliation errors
kubectl logs -n perses-operator -l app.kubernetes.io/name=perses-operator --tail=50 | grep -i error

# Verify ServiceMonitor is working
kubectl get servicemonitor -n monitoring | grep perses
```

---

## See Also

- `dashboard.md` — Dashboard content, DaC patterns, and percli
- `core.md` — Perses server configuration and auth setup
