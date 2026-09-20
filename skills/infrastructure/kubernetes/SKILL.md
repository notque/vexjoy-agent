---
name: kubernetes
description: "Kubernetes diagnosis plus repository-specific CobaltCore/KVM exporter architecture, concurrency, metrics, and tests."
user-invocable: false
context: fork
agent: kubernetes-helm-engineer
routing:
  triggers: ["kubernetes debug", "pod failure", "kubectl logs", "OOMKilled", "k8s RBAC", "network policy", "cobaltcore", "kvm-exporter", "hypervisor metrics"]
  category: kubernetes
---

# Kubernetes

Always name the namespace in `kubectl` commands. Gather read-only evidence before proposing changes; use `--previous` for restarted containers because current logs may hide the crash.

For ordinary Kubernetes debugging or security, rely on current Kubernetes knowledge and live cluster evidence. Do not apply generic manifests blindly: inspect workload/controller ownership, events, selectors/endpoints, policies, requests/limits, and server-supported API versions. Verify with the same symptom probe used before the change.

## CobaltCore / kvm-exporter

This repository-specific domain is the reason to load this skill:

- Architecture, exact collector/config names, metric catalog, QEMU versus Cloud Hypervisor behavior, deployment, alerts, and CI: `references/cobalt-kvm-exporter.md`.
- Concurrency invariants and review probes: `references/cobalt-concurrency-patterns.md`.
- Mock generation, race/E2E commands, and collector coverage contract: `references/cobalt-testing-patterns.md`.

Load only the relevant reference. Pair code changes with the repository's Go patterns and metric conventions rather than generic exporter templates.
