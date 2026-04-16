# Supply Chain Security

> **Scope**: Image signing with cosign, admission controllers (Kyverno, OPA Gatekeeper), secret management (Sealed Secrets, External Secrets Operator), and common misconfiguration detection
> **Version range**: cosign v2+, Kyverno v1.10+, External Secrets Operator v0.9+
> **Generated**: 2026-04-16 — verify against current tool documentation

---

## Overview

Supply chain security covers image provenance, admission-time policy enforcement, secret management, and misconfiguration detection. These controls complement RBAC, pod security, and network policies by securing the software delivery pipeline and runtime configuration.

---

## Image Signing with cosign

```bash
# Sign an image after building
cosign sign --key cosign.key registry.example.com/app:v1.2.3@sha256:abc123

# Verify before deploying
cosign verify --key cosign.pub registry.example.com/app:v1.2.3@sha256:abc123
```

---

## Admission Controllers

Enforce policy at deploy time:
- **Kyverno** or **OPA Gatekeeper** — reject pods that violate security policies
- **Sigstore Policy Controller** — verify image signatures before admission

### Kyverno Policy: Require Non-Root Containers

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

---

## Secret Management

Store secrets using Sealed Secrets or External Secrets Operator, not environment variables from manifests or checked-in YAML. Secrets exposed as env vars are visible in `kubectl describe pod` output, which makes them trivially discoverable after any pod compromise.

### Sealed Secrets

Encrypts secrets client-side so they are safe in Git:

```bash
# Encrypt a secret with kubeseal
kubectl create secret generic db-creds \
  --from-literal=password=supersecret \
  --dry-run=client -o yaml | \
  kubeseal --format yaml > sealed-db-creds.yaml
```

### External Secrets Operator

Syncs secrets from external vaults:

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

### Anti-Patterns (Do Not Use)

- Mounting secrets as environment variables in the pod spec (visible in `kubectl describe pod`)
- Storing secrets in ConfigMaps
- Hardcoding credentials in container images or Dockerfiles

---

## Common Misconfiguration Detection

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
