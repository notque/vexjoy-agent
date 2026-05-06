# Pod Security

> **Scope**: PodSecurityStandards (Baseline, Restricted, Privileged), SecurityContext configuration, non-root enforcement, and image hardening
> **Version range**: Kubernetes 1.25+ (PodSecurity admission GA, PodSecurityPolicy removed)
> **Generated**: 2026-04-16 — verify against current Kubernetes Pod Security Standards documentation

---

## Overview

Kubernetes PodSecurity admission replaces the deprecated PodSecurityPolicy. Apply labels at the namespace level. All containers must run as non-root with a read-only root filesystem unless there is a documented exception. If an app claims it needs root, it usually just needs a writable `/tmp`, which an emptyDir volume solves.

---

## Namespace-Level PodSecurity Labels

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

---

## Restricted-Compliant Pod SecurityContext

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

---

## PodSecurity Levels

- **Baseline** — blocks known privilege escalations (hostNetwork, privileged, hostPID) but allows running as root
- **Restricted** — enforces non-root, drops all capabilities, requires seccomp profile, disallows privilege escalation

---

## Image Hardening

Containers should never run as privileged or with elevated capabilities unless explicitly justified. Privileged mode grants full host access to an attacker if the pod is compromised. Use specific capabilities or debug containers instead.

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
- **Distroless or scratch**: No shell, no package manager — reduces attack surface
- **Pin image digests**: Use `image:tag@sha256:...` to prevent tag mutation attacks
- **Scan images**: Run Trivy, Grype, or Snyk in CI before pushing to registry

---

## Error Handling

### Error: Pod rejected by PodSecurity admission
Cause: Pod spec violates the namespace's PodSecurity level (e.g., missing `runAsNonRoot`, `privileged: true`).
Solution: Check the admission warning message, then update the pod's SecurityContext to comply with the enforced level.
