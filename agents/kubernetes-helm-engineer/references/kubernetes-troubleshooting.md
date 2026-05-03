# Kubernetes Troubleshooting Reference

> **Scope**: Pod failure states, resource issues, networking problems, and diagnostic command patterns. Does NOT cover Helm chart development.
> **Version range**: Kubernetes 1.24+ (pod security admission), Helm 3.x
> **Generated**: 2026-04-08

---

## Overview

Kubernetes pod failures follow predictable patterns. The three most frequent are: image pull failures (registry auth or typos), resource-related crashes (OOMKilled, CPU throttle), and probe failures (liveness killing healthy pods). Each has a deterministic diagnosis path — the commands below surface root cause within 60 seconds.

---

## Pod State Diagnosis Table

| Pod State | Common Cause | First Command |
|-----------|-------------|---------------|
| `ImagePullBackOff` | Wrong image name, missing pull secret, private registry | `kubectl describe pod <pod> \| grep -A5 Events` |
| `CrashLoopBackOff` | App crash, missing env var, OOM, bad probe config | `kubectl logs <pod> --previous` |
| `OOMKilled` | Memory limit too low or memory leak | `kubectl describe pod <pod> \| grep -A2 'OOM\|Limits'` |
| `Pending` | No schedulable node, PVC unbound, resource quota exceeded | `kubectl describe pod <pod> \| grep -A10 Events` |
| `Terminating` (stuck) | Finalizer not cleared, PVC in use | `kubectl describe pod <pod> \| grep Finalizers` |
| `Running` (failing readiness) | Probe misconfigured, app slow to start | `kubectl describe pod <pod> \| grep -A10 Readiness` |
| `CreateContainerConfigError` | Missing ConfigMap or Secret referenced in pod spec | `kubectl get events --sort-by='.lastTimestamp' -n <ns>` |
| `ErrImageNeverPull` | `imagePullPolicy: Never` but image not cached on node | Check image exists: `crictl images \| grep <name>` |

---

## Correct Diagnostic Patterns

### Full Pod Diagnosis in 3 Commands

```bash
# 1. Check current state and recent events
kubectl describe pod <pod-name> -n <namespace>

# 2. Check current logs (or previous if CrashLoop)
kubectl logs <pod-name> -n <namespace> --previous 2>/dev/null || kubectl logs <pod-name> -n <namespace>

# 3. Check recent cluster events (sorted by time)
kubectl get events -n <namespace> --sort-by='.lastTimestamp' | tail -20
```

---

### OOMKilled — Resource Limit Investigation

```bash
# Find pods with OOM kills
kubectl get pods --all-namespaces -o json | \
  jq '.items[] | select(.status.containerStatuses[]?.lastState.terminated.reason == "OOMKilled") |
  {name: .metadata.name, ns: .metadata.namespace}'

# Check actual vs requested memory for a pod
kubectl top pod <pod-name> -n <namespace>

# View resource limits on all containers in a deployment
kubectl get deployment <name> -n <namespace> -o jsonpath='{.spec.template.spec.containers[*].resources}'
```

---

### ImagePullBackOff — Registry Auth Debug

```bash
# Check what image is being pulled and from where
kubectl describe pod <pod> | grep -E 'Image:|Failed to pull'

# Verify pull secret exists in the right namespace
kubectl get secret <secret-name> -n <namespace> -o jsonpath='{.type}'
# Should output: kubernetes.io/dockerconfigjson

# Test pull secret is correctly formatted
kubectl get secret <secret-name> -n <namespace> \
  -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d | jq .
```

---

## Pattern Catalog

### Set Resource Requests and Limits on All Containers
**Detection**:
```bash
# Find deployments with containers missing resource limits
kubectl get deployments --all-namespaces -o json | \
  jq '.items[] | select(.spec.template.spec.containers[] | .resources.limits == null) |
  {name: .metadata.name, ns: .metadata.namespace}'

# Find pods currently running without resource limits
kubectl get pods --all-namespaces -o json | \
  jq '.items[] | select(.spec.containers[] | .resources.limits == null) | .metadata.name'
```

**Signal**:
```yaml
containers:
- name: app
  image: myapp:v1.2.3
  # No resources block at all
```

**Why this matters**: Without limits, a single pod can consume all node memory/CPU. OOMKiller will evict other pods first. Kubernetes scheduler can't pack nodes efficiently without requests.

**Preferred action**:
```yaml
containers:
- name: app
  image: myapp:v1.2.3
  resources:
    requests:
      cpu: "100m"
      memory: "128Mi"
    limits:
      cpu: "500m"
      memory: "256Mi"
```

**Version note**: Pod QoS class (Guaranteed, Burstable, BestEffort) is derived from requests/limits. Guaranteed (requests == limits) gets highest scheduling priority.

---

