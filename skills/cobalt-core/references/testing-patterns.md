# Cobalt Core — Testing Patterns

> **Scope**: Unit testing with moq-generated mocks and E2E testing with Kind clusters, as used in kvm-exporter. Does not cover general Go testing theory.
> **Version range**: Go 1.21+, moq 0.5.0, Kind 0.23+
> **Generated**: 2026-04-16 — verify against `test/` and `internal/libvirt/*_test.go`

---

## Overview

kvm-exporter has two test layers: unit tests using `moq`-generated interface mocks (fast, no libvirt), and E2E tests using a custom Kind cluster image with actual libvirt + Cloud Hypervisor running (slow, requires Docker). The unit test pattern is interface injection — `ServiceImpl` accepts mock `LibVirt` and `Cloudhypervisor` dependencies. The E2E layer validates that expected metrics actually appear in the HTTP response. Skipping the race detector on unit tests is the most common error that lets concurrency bugs through.

---

## Pattern Table

| Tool | Version | Use When | Avoid When |
|------|---------|----------|------------|
| `moq` | 0.5.0 | Generate mocks for `LibVirt`, `Cloudhypervisor` interfaces | Hand-rolling mocks (use `moq` for regeneration) |
| `testify/assert` | All | Readable assertion failures | `t.Fatalf` for non-fatal checks |
| `go test -race` | All | All concurrent code; CI always | Benchmarks (adds overhead) |
| Kind E2E | 0.23+ | Validating actual metric output end-to-end | Unit-testable logic (too slow) |
| `test/test-metrics.sh` | — | HTTP response metric validation in E2E | Go test for HTTP parsing |

---

## Correct Patterns

### Unit Test: Interface Injection with moq

Create `ServiceImpl` with mocked interfaces, inject a metric channel, call the collector, verify emitted metrics.

```go
func TestVcpuCollector(t *testing.T) {
    virt := &LibVirtMock{
        ConnectGetAllDomainStatsFunc: func(...) ([]libvirt.DomainStats, error) {
            return []libvirt.DomainStats{
                {
                    Domain: libvirt.Domain{Name: "test-domain"},
                    Vcpu:   []libvirt.DomainStatsVcpu{{State: 1, Time: 1000}},
                },
            }, nil
        },
    }

    svc := &ServiceImpl{virt: virt}
    ch := make(chan prometheus.Metric, 10)

    svc.collectVcpu(context.Background(), ch)
    close(ch)

    var metrics []prometheus.Metric
    for m := range ch {
        metrics = append(metrics, m)
    }
    assert.NotEmpty(t, metrics, "expected at least one vcpu metric")
}
```

**Why**: No libvirt socket required. The mock records call arguments so you can assert the RPC was called with correct parameters. Regenerate with `make generate` after interface changes.

---

### Regenerating Mocks After Interface Change

After modifying `LibVirt` or `Cloudhypervisor` interfaces, regenerate mocks:

```bash
# In repo root
make generate
# or directly:
moq -out internal/libvirt/interface_mock_gen.go \
    internal/libvirt LibVirt Cloudhypervisor
```

The generated file is committed — never edit `interface_mock_gen.go` by hand.

**Why**: Hand-edited mocks drift from the interface. `moq` regeneration guarantees the mock matches the interface exactly, and CI will fail if the generated file is out of sync.

---

### E2E Test: Kind Cluster + metric validation

The E2E setup creates a Kind cluster with a custom node image containing libvirt and Cloud Hypervisor. VMs are created on worker nodes, the exporter DaemonSet is deployed, and metrics are validated via HTTP.

```bash
# Full E2E (QEMU + CH paths):
make test-all

# QEMU path only:
make test-qemu

# CH path only:
make test-ch

# Manual metric check against running exporter:
curl -s http://NODE_IP:8080/metrics | grep 'kvm_domain_libvirt_vcpu'
```

Metric validation script (`test/test-metrics.sh`) uses grep patterns against the HTTP response — add expected metrics there when adding new collectors.

```bash
# Add to test/test-metrics.sh for a new metric:
check_metric "kvm_domain_libvirt_new_metric_name"
```

**Why**: The unit tests mock libvirt responses. The E2E layer validates that the actual libvirt RPC, cgroup reads, and /proc parsing produce real metrics. It's the only layer that catches libvirt version incompatibilities.

---

### Race-Detector-Clean Tests

Always run the race detector in CI. For local development, add `-race` to catch issues before push.

```bash
# Run with race detector
go test -race ./internal/...

# Run specific test with race detector
go test -race -run TestCollectVcpu ./internal/libvirt/

# Run with verbose output and race detector
go test -race -v ./internal/libvirt/
```

When using `sync.Map` or channels in tests, the race detector validates the access patterns are safe.

---

## Pattern Catalog

