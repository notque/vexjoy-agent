# Crash Diagnosis Reference

> **Scope**: CrashLoopBackOff (OOMKilled, config errors, health check failures), ImagePullBackOff (auth, tags, network), and Pending pod diagnosis (scheduling, affinity, taints, PVC). Does NOT cover networking or resource monitoring.
> **Version range**: Kubernetes 1.25+ (ephemeral containers assumed available)
> **Generated**: 2026-04-16

---

## CrashLoopBackOff Diagnosis

CrashLoopBackOff means the container starts, exits, and Kubernetes restarts it with exponential backoff. Do not `kubectl delete pod` to "fix" this -- the replacement pod will crash the same way, and you lose the previous container's logs. Read `--previous` logs and describe events first.

### OOMKilled -- container exceeded memory limit

```bash
# Check termination reason
kubectl describe pod <pod-name> -n <namespace> | grep -A 5 "Last State"
# Look for: Reason: OOMKilled

# Check resource limits vs actual usage
kubectl top pod <pod-name> -n <namespace>
```

Fix: Increase `resources.limits.memory` or fix the memory leak in the application. Do not blindly increase limits without checking actual usage first -- over-provisioning wastes cluster resources, and a memory leak will eventually exceed any limit you set. Run `kubectl top pod` under realistic load, then set limits to 1.5-2x observed peak.

### Application configuration error -- missing env vars, bad config file, wrong DB host

```bash
# Check logs from the previous (crashed) instance
kubectl logs <pod-name> -n <namespace> --previous

# Verify environment variables are set correctly
kubectl exec <pod-name> -n <namespace> -- env | sort

# Check if ConfigMap/Secret is mounted
kubectl describe pod <pod-name> -n <namespace> | grep -A 10 "Mounts"
```

### Health check failure -- liveness probe kills the container

```bash
# Check probe configuration
kubectl describe pod <pod-name> -n <namespace> | grep -A 10 "Liveness"

# Common issues:
# - initialDelaySeconds too short for slow-starting apps
# - Probe endpoint returns non-200 during startup
# - Probe timeout too aggressive
```

```yaml
# Fix: add a startup probe for slow-starting applications
spec:
  containers:
    - name: app
      startupProbe:
        httpGet:
          path: /healthz
          port: 8080
        failureThreshold: 30
        periodSeconds: 10
      livenessProbe:
        httpGet:
          path: /healthz
          port: 8080
        periodSeconds: 10
        timeoutSeconds: 5
```

---

## ImagePullBackOff Diagnosis

The kubelet cannot pull the container image.

```bash
# Check the exact error
kubectl describe pod <pod-name> -n <namespace> | grep -A 5 "Events"
# Look for: Failed to pull image, ErrImagePull, ImagePullBackOff
```

### Registry authentication -- private registry requires credentials

```bash
# Verify imagePullSecrets exist on the pod
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.imagePullSecrets}'

# Check if the secret exists and has valid data
kubectl get secret <pull-secret> -n <namespace> -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d
```

### Image tag does not exist -- typo or tag was overwritten

```bash
# Verify the image reference
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.containers[0].image}'

# Test pulling manually on a node or locally
docker pull <image-reference>
```

Do not trust `:latest` tags -- they are mutable, so the image you tested locally may differ from what the node pulled. Always use image digests or immutable tags, and verify the exact image reference with the jsonpath command above.

### Network issues -- node cannot reach the registry

```bash
# Check if the node has network access to the registry
kubectl debug node/<node-name> -it --image=busybox -- nslookup registry.example.com
```

---

## Pending Pods

Pods stuck in Pending state have not been scheduled to any node.

```bash
# Check scheduler events
kubectl describe pod <pod-name> -n <namespace> | grep -A 10 "Events"
# Look for: FailedScheduling, Insufficient cpu, Insufficient memory
```

### Resource constraints -- not enough CPU or memory on any node

```bash
# Check node capacity and allocatable resources
kubectl describe nodes | grep -A 5 "Allocated resources"

# Check resource requests across the cluster
kubectl top nodes
```

### Node affinity or node selector mismatch

```bash
# Check what the pod requires
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.nodeSelector}'
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.affinity}'

# Check node labels
kubectl get nodes --show-labels
```

### Taints and tolerations

```bash
# Check node taints
kubectl describe nodes | grep -A 3 "Taints"

# Check pod tolerations
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.tolerations}'
```

### PersistentVolumeClaim not bound

```bash
# Check PVC status
kubectl get pvc -n <namespace>

# Describe the PVC for events
kubectl describe pvc <pvc-name> -n <namespace>
```
