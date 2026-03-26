---
name: kubernetes-security
description: Kubernetes security patterns including RBAC, PodSecurityStandards, network policies, and secret management
version: 1.0.0
user-invocable: false
context: fork
agent: kubernetes-helm-engineer
---

# Kubernetes Security Skill

## Operator Context

This skill operates as an operator for Kubernetes security hardening workflows, configuring Claude's behavior for secure-by-default cluster and workload configurations. It encodes RBAC, pod security, network isolation, secret management, and supply chain security as non-negotiable constraints.

### Hardcoded Behaviors (Always Apply)
- **Least Privilege**: Every Role, ClusterRole, and ServiceAccount gets only the permissions it needs -- never wildcards in production
- **No Privileged Containers**: Containers must not run as privileged or with elevated capabilities unless explicitly justified
- **No Plain-Text Secrets**: Never store secrets in ConfigMaps, environment variables from manifests, or checked-in YAML
- **Network Deny-by-Default**: Namespaces should have a default-deny NetworkPolicy before allow rules are added
- **Non-Root by Default**: All containers run as non-root with a read-only root filesystem unless there is a documented exception

---

## Instructions

### Step 1: RBAC -- Least-Privilege Roles and Bindings

Grant the minimum permissions required. Prefer namespace-scoped Roles over ClusterRoles.

```yaml
# Good: namespace-scoped Role with specific verbs and resources
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

```yaml
# Bind the Role to a specific ServiceAccount, not a user or group wildcard
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  namespace: app-team
  name: deployment-reader-binding
subjects:
  - kind: ServiceAccount
    name: ci-deployer
    namespace: app-team
roleRef:
  kind: Role
  name: deployment-reader
  apiGroup: rbac.authorization.k8s.io
```

ServiceAccount best practices:
- Create dedicated ServiceAccounts per workload -- never use the `default` account
- Set `automountServiceAccountToken: false` on pods that do not need the Kubernetes API
- Regularly audit which ServiceAccounts have ClusterRole bindings

### Step 2: PodSecurityStandards -- Baseline vs Restricted

Kubernetes PodSecurity admission replaces the deprecated PodSecurityPolicy. Apply labels at the namespace level.

```yaml
# Enforce restricted profile, warn on baseline violations
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/audit: restricted
```

SecurityContext for a restricted-compliant pod:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: secure-app
spec:
  securityContext:
    runAsNonRoot: true
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: app
      image: registry.example.com/app:v1.2.3@sha256:abc123
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        runAsUser: 1000
        runAsGroup: 1000
        capabilities:
          drop: ["ALL"]
      resources:
        limits:
          memory: "256Mi"
          cpu: "500m"
        requests:
          memory: "128Mi"
          cpu: "100m"
```

Key differences:
- **Baseline** -- blocks known privilege escalations (hostNetwork, privileged, hostPID) but allows running as root
- **Restricted** -- enforces non-root, drops all capabilities, requires seccomp profile, disallows privilege escalation

### Step 3: Network Policies -- Default Deny and Allow-Lists

Start with a default-deny policy for both ingress and egress in every namespace.

```yaml
# Default deny all traffic in the namespace
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: production
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
```

Then add specific allow rules:

```yaml
# Allow frontend pods to reach backend on port 8080
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend-to-backend
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: frontend
      ports:
        - protocol: TCP
          port: 8080
```

```yaml
# Allow DNS egress for all pods (required for service discovery)
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
    - to: []
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
```

### Step 4: Secret Management

Never use plain Kubernetes Secrets checked into Git. Use one of these approaches:

**Sealed Secrets** -- encrypts secrets client-side so they are safe in Git:

```bash
# Encrypt a secret with kubeseal
kubectl create secret generic db-creds \
  --from-literal=password=supersecret \
  --dry-run=client -o yaml | \
  kubeseal --format yaml > sealed-db-creds.yaml
```

**External Secrets Operator** -- syncs secrets from external vaults:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: db-credentials
  namespace: production
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: ClusterSecretStore
  target:
    name: db-credentials
  data:
    - secretKey: password
      remoteRef:
        key: secret/data/production/db
        property: password
