<!-- scope: Kubernetes security hardening — Pod Security Standards, RBAC, securityContext, NetworkPolicy -->
<!-- versions: Kubernetes 1.25+ (Pod Security Standards GA), Kubernetes 1.21+ (NetworkPolicy) -->
<!-- date: 2026-04-05 -->

# Kubernetes Security Hardening Reference

## Overview

Covers Pod Security Standards enforcement via namespace labels, RBAC anti-patterns and detection, `securityContext` best practices, and NetworkPolicy default-deny. Load this file when hardening a cluster, reviewing workload security posture, or remediating audit findings.

---

## Pod Security Standards

Kubernetes 1.25 removed PodSecurityPolicy and replaced it with built-in Pod Security Admission (PSA). Three policy levels:

| Level | What it allows | Typical use |
|---|---|---|
| `privileged` | No restrictions | System namespaces (`kube-system`), node agents |
| `baseline` | Prevents known privilege escalations; allows some capabilities | Most application namespaces as minimum |
| `restricted` | Hardened; requires non-root, no privilege escalation, dropped capabilities | Production workloads, CI runners |

### Applying via namespace labels

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    # enforce: blocks non-compliant pods
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/enforce-version: latest
    # warn: admits pod but emits a warning
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/warn-version: latest
    # audit: logs violation without blocking
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/audit-version: latest
```

### Migrating from baseline to restricted

Use `warn` mode first to identify violations without blocking deploys:

```bash
# Add warn label to an existing namespace
kubectl label namespace production \
  pod-security.kubernetes.io/warn=restricted \
  pod-security.kubernetes.io/warn-version=latest

# Watch for warnings during next deployment
kubectl apply -f deployment.yaml 2>&1 | grep Warning
```

> **Version note (K8s 1.25+):** PSA is built-in — no admission webhook required. Prior to 1.25, the `pod-security.admission` feature gate was needed (alpha in 1.22, beta in 1.23).

---

## RBAC Anti-Pattern Catalog

### Anti-pattern: cluster-admin bindings for application accounts

`cluster-admin` grants unrestricted access to every resource. No application workload should hold this role.

**Detection:**

```bash
kubectl get clusterrolebindings -o json | jq -r '
  .items[] |
  select(.roleRef.name == "cluster-admin") |
  [.metadata.name,
   (.subjects[]? | .kind + "/" + .name)] |
  @tsv'
