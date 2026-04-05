<!-- scope: Kubernetes pod lifecycle troubleshooting, probe configuration, resource management -->
<!-- versions: Kubernetes 1.25+ -->
<!-- date: 2026-04-05 -->

# Kubernetes Troubleshooting Reference

## Overview

Covers error-fix mappings for common pod states, probe misconfiguration, resource limit calculation from actual usage, and detection commands using `kubectl` with `jq`. Load this file when diagnosing broken pods, OOMKilled events, or probe-related restart loops.

---

## Error-Fix Mappings

| Error State | Root Cause | Fix |
|---|---|---|
| `OOMKilled` | Memory limit too low for workload | Measure actual usage with `kubectl top`, increase `resources.limits.memory` |
| `CrashLoopBackOff` | Container exits non-zero repeatedly | Check `kubectl logs --previous`; fix entrypoint, missing config, or bad env |
| `ImagePullBackOff` | Cannot pull image after retries | Verify image name/tag, check `imagePullSecrets`, ensure registry is reachable |
| `Pending` (insufficient resources) | No node has enough CPU/memory | Check node allocatable vs requested; scale cluster or lower requests |
| `Evicted` | Node pressure (memory/disk) | Check eviction events; add PodDisruptionBudgets, increase node capacity |
| `ErrImagePull` | First pull attempt failed | Wrong tag, registry auth missing, or network issue; check Events section |
| `ContainerCreating` (stuck) | Volume mount, CNI, or secret issue | Check Events for `FailedMount`, `NetworkPlugin`, or missing Secret/ConfigMap |
| `CreateContainerConfigError` | Missing Secret or ConfigMap reference | Verify all `envFrom` / `volumeMounts` sources exist in the same namespace |

---

## Detection Commands

### Find all broken pods across namespaces

```bash
kubectl get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded \
  -o json | jq -r '
  .items[] |
  [.metadata.namespace, .metadata.name, .status.phase,
   (.status.containerStatuses[]? | .state | keys[0])] |
  @tsv'
```

### Find OOMKilled pods in the last hour

```bash
kubectl get pods -A -o json | jq -r '
  .items[] |
  select(.status.containerStatuses[]?.lastState.terminated.reason == "OOMKilled") |
  [.metadata.namespace, .metadata.name,
   (.status.containerStatuses[].lastState.terminated.finishedAt // "unknown")] |
  @tsv'
```

### Find pods in CrashLoopBackOff

```bash
kubectl get pods -A -o json | jq -r '
  .items[] |
  select(.status.containerStatuses[]?.state.waiting.reason == "CrashLoopBackOff") |
  [.metadata.namespace, .metadata.name,
   (.status.containerStatuses[].restartCount | tostring)] |
  @tsv'
```

### Find pods with no resource requests or limits set

```bash
kubectl get pods -A -o json | jq -r '
  .items[] |
  select(
    .spec.containers[] |
    (.resources.requests == null or .resources.limits == null)
  ) |
  [.metadata.namespace, .metadata.name] | @tsv'
```

### Find stuck ContainerCreating pods with events

```bash
kubectl get pods -A --field-selector=status.phase=Pending -o json | \
  jq -r '.items[].metadata | [.namespace, .name] | @tsv' | \
  while IFS=$'\t' read -r ns pod; do
    echo "=== $ns/$pod ===";
    kubectl describe pod "$pod" -n "$ns" | grep -A 20 "^Events:";
  done
```

---

## OOMKilled: Measuring and Setting Memory Limits

### Step 1 — measure peak usage over time

```bash
# Requires metrics-server installed
kubectl top pod <pod-name> -n <namespace> --containers

# For historical data with Prometheus:
kubectl exec -n monitoring deploy/prometheus -- \
  promtool query instant \
  'max_over_time(container_memory_working_set_bytes{pod=~"myapp-.*"}[24h])'
```

### Step 2 — calculate a safe limit

A safe formula: `limit = peak_usage * 1.3` rounded up to the nearest 64Mi.

If a container's `max_over_time` working set was 410Mi over 24 hours, set limit to `512Mi` (410 * 1.3 = 533 → round to 512 is too low, use 576Mi or 640Mi).

### Step 3 — set in values / manifest

```yaml
resources:
  requests:
    memory: "256Mi"   # typical sustained usage
    cpu: "100m"
  limits:
    memory: "640Mi"   # peak * 1.3, rounded to 64Mi boundary
    # Avoid CPU limits to prevent throttling; use requests only for CPU
```

> **Version note (K8s 1.27+):** In-place resource resize for pods (`kubectl patch pod`) is available as alpha. Production use still requires pod restart.

---

## Probes: startup vs liveness vs readiness

| Probe | When it fires | Failure action | Common misconfiguration |
|---|---|---|---|
| `startupProbe` | During container init only, before liveness/readiness start | Kills container if it fails within `failureThreshold * periodSeconds` | `failureThreshold` too low for slow-starting JVM/Ruby apps |
| `livenessProbe` | Continuously after startup probe passes | Kills and restarts container | Checking an endpoint that depends on a downstream service — restarts app when the dependency is broken |
| `readinessProbe` | Continuously after startup probe passes | Removes pod from Service endpoints (no restart) | Same config as liveness; too-aggressive `failureThreshold` causes flapping |

### Correct pattern — differentiated probes

```yaml
startupProbe:
  httpGet:
    path: /healthz/startup
    port: 8080
  failureThreshold: 30   # 30 * 10s = 5 minutes for slow start
  periodSeconds: 10

livenessProbe:
  httpGet:
    path: /healthz/live    # checks only internal state; never external deps
    port: 8080
  initialDelaySeconds: 0  # startupProbe handles the delay
  periodSeconds: 15
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /healthz/ready   # may include dependency checks
    port: 8080
  periodSeconds: 5
  failureThreshold: 3
```

---

## Anti-Pattern Catalog

### Anti-pattern: liveness probe identical to readiness probe

**Why it causes harm:** If a downstream dependency fails, the readiness probe correctly removes the pod from the load balancer. But the identical liveness probe then also fires, killing and restarting the container — which doesn't fix the downstream issue, creates a restart loop, and generates unnecessary `CrashLoopBackOff` backoff delay.

**Detection:**

```bash
kubectl get pods -A -o json | jq -r '
  .items[] |
  select(
    .spec.containers[] |
    (.livenessProbe != null) and (.readinessProbe != null) and
    (.livenessProbe == .readinessProbe)
  ) |
  [.metadata.namespace, .metadata.name] | @tsv'
```

**Fix:** Liveness checks internal process health only. Readiness checks readiness to serve traffic (may include dependency checks).

---

### Anti-pattern: no terminationGracePeriodSeconds on StatefulSets

**Why it causes harm:** The default grace period is 30 seconds. StatefulSets with slow shutdown (databases flushing WAL, Kafka flushing offsets, Elasticsearch merging segments) can be killed mid-operation, causing data corruption or recovery overhead on next start.

**Detection:**

```bash
kubectl get statefulsets -A -o json | jq -r '
  .items[] |
  select(.spec.template.spec.terminationGracePeriodSeconds == null) |
  [.metadata.namespace, .metadata.name] | @tsv'
```

**Fix:** Set based on measured shutdown time plus buffer.

```yaml
# StatefulSet spec.template.spec
terminationGracePeriodSeconds: 120   # tune to actual shutdown duration
```

Also add a `preStop` hook to allow the container to drain before SIGTERM is sent:

```yaml
lifecycle:
  preStop:
    exec:
      command: ["/bin/sh", "-c", "sleep 5"]  # allow load balancer to drain
```