### Use Immutable Image Tags in Production
**Detection**:
```bash
# Find deployments using :latest tag
kubectl get deployments --all-namespaces -o json | \
  jq '.items[] | select(.spec.template.spec.containers[].image | endswith(":latest")) |
  {name: .metadata.name, namespace: .metadata.namespace,
   image: .spec.template.spec.containers[].image}'

# Check in manifests/helm values
grep -rn ':latest' --include="*.yaml" --include="*.yml" .
rg ':latest' --type yaml
```

**Why this matters**: `:latest` is pulled differently based on `imagePullPolicy`. `Always` causes unnecessary registry calls; `IfNotPresent` means different nodes run different versions silently. Rollbacks are impossible — you can't pin `:latest` to a previous image.

**Preferred action**: Use immutable tags: `image: myapp:v1.2.3` or `image: myapp:$(git rev-parse --short HEAD)`.

---

### Configure Conservative Liveness Probes
**Detection**:
```bash
# Find pods with short liveness probe timeouts
kubectl get pods --all-namespaces -o json | \
  jq '.items[] | select(.spec.containers[].livenessProbe.failureThreshold <= 2) |
  {name: .metadata.name, threshold: .spec.containers[].livenessProbe.failureThreshold}'

grep -rn 'failureThreshold: [12]$' --include="*.yaml" .
```

**Signal**:
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
  failureThreshold: 2  # Kills pod after 10 seconds of slowness
```

**Why this matters**: A GC pause, high load, or slow startup triggers liveness failure, causing a restart loop. CrashLoopBackOff makes the pod worse, not better.

**Preferred action**:
```yaml
livenessProbe:
  httpGet:
    path: /healthz   # Lightweight: just return 200, no DB checks
    port: 8080
  initialDelaySeconds: 30  # Give app time to start
  periodSeconds: 10
  failureThreshold: 5    # Allow 50 seconds of slowness before killing

readinessProbe:
  httpGet:
    path: /ready      # Full health check: DB, cache, dependencies
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 5
  failureThreshold: 3
```

**Rule**: Liveness = "is the process fundamentally broken?" (simple). Readiness = "is the process ready for traffic?" (thorough).

---

### Add PodDisruptionBudget for Production Deployments
**Detection**:
```bash
# Find deployments without a matching PDB
kubectl get deployments -n <namespace> -o jsonpath='{.items[*].metadata.name}' | \
  tr ' ' '\n' | while read dep; do
    kubectl get pdb -n <namespace> -o jsonpath='{.items[*].spec.selector.matchLabels}' | \
      grep -q "$dep" || echo "No PDB for: $dep"
  done
```

**Why this matters**: Without a PDB, node drains (maintenance, rolling upgrades) can take down all replicas simultaneously, causing a production outage.

**Preferred action**:
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: myapp-pdb
  namespace: production
spec:
  minAvailable: 1  # Always keep at least 1 pod running
  selector:
    matchLabels:
      app: myapp
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `Back-off restarting failed container` | CrashLoopBackOff — check `kubectl logs --previous` | Fix app crash; check env vars, config mounts, resource limits |
| `0/N nodes are available: N Insufficient memory` | No node has enough available memory | Reduce memory request, add nodes, or check if pods are OOMKilled elsewhere |
| `persistentvolumeclaim "X" not found` | PVC doesn't exist or wrong namespace | `kubectl get pvc -n <ns>` to verify; check if storage class is default |
| `Error creating: pods "X" is forbidden: exceeded quota` | ResourceQuota in namespace exceeded | `kubectl describe resourcequota -n <ns>` to see limits; delete or resize |
| `MountVolume.SetUp failed` | Volume mount failure (CSI driver, permissions) | `kubectl describe node <node>` for CSI driver status |
| `Readiness probe failed: connection refused` | App not listening on probe port, or not ready yet | Increase `initialDelaySeconds`; verify app starts on correct port |
| `Error from server (Forbidden): pods "X" is forbidden: unable to validate against any security policy` | Pod Security Admission blocks pod spec | Check `securityContext`, add `runAsNonRoot: true`, remove privileged containers |

---

## Detection Commands Reference

```bash
# Full cluster health snapshot
kubectl get pods --all-namespaces | grep -v Running | grep -v Completed

# Recent events with problems (all namespaces)
kubectl get events --all-namespaces --sort-by='.lastTimestamp' | grep -E 'Warning|Error' | tail -30

# Resource pressure on nodes
kubectl top nodes

# Pods consuming most memory
kubectl top pods --all-namespaces --sort-by=memory | head -20

# Pods without resource limits (production risk)
kubectl get pods --all-namespaces -o json | \
  jq '.items[] | select(.spec.containers[] | .resources.limits == null) | .metadata.name'

# Deployments using :latest tag (production anti-pattern)
kubectl get deployments --all-namespaces -o json | \
  jq '.items[] | select(.spec.template.spec.containers[].image | endswith(":latest")) | .metadata.name'
```

---

## See Also

- `helm-patterns.md` — chart development, values hierarchy, template anti-patterns
- `security.md` — RBAC patterns, pod security standards, network policy templates