```

Avoid these patterns:
- Mounting secrets as environment variables in the pod spec (visible in `kubectl describe pod`)
- Storing secrets in ConfigMaps
- Hardcoding credentials in container images or Dockerfiles

### Step 5: Image Security

Build minimal, non-root container images:

```dockerfile
# Use distroless or minimal base images
FROM gcr.io/distroless/static-debian12:nonroot
COPY --chown=65532:65532 app /app
USER 65532:65532
ENTRYPOINT ["/app"]
```

Requirements:
- **Non-root user**: Always set `USER` in the Dockerfile and `runAsNonRoot: true` in the SecurityContext
- **Read-only root filesystem**: Use `readOnlyRootFilesystem: true` and mount writable volumes only where needed
- **Distroless or scratch**: No shell, no package manager -- reduces attack surface
- **Pin image digests**: Use `image:tag@sha256:...` to prevent tag mutation attacks
- **Scan images**: Run Trivy, Grype, or Snyk in CI before pushing to registry

### Step 6: Supply Chain Security

**Image signing with cosign:**

```bash
# Sign an image after building
cosign sign --key cosign.key registry.example.com/app:v1.2.3@sha256:abc123

# Verify before deploying
cosign verify --key cosign.pub registry.example.com/app:v1.2.3@sha256:abc123
```

**Admission controllers** to enforce policy at deploy time:
- **Kyverno** or **OPA Gatekeeper** -- reject pods that violate security policies
- **Sigstore Policy Controller** -- verify image signatures before admission

Example Kyverno policy to require non-root containers:

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-run-as-nonroot
spec:
  validationFailureAction: Enforce
  rules:
    - name: run-as-non-root
      match:
        any:
          - resources:
              kinds:
                - Pod
      validate:
        message: "Containers must run as non-root"
        pattern:
          spec:
            containers:
              - securityContext:
                  runAsNonRoot: true
```

### Step 7: Detect Common Misconfigurations

Watch for these frequent security mistakes:

| Misconfiguration | Risk | Fix |
|------------------|------|-----|
| `privileged: true` | Full host access | Remove or use specific capabilities |
| `hostNetwork: true` | Pod shares host network stack | Use CNI networking |
| `hostPID: true` / `hostIPC: true` | Can see/signal host processes | Remove unless debugging |
| Wildcard RBAC verbs (`*`) | Grants all operations | List specific verbs |
| `automountServiceAccountToken: true` on workloads | Token exposed to compromised pod | Set to `false` unless API access needed |
| No resource limits | Pod can exhaust node resources (DoS) | Set CPU and memory limits |
| Latest tag without digest | Image can change without notice | Pin by digest |
| Secrets as env vars in pod spec | Visible in `kubectl describe` | Mount as files or use external secrets |

---

## Error Handling

### Error: Pod rejected by PodSecurity admission
Cause: Pod spec violates the namespace's PodSecurity level (e.g., missing `runAsNonRoot`, `privileged: true`).
Solution: Check the admission warning message, then update the pod's SecurityContext to comply with the enforced level.

### Error: NetworkPolicy blocking legitimate traffic
Cause: Default-deny is in place but the allow-list rule is missing or has incorrect label selectors.
Solution: Verify pod labels match the NetworkPolicy `podSelector` and `from`/`to` selectors. Use `kubectl describe networkpolicy` to inspect rules.

### Error: RBAC "forbidden" errors in application logs
Cause: ServiceAccount lacks required permissions.
Solution: Identify the API group, resource, and verb from the error message. Create or update a Role with the exact permissions needed -- do not add wildcards.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Privileged mode is faster to debug" | Grants full host access to attacker if pod is compromised | Use specific capabilities or debug containers |
| "Wildcard RBAC is fine for dev" | Dev clusters get promoted; habits carry | Write exact verbs and resources |
| "Secrets in env vars are convenient" | Visible in process listing, logs, kubectl describe | Mount as files or use external-secrets |
| "We'll add network policies later" | Lateral movement is trivial without them | Default-deny from day one |
| "Non-root breaks our app" | Almost never true; app just needs writable /tmp | Add an emptyDir volume for /tmp |
