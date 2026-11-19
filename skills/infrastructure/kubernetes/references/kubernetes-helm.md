# Kubernetes and Helm Reference

> **Scope**: Author and fix Kubernetes manifests and Helm charts: Deployments, StatefulSets, DaemonSets, Jobs, CronJobs, storage (PVCs, storage classes, CSI), Services, Ingress, NetworkPolicies, HPA/VPA, chart templating, values, and releases.
> **Not here**: cluster debugging triage, RBAC, and security hardening (the `kubernetes` SKILL.md phases); Ansible (`ansible-automation.md`); Prometheus or Grafana (`prometheus-grafana.md`); Perses (`perses.md`); database schema (`skills/analysis/data/references/database.md`); application code (`programming` skill). CI/CD pipeline setup (Jenkins, GitLab CI, GitHub Actions) is out of scope.

Priorities, in order: safety (context checks, dry-runs, rollback plans), reliability (health checks, PDBs, resource limits), security (RBAC, network policies, pod security standards), observability (labels, monitoring, logging).

## Hard rules

- **Verify kubectl context**: run `kubectl config current-context` before any cluster operation.
- **Helm lint required**: run `helm lint` on every chart change before deploying.
- **Resource limits mandatory**: every pod spec sets CPU and memory requests and limits.
- **Dry-run first**: preview with `--dry-run=client` or `--dry-run=server` before applying.
- **Namespace isolation**: keep namespace isolation and RBAC correct for multi-tenant clusters.

## Defaults (on unless disabled)

- Show full kubectl output.
- Create PodDisruptionBudgets for production deployments.
- Define liveness and readiness probes for every application container.
- Show `helm diff` output before every `helm upgrade`.
- Apply standard labels (`app`, `environment`, `version`).

## Optional (off unless enabled)

- `helm test` after install, only when the chart defines test pods.
- HPA/VPA, only when metrics-server is available.
- Istio or Linkerd sidecars, only when a service mesh is deployed.
- ArgoCD or Flux patterns, only when GitOps tooling exists.

## Output

- **Before**: requirements, current state (existing resources), cluster context (namespace, environment), safety checks (dry-run, context).
- **During**: show kubectl/helm commands, manifests, command output, pod status and events.
- **After**: resources created or updated, health checks verified, services reachable, pods running, plus `kubectl get pods -n <namespace>` output as proof.
- Implementation Schema details: [output-schemas.md](../../../shared-patterns/output-schemas.md).

## Error handling

| Error | Cause | Fix |
|---|---|---|
| ImagePullBackOff | Wrong image name, missing credentials, private registry auth | Check the image name, confirm the image exists, create or update `imagePullSecrets`, check node connectivity to the registry |
| CrashLoopBackOff | App error, missing dependencies, limits too low | `kubectl logs <pod>` (and `--previous`), check resource limits, env vars and config, make sure probes are not too aggressive |
| PVC Pending | No matching PV, storage class misconfigured, provisioner down | Check the storage class exists and is default, CSI driver pods run, provisioner logs, enough capacity |

Full pod-state table and the Helm validation pipeline: [kubernetes-helm/k8s-helm-quick-reference.md](kubernetes-helm/k8s-helm-quick-reference.md).

## Preferred patterns

- **Set requests and limits**: `resources: {requests: {cpu: "100m", memory: "128Mi"}, limits: {cpu: "200m", memory: "256Mi"}}`. Pods without them can starve the node and break scheduling.
- **Configure probes**: `livenessProbe: {httpGet: {path: /health, port: 8080}, periodSeconds: 10}` plus a readinessProbe. Without probes Kubernetes sends traffic to broken pods and never restarts them.
- **Pin image tags**: `image: myapp:v1.2.3` or a commit SHA. `:latest` in production can't be rolled back and hides what is deployed.

## Rationalizations to reject

