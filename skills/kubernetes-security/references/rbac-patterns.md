# RBAC Patterns

> **Scope**: Role, RoleBinding, ClusterRole YAML manifests and ServiceAccount best practices for least-privilege Kubernetes access control
> **Version range**: Kubernetes 1.26+ (RBAC v1 stable)
> **Generated**: 2026-04-16 — verify against current Kubernetes RBAC documentation

---

## Overview

RBAC (Role-Based Access Control) is the primary authorization mechanism in Kubernetes. Grant the minimum permissions required. Prefer namespace-scoped Roles over ClusterRoles. Write exact verbs and resources in production. Even in dev clusters, because dev habits carry forward and dev manifests get promoted. Write exact verbs and resources every time.

---

## Namespace-Scoped Role

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

---

## RoleBinding

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

---

## ServiceAccount Best Practices

- Create dedicated ServiceAccounts per workload
- Set `automountServiceAccountToken: false` on pods that have no need for Kubernetes API access
- Regularly audit which ServiceAccounts have ClusterRole bindings

---

## Error Handling

### Error: RBAC "access denied" errors in application logs
Cause: ServiceAccount lacks required permissions.
Solution: Identify the API group, resource, and verb from the error message. Create or update a Role with the exact permissions needed. List specific verbs and resources.
