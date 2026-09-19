---
name: kubernetes
description: "Kubernetes operations: debugging, security, RBAC, and infrastructure tooling."
user-invocable: false
context: fork
agent: kubernetes-helm-engineer
routing:
  triggers:
    # from kubernetes-debugging
    - "kubernetes debug"
    - "pod failure"
    - "pod crashloop"
    - "kubectl logs"
    - "OOMKilled"
    - "pod pending"
    # from kubernetes-security
    - "kubernetes security"
    - "k8s RBAC"
    - "RBAC setup"
    - "pod security policy"
    - "network policy"
    # from cobalt-core
    - "cobalt core"
    - "cobaltcore"
    - "kvm-exporter"
    - "kvm exporter"
    - "hypervisor metrics"
    - "libvirt exporter"
    - "cloud hypervisor"
  category: kubernetes
  pairs_with:
    - assessment
    - programming
    - prometheus-grafana-engineer
---

# Kubernetes Skill

Three domains: **debugging** (pod triage, networking, resources), **security** (RBAC, pod hardening, network isolation, supply chain), and **cobaltcore** (KVM exporter, hypervisor metrics). Select by request signal, then follow the phases below.

Always specify `-n <namespace>` in every kubectl command. Use read-only commands to gather evidence before proposing changes.

---

## Domain Selection

| Signal | Domain |
|--------|--------|
| CrashLoopBackOff, OOMKilled, ImagePullBackOff, Pending | Debugging |
| Service unreachable, DNS failure, port-forward | Debugging (network) |
| CPU throttling, memory limit, disk pressure | Debugging (resources) |
| RBAC, permissions, roles, ServiceAccount | Security (access) |
| Pod hardening, container security, PodSecurity | Security (pods) |
| NetworkPolicy, default-deny, namespace isolation | Security (network) |
| Image signing, secrets, admission control | Security (supply chain) |
| KVM exporter, cobaltcore, hypervisor metrics | Cobaltcore |

---

## Phase 1: TRIAGE

### Debugging Triage Flow

Follow this sequence for every pod or workload issue. Do not skip steps -- many failures are only visible in events and describe output, not in logs.

```bash
kubectl get pods -n <namespace> -o wide
kubectl describe pod <pod-name> -n <namespace>
kubectl logs <pod-name> -n <namespace> -c <container-name>
kubectl logs <pod-name> -n <namespace> -c <container-name> --previous
kubectl get events -n <namespace> --sort-by='.lastTimestamp'
kubectl exec -it <pod-name> -n <namespace> -c <container-name> -- /bin/sh
```

Always check `--previous` logs for crashed containers before current logs -- restarting destroys them permanently.

**Diagnosis routing**:

| Symptom | Action |
|---------|--------|
| CrashLoopBackOff, ImagePullBackOff, Pending, FailedScheduling | Check describe output for events, previous logs, image pull errors |
| Service unreachable, DNS failure | Check service endpoints, CoreDNS, NetworkPolicy below |
| CPU throttling, OOMKill, disk pressure | Check resource limits, requests vs actual, node capacity |
| "no endpoints available for service" | Compare svc selector with pod labels |

**Network debugging**:

```bash
# Verify service has endpoints
kubectl get endpoints <service-name> -n <namespace>
# DNS lookup from inside cluster
kubectl run dns-debug --rm -it --restart=Never --image=busybox:1.36 -n <namespace> -- \
  nslookup <service-name>.<namespace>.svc.cluster.local
# Check CoreDNS
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=50
# Port-forward for local testing
kubectl port-forward svc/<service-name> -n <namespace> 8080:80
```

### Security Domain Selection

For security requests, provide concrete YAML manifests from the patterns below. Reference-backed specifics, not generic advice.

**RBAC patterns**: Prefer namespace-scoped Roles over ClusterRoles. Write exact verbs and resources. Create dedicated ServiceAccounts per workload. Set `automountServiceAccountToken: false` on pods that need no API access.

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: app-team
  name: deployment-reader
rules:
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["get", "list", "watch"]
```

**Pod security**: Enforce PodSecurity labels at namespace level. All containers: `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`, `capabilities: drop: ["ALL"]`. Use distroless base images. Pin image digests.

```yaml
labels:
  pod-security.kubernetes.io/enforce: restricted
  pod-security.kubernetes.io/warn: restricted
```

**Network policies**: Start with default-deny for ingress and egress. Add allow-list rules per service. Always allow DNS egress (UDP/TCP 53).

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]
```

### Cobaltcore Domain

Components: KVM Exporter (`cobaltcore-dev/kvm-exporter`). Load `references/cobalt-kvm-exporter.md` for architecture, metric catalogs, configuration, and deployment. Pair with `go-patterns` for code, `prometheus-grafana-engineer` for metrics.

---

## Phase 2: DIAGNOSE / RESPOND

**Debugging**: Follow the triage flow. Gather evidence with read-only commands before proposing changes.

**Security**: Provide copy-paste-ready YAML using the patterns in Phase 1.

**Cobaltcore**: Use component-specific references for architecture, metrics, concurrency patterns, and testing.

---

## Phase 3: VERIFY

- **Debugging**: Confirm the fix resolves the symptom with the same triage commands.
- **Security**: Validate against the PodSecurity standards and RBAC least-privilege patterns above.
- **Cobaltcore**: Verify against component test patterns in `references/cobalt-testing-patterns.md`.

---

## Deep References

| Signal | Reference | Content |
|--------|-----------|---------|
| KVM exporter architecture, metrics, config | `references/cobalt-kvm-exporter.md` | Full component reference (463 lines) |
| Cobaltcore concurrency, goroutine, semaphore | `references/cobalt-concurrency-patterns.md` | Go concurrency patterns (268 lines) |
| Cobaltcore testing, mock, Kind cluster | `references/cobalt-testing-patterns.md` | Testing strategies (271 lines) |
