# Helm Chart Patterns Reference

> **Scope**: Helm 3.x chart structure, values hierarchy, template anti-patterns, and deployment safety. Does NOT cover Helm plugin development.
> **Version range**: Helm 3.x (Helm 2 is EOL — all patterns assume Helm 3)
> **Generated**: 2026-04-08

---

## Overview

Helm chart bugs fall into three classes: template errors (only caught at `helm lint` or deploy time), values hierarchy confusion (defaulting vs overriding at the wrong level), and idempotency failures (releases that break on upgrade). The detection commands below catch the most expensive mistakes before deploy.

---

## Chart Validation Pipeline

Run in this order before every deploy:

```bash
# 1. Lint for syntax errors and missing required values
helm lint ./charts/myapp --values values-prod.yaml

# 2. Render templates and inspect output
helm template myapp ./charts/myapp --values values-prod.yaml | less

# 3. Dry-run against cluster (server-side validation)
helm upgrade --install myapp ./charts/myapp \
  --values values-prod.yaml \
  --dry-run=server \
  --namespace production

# 4. Diff if upgrading existing release
helm diff upgrade myapp ./charts/myapp \
  --values values-prod.yaml \
  --namespace production
```

**Why**: `helm lint` catches template syntax. `--dry-run=server` validates against the actual Kubernetes API (catches `apiVersion` deprecations that `--dry-run=client` misses).

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| `{{ .Values.key \| default "fallback" }}` | Helm 3 | Optional values with sensible defaults | Required values — use `required` instead |
| `{{ required "msg" .Values.key }}` | Helm 3 | Values that must be set by deployer | Values with sensible defaults |
| `{{ include "mychart.labels" . \| indent 4 }}` | Helm 3 | Shared label/annotation blocks | One-off templates |
| `helm upgrade --atomic` | Helm 3 | Production deploys needing auto-rollback | Dev/test where rollback not needed |
| `lookup` function | Helm 3.1+ | Conditionally creating resources based on existing state | Simple unconditional deploys |
| `helm.sh/resource-policy: keep` annotation | Helm 3 | Secrets/PVCs that must survive `helm uninstall` | Resources that should be cleaned up |

---

## Correct Patterns

### Values File Hierarchy

Structure values from most-generic to most-specific:

```
charts/myapp/
  values.yaml          # Defaults — checked into git, safe to expose
  values-staging.yaml  # Staging overrides
  values-prod.yaml     # Production overrides (may reference secrets)
```

```yaml
# values.yaml (defaults)
replicaCount: 1
image:
  repository: myapp
  tag: "latest"       # Overridden in prod
  pullPolicy: IfNotPresent
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 256Mi

# values-prod.yaml (production overrides)
replicaCount: 3
image:
  tag: "v1.2.3"       # Specific tag in prod — never :latest
  pullPolicy: Always
```

---

### Named Templates for Shared Labels

```yaml
# templates/_helpers.tpl
{{- define "myapp.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

# templates/deployment.yaml
metadata:
  labels:
    {{- include "myapp.labels" . | nindent 4 }}
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: {{ .Chart.Name }}
      app.kubernetes.io/instance: {{ .Release.Name }}
```

**Why**: Consistent labels enable `kubectl get` filtering, `helm diff`, and monitoring dashboards that rely on `app.kubernetes.io` standard labels.

---

### Atomic Upgrades with Rollback

```bash
helm upgrade myapp ./charts/myapp \
  --values values-prod.yaml \
  --namespace production \
  --atomic \           # Auto-rollback on failure
  --timeout 5m \       # Give health checks time to pass
  --cleanup-on-fail \  # Remove new resources if upgrade fails
  --wait               # Wait for all pods to be ready before returning
```

---

## Anti-Pattern Catalog

### ❌ Hardcoded Secrets in Values Files

**Detection**:
```bash
grep -rn 'password\|secret\|token\|apiKey\|api_key' --include="values*.yaml" .
rg '(password|secret|token|apiKey|api_key): ' --type yaml
```

**What it looks like**:
```yaml
# values-prod.yaml — NEVER DO THIS
database:
  password: "mysecretpassword"   # Exposed in git history
  connectionString: "postgres://user:pass@host/db"
```

**Why wrong**: Values files are checked into git. Secrets in git history persist forever even after deletion. CI logs, PR previews, and `helm get values` all expose them.

