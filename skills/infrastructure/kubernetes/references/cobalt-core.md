# Cobalt Core

Domain knowledge for the cobaltcore-dev project family — SAP Converged Cloud infrastructure components for KVM hypervisor management, metrics collection, and compute-node tooling.

## Component Table

| Component | Repository | Reference |
|-----------|-----------|-----------|
| KVM Exporter | `cobaltcore-dev/kvm-exporter` | `cobalt-kvm-exporter.md` |

## Implementation Pairing

- Go code patterns: pair with `go-patterns` skill
- Prometheus/Grafana: pair with `prometheus-grafana-engineer`
- Kubernetes deployment: this skill covers it

## Extension Process

To add a new cobaltcore repo:
1. Analyze repo systematically (README, go.mod, source, Dockerfile, Helm)
2. Create reference file at `references/cobalt-{repo-name}.md`
3. Update the Reference Loading Table in SKILL.md
