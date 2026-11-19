---
name: kubernetes
description: "Kubernetes and infrastructure operations: cluster debugging, security and RBAC, manifests and Helm charts, Ansible, Prometheus/Grafana, Perses, OpenSearch/Elasticsearch, RabbitMQ, and cobaltcore tooling."
user-invocable: false
context: fork
agent: general-purpose
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
    # from kubernetes-helm
    - "kubernetes"
    - "helm"
    - "k8s"
    - "kubectl"
    - "statefulset"
    - "argocd"
    # from ansible-automation
    - "ansible"
    - "playbook"
    - "molecule"
    - "ansible-tower"
    - "AWX"
    # from prometheus-grafana
    - "prometheus"
    - "grafana"
    - "alerting"
    - "observability"
    # from opensearch-elasticsearch
    - "opensearch"
    - "elasticsearch"
    - "search cluster"
    - "logstash"
    - "kibana"
    - "search performance"
    # from rabbitmq-messaging
    - "rabbitmq"
    - "messaging"
    - "message queue"
    - "amqp"
    - "event bus"
    # from perses
    - "perses"
    - "perses dashboard"
    - "perses plugin"
    - "perses operator"
    - "perses kubernetes"
    - "perses CRD"
    - "percli"
    - "perses migrate"
    - "perses dac"
    - "PersesDashboard"
    - "perses core"
    - "contribute perses"
    - "perses backend"
    - "perses frontend"
    - "perses architecture"
    - "perses internals"
    - "perses project"
    - "observability dashboard"
    - "perses datasource"
    - "perses variable"
    - "perses helm"
    - "perses k8s"
    - "create plugin"
    - "panel plugin"
    - "datasource plugin"
    - "perses plugin development"
    - "perses cue schema"
    - "plugin schema"
  not_for: "analyzing business or product metrics data (use data); relational database schema and query tuning, ETL/ELT, or Kafka/Spark stream pipelines (use data); application test automation (use testing); Claude Code hook or toolkit automation (use toolkit); search-relevance UX or query-DSL authoring inside an app (use domain); TypeScript frontend work outside the Perses codebase (use frontend)"
  category: kubernetes
  pairs_with:
    - assessment
    - programming
    - testing
    - data
---

# Kubernetes Skill

Home for Kubernetes and infrastructure operations. Cluster domains: **debugging** (pod triage, networking, resources), **security** (RBAC, pod hardening, network isolation, supply chain), and **cobaltcore** (KVM exporter, hypervisor metrics); follow the phases below for these. Infrastructure engineering domains (manifests and Helm, Ansible, Prometheus/Grafana, Perses, OpenSearch/Elasticsearch, RabbitMQ): load the matching reference from the Domain Selection table and follow its hard rules, gates, and blockers.

In cluster work, always specify `-n <namespace>` in every kubectl command. Use read-only commands to gather evidence before proposing changes. When dispatch pays, use a `general-purpose` worker that loads this skill and the matching reference.

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
| Author or fix manifests, Helm charts, StatefulSets, ArgoCD, deploy safety | `references/kubernetes-helm.md` |
| Ansible playbooks, roles, Molecule, Vault, AWX | `references/ansible-automation.md` |
| Prometheus, Grafana, PromQL, alerting, SLO burn rate, cardinality | `references/prometheus-grafana.md` |
| Perses dashboards, plugins, operator, core | `references/perses.md` |
| OpenSearch or Elasticsearch cluster, shards, mappings, ILM, query DSL tuning | `references/opensearch-elasticsearch.md` |
| RabbitMQ, AMQP, quorum queues, DLX, prefetch | `references/rabbitmq-messaging.md` |

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

Components: KVM Exporter (`cobaltcore-dev/kvm-exporter`). Load `references/cobalt-kvm-exporter.md` for architecture, metric catalogs, configuration, and deployment. Load the `programming` skill for Go code and `references/prometheus-grafana.md` for metrics.

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
| Kubernetes manifests, Helm charts, probes, limits, image tags, deploy safety | `references/kubernetes-helm.md` | Hard rules, gates, detection, blockers; sub-reference `kubernetes-helm/` |
| Ansible playbooks, roles, idempotency, Vault, Molecule, ansible-lint | `references/ansible-automation.md` | Hard rules, gates, detection; sub-references `ansible-automation/` (security, testing, modules) |
| Prometheus, Grafana, PromQL, recording rules, Alertmanager, cardinality | `references/prometheus-grafana.md` | Hard rules, gates, audit list; sub-references `prometheus-grafana/` (PromQL, alerting, cardinality) |
| Perses dashboards, DaC, percli, plugins, CUE schema, Perses operator CRDs | `references/perses.md` | Areas and loading table; sub-references `perses/` (dashboard, operator, plugin) |
| OpenSearch, Elasticsearch, shard sizing, heap, mappings, ILM, snapshots | `references/opensearch-elasticsearch.md` | Hard rules, gates, audit list; sub-references `opensearch-elasticsearch/` (query, index, cluster) |
| RabbitMQ, AMQP, quorum queues, publisher confirms, acks, DLX, prefetch | `references/rabbitmq-messaging.md` | Hard rules, gates, audit list; sub-references `rabbitmq-messaging/` (channels, performance, error handling) |