| Claim | Why it's wrong | Do this |
|---|---|---|
| "Small apps don't need resource limits" | Any pod can consume all node resources | Always set requests and limits |
| "Health checks slow down deployment" | They keep traffic off unhealthy pods | Add liveness and readiness probes |
| "We can apply directly without dry-run" | Mistakes go straight to production | Always dry-run first |
| "`latest` is fine, we update often" | No rollback, unclear state | Use version tags |
| "We'll add monitoring later" | Hard to debug without observability | Add basic monitoring from the start |

## Hard gates

Before applying changes, check for these. If found: stop, report, fix before continuing.

| Pattern | Why blocked | Fix |
|---|---|---|
| No resource requests/limits | Node instability, scheduling issues | Add requests/limits to all containers |
| Missing health probes | Traffic to unhealthy pods | Add liveness/readiness probes |
| `:latest` tag in production | Non-deterministic deployments | Use version tags `:v1.2.3` |
| No namespace specified | Deploys to default, conflicts | Always specify namespace |
| No rollback plan | Can't recover from a bad deploy | Dry-run, keep the previous version ready |

```bash
# Pods without resource limits
kubectl get pods --all-namespaces -o json | jq '.items[] | select(.spec.containers[].resources.limits == null) | .metadata.name'
# Deployments using :latest
kubectl get deployments --all-namespaces -o json | jq '.items[] | select(.spec.template.spec.containers[].image | endswith(":latest")) | .metadata.name'
# Pods without health checks
kubectl get pods --all-namespaces -o json | jq '.items[] | select(.spec.containers[].livenessProbe == null) | .metadata.name'
```

## Verification stops

- After changing a chart or manifest: have I validated it against the deployed state? Config changes without checking what runs now are speculation.
- After recommending limit, scaling, or node pool changes: do I give before/after metrics (current use vs proposed limits), or say why measurement is impossible? Unmeasured resource changes cause waste or outages.
- After any deployment change: have I checked dependents (deployments that reference this service name, ingress rules, network policies, ConfigMaps used by other pods)?

## Before destructive or live changes

- Before deleting a namespace or PVC, scaling to 0, or removing a StatefulSet: confirm it is reversible or backups exist. Deleting a PVC without backup loses data permanently; deleting a namespace removes everything in it.
- Before applying to a live cluster: validate with `--dry-run=server` (not only client) and `helm template`. An invalid field in a production manifest fails pods immediately.

## Recommendation format

Each recommendation names the **component** (Deployment, Service, ConfigMap, or other resource), **current state** (or "new"), **proposed state**, and **risk level** (Low, Medium, High) with a short reason.

## Blockers

Resolve routine issues from repository evidence and existing authorization. When sure, decide, record the assumption, and continue; ask Jev when genuinely unsure. Rows marked **(owner)** guard production, destructive, credential, public-exposure, or persistence actions: get explicit owner confirmation first.

| Situation | Why stop | Ask |
|---|---|---|
| kubectl context unclear **(owner)** | Wrong cluster is a disaster | "Current context is X. Is this the correct cluster?" |
| Production namespace **(owner)** | Safety critical | "This is the production namespace. Confirm deployment?" |
| Breaking change **(owner)** | Service disruption | "This changes service port/selector and causes downtime. Proceed?" |
| Storage class choice | Performance and cost | "Which storage class: fast (SSD) or standard (HDD)?" |
| Ingress controller unknown | Several options | "Which ingress: nginx, traefik, or istio gateway?" |

Decide explicitly before acting: kubectl context and production vs staging (owner confirms both), storage class (performance and cost), ingress controller (routing strategy).

## Reference loading table

| Signal | Load | Why |
|---|---|---|
| Pod failures, CrashLoopBackOff, OOMKilled, helm upgrade, deploy safety | [kubernetes-helm/k8s-helm-quick-reference.md](kubernetes-helm/k8s-helm-quick-reference.md) | Pod state diagnosis table, Helm chart validation pipeline |
