# Resource Debugging Reference

> **Scope**: CPU throttling detection, memory limits and OOMKill analysis, ephemeral storage pressure, ephemeral debug containers, and kubectl command reference table. Does NOT cover crash diagnosis root causes or networking.
> **Version range**: Kubernetes 1.25+ (ephemeral containers assumed available)
> **Generated**: 2026-04-16

---

## CPU Throttling -- container is being throttled by its CPU limit

```bash
# Check current usage vs limits
kubectl top pod <pod-name> -n <namespace> --containers

# Check throttling metrics (requires metrics-server or Prometheus)
# Look for container_cpu_cfs_throttled_periods_total in metrics
kubectl describe pod <pod-name> -n <namespace> | grep -A 5 "Limits"
```

---

## Memory Limits -- OOMKill or high memory pressure

```bash
# Check if the pod was OOMKilled
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.containerStatuses[0].lastState}'

# Check current memory usage
kubectl top pod <pod-name> -n <namespace> --containers

# Check node memory pressure
kubectl describe node <node-name> | grep -A 5 "Conditions"
```

---

## Ephemeral Storage Pressure -- logs or temp files fill the node disk

```bash
# Check node disk pressure condition
kubectl describe node <node-name> | grep -A 2 "DiskPressure"

# Check pod ephemeral storage usage
kubectl describe pod <pod-name> -n <namespace> | grep -A 3 "ephemeral-storage"
```

---

## Ephemeral Debug Containers

When a container has no shell (distroless, scratch), use ephemeral containers:

```bash
# Attach a debug container with networking tools
kubectl debug -it <pod-name> -n <namespace> \
  --image=nicolaka/netshoot \
  --target=<container-name>

# Inside the debug container, you can:
# - Check network: curl, dig, tcpdump, ss
# - Inspect filesystem: ls /proc/1/root (target container's filesystem)
# - Check processes: ps aux
```

```bash
# Debug a node directly
kubectl debug node/<node-name> -it --image=ubuntu

# This creates a pod with hostPID, hostNetwork, and mounts the node filesystem at /host
# Useful for: checking kubelet logs, node networking, disk usage
chroot /host
journalctl -u kubelet --no-pager --tail=50
```

---

## kubectl Commands Reference

| Command | Purpose |
|---------|---------|
| `kubectl describe pod <pod> -n <ns>` | Full pod status, events, conditions |
| `kubectl logs <pod> -n <ns> --previous` | Logs from the last crashed container |
| `kubectl logs <pod> -n <ns> --tail=100 -f` | Stream last 100 lines and follow |
| `kubectl get events -n <ns> --sort-by='.lastTimestamp'` | Namespace events in chronological order |
| `kubectl top pod -n <ns>` | CPU and memory usage per pod |
| `kubectl top nodes` | CPU and memory usage per node |
| `kubectl get pod <pod> -n <ns> -o yaml` | Full pod spec and status in YAML |
| `kubectl exec -it <pod> -n <ns> -- /bin/sh` | Shell into a running container |
| `kubectl port-forward pod/<pod> -n <ns> 8080:8080` | Forward pod port to localhost |
| `kubectl debug pod/<pod> -n <ns> --image=busybox -it` | Attach ephemeral debug container |
| `kubectl rollout status deployment/<name> -n <ns>` | Watch deployment rollout progress |
| `kubectl rollout undo deployment/<name> -n <ns>` | Roll back to previous revision |

---

## Error Handling

### Error: "kubectl exec" fails with "container not running"
Cause: The container is in CrashLoopBackOff or has not started yet.
Solution: Use `kubectl logs --previous` to get crash logs. If the container exits immediately, check the entrypoint command and environment variables.

### Error: "kubectl debug" not available
Cause: Ephemeral containers require Kubernetes 1.25+ and the feature gate to be enabled.
Solution: Check cluster version with `kubectl version`. For older clusters, create a standalone debug pod in the same namespace with `kubectl run`.