### ❌ Hand-Editing interface_mock_gen.go

**Detection**:
```bash
git log --oneline internal/libvirt/interface_mock_gen.go
grep -n "hand" internal/libvirt/interface_mock_gen.go
rg 'interface_mock_gen' --type go
```
Check if the file has commits that don't come from `make generate`.

**What it looks like**:
```go
// In interface_mock_gen.go — manually added method:
func (m *LibVirtMock) NewMethod(ctx context.Context) error {
    // hand-written — not from moq
    return nil
}
```

**Why wrong**: The next `make generate` overwrites the file. The hand-written method disappears silently. Tests that relied on it compile but the mock no longer has the behavior.

**Fix**: Extend the actual `LibVirt` interface, then run `make generate`. The mock is always derived from the interface.

---

### ❌ Skipping Race Detector in Tests with Goroutines

**Detection**:
```bash
rg 'go test' Makefile
grep -n "go test" Makefile
```
Check that all `go test` invocations in Makefile include `-race`.

**What it looks like**:
```makefile
test:
    go test ./internal/...   # no -race
```

**Why wrong**: kvm-exporter's domain collection is concurrent. Tests that exercise collection without `-race` can pass even with data races — the race detector is not enabled by default. Race conditions surface only under load in production.

**Fix**:
```makefile
test:
    go test -race ./internal/...
```

**Version note**: `-race` requires CGO on Linux. Since kvm-exporter already requires `CGO_ENABLED=1` for libvirt, this is always available.

---

### ❌ Asserting Exact Metric Count Instead of Presence

**Detection**:
```bash
rg 'assert\.Len\(t, metrics' --type go internal/
grep -n "assert.Len" internal/libvirt/*_test.go
```

**What it looks like**:
```go
assert.Len(t, metrics, 3, "expected exactly 3 metrics")
```

**Why wrong**: Adding a label to an existing metric (e.g., adding `numa_node` label to steal time) changes the cardinality. The exact-count assertion breaks, but the metric is still correct. Tests become a maintenance burden.

**Fix**: Assert metric presence and specific label values rather than total count:
```go
assert.NotEmpty(t, metrics)
// Find the specific metric you care about:
found := false
for _, m := range metrics {
    if strings.Contains(m.Desc().String(), "kvm_domain_libvirt_steal_time") {
        found = true
    }
}
assert.True(t, found, "steal time metric must be present")
```

---

### ❌ E2E Tests Without test-metrics.sh Coverage for New Collectors

**Detection**:
```bash
grep -n "check_metric" test/test-metrics.sh
# Compare against collector list in DISABLED_COLLECTORS docs
```
If a new collector name does not appear in `test-metrics.sh`, its E2E coverage is missing.

**What it looks like**:
New collector `hugepages` is added to `internal/libvirt/hugepages.go` but `test/test-metrics.sh` has no `check_metric "kvm_domain_hugepages_bytes"` line.

**Why wrong**: Unit tests cover the mock path. The E2E cluster deploys the exporter against real VMs. If hugepages collection silently returns no metrics (e.g., smaps not readable), no test catches it.

**Fix**: For every new collector, add at minimum one `check_metric "kvm_..."` line to `test/test-metrics.sh` targeting the primary metric the collector emits.

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|-------|-----------|-----|
| `undefined: LibVirtMock` | `interface_mock_gen.go` not regenerated after interface change | Run `make generate` |
| `DATA RACE` in `go test -race` | Goroutine-per-domain accessing shared state without sync | Check `sync.Map` usage; add mutex if using plain map |
| `no such file or directory: /run/libvirt/libvirt-sock-ro` (unit test) | Test code directly instantiating real libvirt connection | Inject mock via interface; never connect to real libvirt in unit tests |
| E2E `make test-all` fails at Kind node image build | Custom Kind Dockerfile outdated after Ubuntu/libvirt version bump | Rebuild base image: `make build-test-image` |
| `check_metric` fails in `test-metrics.sh` | New collector not returning metrics in E2E cluster | Check collector enabled/disabled status; add debug logging; validate cgroup paths on Kind node |

---

## Detection Commands Reference

```bash
# Check if race detector is in Makefile test targets
grep -n "go test" Makefile

# Find any test that skips -race
rg 'go test [^-]' Makefile

# Find hand-edits to generated mock file
git log --oneline internal/libvirt/interface_mock_gen.go

# Find exact-count metric assertions (fragile)
rg 'assert\.Len\(t, metrics' --type go internal/

# Find uncovered collectors in E2E script
grep "check_metric" test/test-metrics.sh

# Run unit tests with race detector
go test -race -v ./internal/...
```

---

## See Also

- `references/kvm-exporter.md` — Testing section for E2E infrastructure setup and `make test-all` targets
- `references/concurrency-patterns.md` — Concurrency patterns that need race-detector-clean tests
