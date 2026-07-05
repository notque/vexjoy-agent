# Kubernetes Security Process

Harden Kubernetes clusters and workloads through RBAC, pod security, network isolation, secret management, and supply chain controls.

## Domain Routing

| Domain | Reference |
|--------|-----------|
| Access control, permissions, roles | `rbac-patterns.md` |
| Pod hardening, container security | `pod-security.md` |
| Network isolation, traffic rules | `network-policies.md` |
| Image signing, secrets, admission control | `supply-chain.md` |

If the question spans multiple domains, load all relevant references. Most production hardening touches at least RBAC + pod security.

For general Kubernetes debugging, see `kubernetes-debugging.md`.
