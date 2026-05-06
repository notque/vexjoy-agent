# Network Policies

> **Scope**: Default-deny NetworkPolicy YAML, allow-list patterns, DNS egress rules, and namespace isolation
> **Version range**: Kubernetes 1.26+ (NetworkPolicy v1 stable)
> **Generated**: 2026-04-16 — verify against current Kubernetes Network Policies documentation

---

## Overview

Start with a default-deny policy for both ingress and egress in every namespace. Apply this on day one, not later. Without network policies, lateral movement between compromised pods is trivial.

---

## Default Deny All Traffic

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

---

## Allow-List: Frontend to Backend

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

---

## DNS Egress (Required for Service Discovery)

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

---

## Error Handling

### Error: NetworkPolicy blocking legitimate traffic
Cause: Default-deny is in place but the allow-list rule is missing or has incorrect label selectors.
Solution: Verify pod labels match the NetworkPolicy `podSelector` and `from`/`to` selectors. Use `kubectl describe networkpolicy` to inspect rules.
