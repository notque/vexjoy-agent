---
name: cobalt-core
description: "Cobalt Core infrastructure knowledge: KVM exporters, hypervisor tooling, OpenStack compute."
agent: kubernetes-helm-engineer
user-invocable: true
argument-hint: "<cobaltcore topic or repo name>"
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Agent
  - Edit
  - Write
routing:
  triggers:
    - "cobalt core"
    - "cobaltcore"
    - "kvm-exporter"
    - "kvm exporter"
    - "hypervisor metrics"
    - "libvirt exporter"
    - "cloud hypervisor"
  category: infrastructure
  pairs_with:
    - go-patterns
    - prometheus-grafana-engineer
    - kubernetes-helm-engineer
---

# Cobalt Core

Domain skill for [cobaltcore-dev](https://github.com/cobaltcore-dev) -- SAP Converged Cloud infrastructure for KVM hypervisor management, metrics collection, and compute-node tooling.

## Reference Loading Table

| Signal | Reference | Size |
|--------|-----------|------|
| kvm-exporter, metrics, prometheus, libvirt, hypervisor, collector, scrape, steal time, NUMA, cgroups, cloud hypervisor | `references/kvm-exporter.md` | ~800 lines |
| goroutine, concurrency, semaphore, TryLock, sync.Map, race condition, socket exhaustion, scrape overlap, ClearScrapeCache | `references/concurrency-patterns.md` | ~200 lines |
| test, mock, moq, unit test, E2E, Kind cluster, race detector, interface_mock_gen, test-metrics.sh | `references/testing-patterns.md` | ~200 lines |

**Load greedily.** If the question touches any signal keyword, load the matching reference before responding. Multiple matches = load all.

---

## Phase 1: IDENTIFY

Determine which cobaltcore component the user is asking about.

| Component | Repository | Reference |
|-----------|-----------|-----------|
| KVM Exporter | `cobaltcore-dev/kvm-exporter` | `references/kvm-exporter.md` |

If not listed, tell the user no reference exists yet and offer to analyze the repo.

**Gate**: Component identified. Reference loaded.

---

## Phase 2: RESPOND

Use loaded reference knowledge to answer. References contain: architecture and data flow, metric catalogs with types/labels/descriptions, configuration and env vars, deployment models (Helm, DaemonSet), code patterns (concurrency, caching, error handling), testing strategies (unit mocks, E2E with Kind), alerting rules and ops concerns.

For Go code questions, pair with `go-patterns`. For Prometheus/Grafana, pair with `prometheus-grafana-engineer`. For K8s deployment, pair with `kubernetes-helm-engineer`.

**Gate**: Question answered with reference-backed specifics, not generic advice.

---

## Phase 3: EXTEND

When adding a new cobaltcore repo:
1. Analyze systematically (README, go.mod, key source files, Dockerfile, Helm chart)
2. Create reference at `references/{repo-name}.md`
3. Update Reference Loading Table in this SKILL.md
4. Update component table in Phase 1

Follow structure in `references/kvm-exporter.md`.