**Fix**: Use external secret management:
```yaml
# values-prod.yaml — reference only, no values
database:
  passwordSecretRef:
    name: myapp-db-secret
    key: password
```
```yaml
# Separate Secret (created outside Helm, or via external-secrets-operator)
apiVersion: v1
kind: Secret
metadata:
  name: myapp-db-secret
data:
  password: {{ env "DB_PASSWORD" | b64enc }}  # Or use external-secrets
```

---

### ❌ Not Using `required` for Mandatory Values

**Detection**:
```bash
grep -rn '\.Values\.' --include="*.yaml" charts/*/templates/ | grep -v 'default\|required' | head -20
```

**What it looks like**:
```yaml
# templates/deployment.yaml
image: {{ .Values.image.repository }}:{{ .Values.image.tag }}
# If image.tag is missing: renders as "myapp:<no value>" — deploys broken pod
```

**Why wrong**: Missing values render as `<no value>` or empty string. The chart deploys without error, but the pod fails at runtime with a confusing image pull error.

**Fix**:
```yaml
image: {{ .Values.image.repository }}:{{ required "image.tag is required" .Values.image.tag }}
```

---

### ❌ Missing apiVersion Deprecation Check

**Detection**:
```bash
# Find deprecated API versions in chart templates
grep -rn 'apps/v1beta\|extensions/v1beta\|networking.k8s.io/v1beta1' --include="*.yaml" charts/
rg 'v1beta' --type yaml charts/
```

**What it looks like**:
```yaml
# Still works in K8s < 1.16 but deprecated since 1.16, removed in 1.25
apiVersion: extensions/v1beta1
kind: Ingress
```

**Fix**: Check target cluster version and use appropriate apiVersion:
```yaml
apiVersion: networking.k8s.io/v1  # Stable since K8s 1.19
kind: Ingress
```

**Version note**: Run `helm template | pluto detect -` or `helm lint` with `--kube-version` to catch deprecated APIs against target cluster version.

---

### ❌ No Chart Tests

**Detection**:
```bash
ls charts/*/templates/tests/ 2>/dev/null || echo "No test directory found"
find charts/ -name "*test*" -path "*/templates/*"
```

**What it looks like**: A chart with no `templates/tests/` directory and no `helm.sh/hook: test` annotated pods.

**Why wrong**: `helm install` can succeed with pods in Pending/Unready state. Without tests, there's no way to verify the chart actually works.

**Fix**:
```yaml
# templates/tests/test-connection.yaml
apiVersion: v1
kind: Pod
metadata:
  name: "{{ .Release.Name }}-test-connection"
  annotations:
    "helm.sh/hook": test
    "helm.sh/hook-delete-policy": hook-succeeded
spec:
  restartPolicy: Never
  containers:
  - name: wget
    image: busybox
    command: ['wget']
    args: ['{{ .Release.Name }}-myapp:{{ .Values.service.port }}']
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `Error: UPGRADE FAILED: resource name may not be empty` | Template renders empty name (missing required value) | Add `required` guard or check `.Values.name` |
| `Error: rendered manifests contain a resource that already exists` | Resource created outside Helm, Helm doesn't own it | Adopt with `helm upgrade --force` or delete the orphaned resource |
| `Error: chart requires kubeVersion >= X.Y.Z` | Cluster version below chart's kubeVersion constraint | Upgrade cluster or relax chart's `kubeVersion` field |
| `Error: manifest validation error: unknown field "spec.template.spec.containers[0].securityContext.seccompProfile"` | API field not available in target K8s version | Remove field or check `--kube-version` during lint |
| `Error: UPGRADE FAILED: cannot patch "X" with kind Deployment` | Immutable field changed (e.g., selector labels) | Delete and re-create the deployment |
| `template: X:Y:Z: executing "X" at <.Values.foo>: nil pointer evaluating interface {}.foo` | Nested value accessed without nil check | Use `{{ if .Values.foo }}{{ .Values.foo.bar }}{{ end }}` |

---

## Detection Commands Reference

```bash
# Validate chart before deploy
helm lint ./charts/myapp --values values-prod.yaml --strict

# Find deprecated API versions
grep -rn 'v1beta\|v1alpha' --include="*.yaml" charts/

# Find hardcoded secrets
grep -rn 'password\|secret\|token' --include="values*.yaml" . | grep -v '.example\|#'

# Find missing required guards
grep -rn '\.Values\.' charts/*/templates/ | grep -v 'default\|required\|if\|range' | head -30

# Diff upgrade before applying
helm diff upgrade <release> ./charts/myapp --values values-prod.yaml -n <namespace>
```

---

## See Also

- `kubernetes-troubleshooting.md` — pod states, resource issues, diagnostic commands
- `security.md` — RBAC templates, pod security contexts, network policies