```

**Fix:** Create a least-privilege Role scoped to the namespace and bind it to the ServiceAccount.

---

### Anti-pattern: wildcard resource or verb permissions

`resources: ["*"]` or `verbs: ["*"]` grants far broader access than any application needs.

**Detection:**

```bash
kubectl get clusterroles,roles -A -o json | jq -r '
  .items[] |
  select(.rules[]? | .resources[] == "*" or .verbs[] == "*") |
  [(.metadata.namespace // "cluster-scoped"), .metadata.name] | @tsv'
```

**Fix:** Enumerate only the exact resources and verbs the workload needs.

```yaml
# BAD
rules:
  - apiGroups: ["*"]
    resources: ["*"]
    verbs: ["*"]

# GOOD — minimal permissions for a read-only config consumer
rules:
  - apiGroups: [""]
    resources: ["configmaps"]
    verbs: ["get", "list", "watch"]
    resourceNames: ["app-config"]   # restrict to specific named resource
```

---

### Anti-pattern: manually mounting ServiceAccount tokens

Auto-mounted tokens are short-lived (1 hour, rotated by the kubelet). Manually projecting long-lived tokens or using legacy `kubernetes.io/service-account-token` Secrets bypasses this protection.

**Detection:**

```bash
# Find pods that mount legacy SA token secrets manually
kubectl get pods -A -o json | jq -r '
  .items[] |
  select(
    .spec.volumes[]? |
    .secret.secretName? | startswith("default-token") or startswith("sa-token")
  ) |
  [.metadata.namespace, .metadata.name] | @tsv'
```

**Fix:** Use projected service account tokens with explicit expiration:

```yaml
volumes:
  - name: kube-api-access
    projected:
      sources:
        - serviceAccountToken:
            path: token
            expirationSeconds: 3600
```

---

## Detection Commands

### Find pods running as root (UID 0)

```bash
kubectl get pods -A -o json | jq -r '
  .items[] |
  select(
    (.spec.securityContext.runAsUser == 0 or
     .spec.securityContext.runAsUser == null) and
    (.spec.containers[].securityContext.runAsNonRoot != true)
  ) |
  [.metadata.namespace, .metadata.name] | @tsv'
```

### Find privileged containers

```bash
kubectl get pods -A -o json | jq -r '
  .items[] |
  select(.spec.containers[].securityContext.privileged == true) |
  [.metadata.namespace, .metadata.name] | @tsv'
```

### Find over-privileged ClusterRoleBindings (non-system)

```bash
kubectl get clusterrolebindings -o json | jq -r '
  .items[] |
  select(
    .metadata.name | startswith("system:") | not
  ) |
  [.metadata.name, .roleRef.name,
   ([.subjects[]? | .kind + "/" + .name] | join(", "))] |
  @tsv'
```

### Find namespaces with no Pod Security labels

```bash
kubectl get namespaces -o json | jq -r '
  .items[] |
  select(
    (.metadata.labels | keys | map(startswith("pod-security.kubernetes.io")) | any) | not
  ) |
  select(.metadata.name | startswith("kube") | not) |
  .metadata.name'
```

---

## securityContext Best Practices

### Pod-level securityContext

```yaml
spec:
  securityContext:
    runAsNonRoot: true       # kubelet rejects containers that attempt to run as UID 0
    runAsUser: 1000          # explicit non-root UID
    runAsGroup: 1000
    fsGroup: 1000            # volume ownership group
    seccompProfile:
      type: RuntimeDefault   # apply the container runtime's default seccomp filter
```

### Container-level securityContext

```yaml
containers:
  - name: app
    securityContext:
      allowPrivilegeEscalation: false   # prevents setuid / sudo escalation
      readOnlyRootFilesystem: true      # prevents writes outside mounted volumes
      capabilities:
        drop:
          - ALL                          # drop every Linux capability
        add:
          - NET_BIND_SERVICE             # re-add only what's needed (port < 1024)
```

### Writable directories when readOnlyRootFilesystem: true

```yaml
# Mount emptyDir for directories the app must write to
volumes:
  - name: tmp
    emptyDir: {}
  - name: cache
    emptyDir: {}

containers:
  - name: app
    volumeMounts:
      - name: tmp
        mountPath: /tmp
      - name: cache
        mountPath: /app/cache
    securityContext:
      readOnlyRootFilesystem: true
```

---

## NetworkPolicy: Default-Deny Pattern

Kubernetes allows all pod-to-pod traffic by default. A default-deny policy requires explicit allow rules for any connection.

### Default-deny all ingress and egress in a namespace

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: production
spec:
  podSelector: {}       # matches all pods in the namespace
  policyTypes:
    - Ingress
    - Egress
  # No ingress or egress rules = deny all
```

### Allow ingress from specific namespace and label selector

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend-to-api
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: api-server
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: production
          podSelector:
            matchLabels:
              app: frontend
      ports:
        - protocol: TCP
          port: 8080
```

### Allow DNS egress (required for most workloads with default-deny egress)

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns-egress
  namespace: production
spec:
  podSelector: {}
  policyTypes:
    - Egress
  egress:
    - ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
```

> **Note:** NetworkPolicy enforcement requires a CNI plugin that supports it (Calico, Cilium, Weave Net). Flannel does not enforce NetworkPolicies — policies will be accepted by the API server but silently have no effect.

---

## Error-Fix Mappings

| Finding | Cause | Fix |
|---|---|---|
| Pod rejected by PSA with `restricted` | `allowPrivilegeEscalation` not set to false, or running as root | Add `securityContext.allowPrivilegeEscalation: false` and `runAsNonRoot: true` |
| Pod rejected: `forbidden: unable to validate against any security policy` | Namespace enforcing `restricted`; pod uses `hostNetwork` or `hostPID` | Remove host-level access or move to a `baseline` namespace with documented exception |
| `Error from server (Forbidden): pods is forbidden: User cannot create` | Missing RBAC or wrong ServiceAccount | Check `kubectl auth can-i create pods --as=system:serviceaccount:ns:sa` |
| NetworkPolicy blocks expected traffic | Default-deny in place, no allow rule | Add a NetworkPolicy with the correct `podSelector` and `from`/`to` rules |
| Container writes fail with `read-only file system` | `readOnlyRootFilesystem: true` with no emptyDir for writable paths | Mount `emptyDir` volumes for `/tmp`, log dirs, and any runtime-generated files |
