# kvm-exporter Reference

Repository: [cobaltcore-dev/kvm-exporter](https://github.com/cobaltcore-dev/kvm-exporter)
Language: Go 1.23+ (module `github.com/cobaltcore-dev/kvm-exporter`)
License: Apache-2.0
Current version: 1.3.0 (Helm chart 0.3.8)

Prometheus metrics exporter collecting hypervisor-level statistics from KVM hosts running QEMU or Cloud Hypervisor (CH). Gathers data via libvirt, cgroups v2, `/proc`, and CH HTTP socket API. Designed for SAP Converged Cloud OpenStack Nova compute nodes.

---

## Architecture

### Directory Structure

```
cmd/
  server/main.go          # Entry point — HTTP server with chi router
  playground/main.go      # Development playground
internal/
  config/                 # Environment-based configuration (envconfig)
  globals/                # HTTP endpoint constants
  libvirt/                # Core: all collectors, CH integration, metrics
  log/                    # Structured logging (logrus wrapper)
  middlewares/            # HTTP readiness probe middleware
  numareader/             # NUMA topology reader (/proc/pid/numa_maps, sysfs numastat)
  procreader/             # Process reader (/proc: schedstat, cmdline)
chart/                    # Helm chart (DaemonSet, ServiceMonitor, alerts, dashboards)
config/                   # Kustomize deployment configs
test/                     # E2E infrastructure (Kind cluster with VMs)
```

### Data Flow

```
                              Prometheus scrape
                                    |
                               GET /metrics
                                    |
                            promhttp.Handler()
                                    |
                          ServiceImpl.Collect()
                                    |
                          RetrieveMetrics(ctx)
                                    |
          +-----------+-------------+----------+-----------+
          |           |             |          |           |
      libvirt     cgroups v2    /proc fs    CH socket   sysfs
      (RPC)       (cgroup2)    (procreader) (HTTP API)  (numa)
          |           |             |          |           |
          +-----------+-------------+----------+-----------+
                                    |
                          chan<- prometheus.Metric
```

### Entry Point (`cmd/server/main.go`)

1. Reads config via `config.ReadConfig()` (env vars + optional libvirt.conf)
2. Sets GC to 50%, memory limit to 450 MiB (tuned for memory-constrained pods)
3. Creates `libvirt.ServiceImpl` (the Prometheus collector)
4. Registers with `prometheus.MustRegister()`
5. Sets up chi router: `/health`, `/ready`, `/metrics`, `/debug/pprof/*` (optional)
6. Starts HTTP server (default port 8080)
7. Graceful shutdown on SIGINT/SIGTERM

### Collector Architecture

`ServiceImpl` implements `prometheus.Collector` (Describe/Collect). On each scrape:

1. **Connect** to libvirt via Unix socket if not connected
2. **List all domains** (active + inactive) via `ConnectListAllDomains`
3. **Parallel /proc scan** — `UpdateAllProcesses()` finds VM processes
4. **Bulk domain stats** — single `ConnectGetAllDomainStats` RPC (QEMU only)
5. **Concurrent domain collection** — goroutines per domain (semaphore-limited to 50):
   domain info, vCPU, block, network, memory, uptime, steal time, hugepages, NUMA
6. **Node-level collection** — storage pools, libvirt version, NIC bonding, CPU SMT, host NUMA
7. **Stale cleanup** — remove cached data for inactive domains
8. **Aggregation** — weighted average steal time across all domains

### Performance Optimizations

| Technique | Purpose |
|-----------|---------|
| Bulk `ConnectGetAllDomainStats` | Replace N per-domain RPCs with one call |
| XML cache (5-min TTL) | Eliminate XML desc RPCs per scrape |
| Block I/O tune cache (5-min TTL) | Reduce I/O tune lookups |
| Concurrency semaphore (50 goroutines) | Prevent libvirt socket exhaustion |
| Collection timeout (40s) | Context cancellation on slow scrapes |
| `sync.Mutex.TryLock()` | Prevent overlapping scrapes |
| `debug.FreeOSMemory()` | Explicit memory return after collection |

---

## Configuration

All via environment variables (`kelseyhightower/envconfig`):

| Env Variable | Type | Default | Purpose |
|---|---|---|---|
| `SERVICE_NAME` | string | `kvm-exporter` | Service identifier in logs |
| `APP` | string | `kvm-exporter` | Application name |
| `ENV` | string | `LOCAL` | Environment (LOCAL = debug text, else JSON info) |
| `PORT` | int | `8080` | HTTP listen port |
| `LIBVIRT_SOCKET` | string | `/run/libvirt/libvirt-sock-ro` | Libvirt Unix socket path |
| `LIBVIRT_URI` | string | `ch:///system` | Libvirt connection URI |
| `LIBVIRT_CONF_PATH` | string | `/etc/libvirt/libvirt.conf` | Optional libvirt config |
| `CLOUDHYPERVISOR_SOCKET_PATH` | string | `/run/libvirt/ch` | CH socket base directory |
| `EXTERNAL_MOUNT_PATHS` | []string | `/var/lib/nova/mnt,/var/lib/nova/instances` | Disk usage mount paths |
| `DISABLED_COLLECTORS` | []string | (empty) | Collectors to disable |
| `HOSTNAME` | string | (from env) | Node hostname |
| `ENABLE_PPROF` | string | (unset) | `true` enables pprof endpoints |

### Valid Collector Names for `DISABLED_COLLECTORS`

`domain_info`, `vcpu`, `network`, `memory`, `block`, `block_limits`, `storage_pools`, `uptime`, `steal_time`, `hugepages`, `version`, `nic_bonding`, `cpu_smt`, `domain_numa`, `node_numa`

### Hypervisor Detection

`isCloudHypervisor()` checks if `LIBVIRT_URI` starts with `ch://`. Drives conditional logic throughout all collectors.

---

## Metric Catalog

### Domain Info (`domain_info`)

| Metric | Type | Labels |
|---|---|---|
| `kvm_domain_libvirt_info` | Gauge | node, domain, uuid, instance_name, flavor, user_name, user_uuid, project_name, project_uuid, root_type, root_uuid |
| `kvm_domain_libvirt_info_maximum_memory_bytes` | Gauge | node, domain |
| `kvm_domain_libvirt_info_memory_usage_bytes` | Gauge | node, domain |
| `kvm_domain_libvirt_info_virtual_cpus` | Gauge | node, domain |
| `kvm_domain_libvirt_info_cpu_time_seconds_total` | Counter | node, domain |
| `kvm_domain_libvirt_info_vstate` | Gauge | node, domain |

vstate values: 0=no state, 1=running, 2=blocked, 3=paused, 4=shutting down, 5=shut off, 6=crashed, 7=suspended

### vCPU (`vcpu`)

| Metric | Type | Labels |
|---|---|---|
| `kvm_domain_libvirt_vcpu_delay_nanoseconds` | Counter | node, domain, vcpu, cpu_index |
| `kvm_domain_libvirt_vcpu_spent_nanoseconds` | Counter | node, domain, vcpu, cpu_index |
| `kvm_domain_libvirt_vcpu_timeslices_total` | Counter | node, domain, vcpu, cpu_index |
| `kvm_domain_libvirt_vcpu_time_seconds_sum` | Counter | node, domain |
| `kvm_domain_libvirt_vcpu_online_count` | Gauge | node, domain |
| `kvm_domain_libvirt_vcpu_blocked_count` | Gauge | node, domain |

### Network (`network`)

| Metric | Type | Labels |
|---|---|---|
| `kvm_domain_libvirt_interface_stats_receive_bytes_total` | Counter | node, domain, target_device |
| `kvm_domain_libvirt_interface_stats_receive_packets_total` | Counter | node, domain, target_device |
| `kvm_domain_libvirt_interface_stats_receive_errors_total` | Counter | node, domain, target_device |
| `kvm_domain_libvirt_interface_stats_receive_drops_total` | Counter | node, domain, target_device |
| `kvm_domain_libvirt_interface_stats_transmit_bytes_total` | Counter | node, domain, target_device |
| `kvm_domain_libvirt_interface_stats_transmit_packets_total` | Counter | node, domain, target_device |
| `kvm_domain_libvirt_interface_stats_transmit_errors_total` | Counter | node, domain, target_device |
| `kvm_domain_libvirt_interface_stats_transmit_drops_total` | Counter | node, domain, target_device |

### Memory (`memory`)

| Metric | Type | Labels |
|---|---|---|
| `kvm_domain_libvirt_memory_stats_major_fault_total` | Counter | node, domain |
| `kvm_domain_libvirt_memory_stats_minor_fault_total` | Counter | node, domain |
| `kvm_domain_libvirt_memory_stats_unused_bytes` | Gauge | node, domain |
| `kvm_domain_libvirt_memory_stats_available_bytes` | Gauge | node, domain |
| `kvm_domain_libvirt_memory_stats_actual_balloon_bytes` | Gauge | node, domain |
| `kvm_domain_libvirt_memory_stats_rss_bytes` | Gauge | node, domain |
| `kvm_domain_libvirt_memory_stats_usable_bytes` | Gauge | node, domain |
| `kvm_domain_libvirt_memory_stats_disk_cache_bytes` | Gauge | node, domain |
| `kvm_domain_libvirt_memory_stats_used_percent` | Gauge | node, domain |

Memory stats fallback chain: libvirt API → CH cgroup stats → /proc/PID/status

### Block Device (`block`)

| Metric | Type | Labels |
|---|---|---|
| `kvm_domain_libvirt_block_device_info` | Gauge | node, domain, device_name, path, allocation, capacity, physical |

### Block Limits (`block_limits`)

19 Gauge metrics with labels `node, domain, target_device` covering I/O throttling:
- `kvm_domain_libvirt_block_stats_limit_{total,write,read}_bytes`
- `kvm_domain_libvirt_block_stats_limit_{total,write,read}_requests`
- `kvm_domain_libvirt_block_stats_limit_size_iops_bytes`
- `kvm_domain_libvirt_block_stats_limit_burst_{total,write,read}_bytes`
- `kvm_domain_libvirt_block_stats_limit_burst_{total,write,read}_requests`
- `kvm_domain_libvirt_block_stats_limit_burst_{total,write,read}_bytes_length_seconds`
- `kvm_domain_libvirt_block_stats_limit_burst_length_{total,write,read}_requests_seconds`

### Storage Pools (`storage_pools`)

| Metric | Type | Labels |
|---|---|---|
| `kvm_domain_libvirt_pool_info_capacity_bytes` | Gauge | pool |
| `kvm_domain_libvirt_pool_info_allocation_bytes` | Gauge | pool |
| `kvm_domain_libvirt_pool_info_available_bytes` | Gauge | pool |

### Uptime (`uptime`)

| Metric | Type | Labels |
|---|---|---|
| `kvm_domain_libvirt_uptime_seconds` | Gauge | node, domain |

### Steal Time (`steal_time`)

| Metric | Type | Labels |
|---|---|---|
| `kvm_domain_libvirt_steal_time` | Gauge | node, domain |
| `kvm_node_hypervisor_steal_time` | Gauge | node |

Per-domain steal time is percentage-based (delta between scrapes). Node-level is weighted average by vCPU count.

### Version (`version`)

| Metric | Type | Labels |
|---|---|---|
| `kvm_node_libvirt_versions_info` | Gauge | node, libvirtd_running, libvirt_library, libvirt_uri |

### NIC Bonding (`nic_bonding`)

| Metric | Type | Labels |
|---|---|---|
| `kvm_node_nic_bonding_info` | Gauge | node, master, slave_interface, status |

status: 1=up, 0=down

### CPU SMT (`cpu_smt`)

| Metric | Type | Labels |
|---|---|---|
| `kvm_node_cpu_smt_info` | Gauge | node, smt_active, smt_control |

### Hugepages (`hugepages`)

| Metric | Type | Labels |
|---|---|---|
| `kvm_domain_hugepages_bytes` | Gauge | node, domain |

From /proc/PID/smaps `Private_Hugetlb`.

### NUMA (`domain_numa`, `node_numa`)

| Metric | Type | Labels |
|---|---|---|
| `kvm_domain_numa_memory_bytes` | Gauge | node, domain, numa_node |
| `kvm_node_numa_hit_total` | Counter | node, numa_node |
| `kvm_node_numa_miss_total` | Counter | node, numa_node |
| `kvm_node_numa_foreign_total` | Counter | node, numa_node |
| `kvm_node_numa_local_total` | Counter | node, numa_node |
| `kvm_node_numa_other_total` | Counter | node, numa_node |
| `kvm_node_numa_interleave_hit_total` | Counter | node, numa_node |

### Internal Operational Metrics

| Metric | Type | Description |
|---|---|---|
| `functions_processed` | Counter | Processed function calls |
| `jobs_errors` | Counter | Error counter |
| `methods_called_seconds` | Histogram | Per-method latency (labels: source, method, node) |

---

## Cloud Hypervisor Integration

`CloudhypervisorWrapper` provides an alternative data path for CH-based VMs.

### Connection

Per-domain Unix socket at `{socketPath}/{domainName}-socket`. HTTP client with 15s timeout.

### Cgroup Stats

Reads cgroup v2 via `containerd/cgroups/v3`. Includes workaround for containerd library bug where `Stat()` fails to read `cpu.stat` for leaf cgroups — reads the file directly as fallback.

### PID Lookup Strategies

1. Cgroup `cgroup.procs` file
2. Domstatus XML at `/run/libvirt/ch/{domain}.xml`
3. Process name matching via /proc

### Key Differences from QEMU

| Aspect | QEMU | Cloud Hypervisor |
|--------|------|------------------|
| Stats source | libvirt RPC | HTTP API (vm.info, vm.counters) |
| Cgroup path | `machine.slice` | `machine` |
| CPU time | libvirt stats | Cgroup-based |
| Memory stats | libvirt API | Cgroup + /proc fallback |
| Socket | Single libvirt socket | Per-domain socket |

### Caching

- **Per-scrape caches**: PID, VM counters — cleared via `ClearScrapeCache()`
- **Cross-scrape caches**: config, qemu-img info, df source — 5-minute TTL

---

## Deployment

### Container Image

- Base: `gcr.io/distroless/cc:nonroot`
- CGO_ENABLED=1 (required for libvirt)
- Bundled tools: `ps`, `df`, `qemu-img`, `nsenter`, `cat`, `ls`
- UID/GID: `42438:42438` (kvm-node-agent user)
- Registry: `ghcr.io/cobaltcore-dev/kvm-exporter`

### Kubernetes DaemonSet

```yaml
hostPID: true        # Read /proc of host VM processes
hostNetwork: true    # Host network access
securityContext:
  runAsUser: 0
  readOnlyRootFilesystem: true
  capabilities:
    add: [SYS_PTRACE]   # /proc reading
    drop: [ALL]
appArmorProfile:
  type: Unconfined       # Required for libvirt operations
```

Volume mounts: `/run/libvirt` (ro), `/sys/fs/cgroup` (ro), libvirt.conf, Nova mount paths.

### Health Probes

| Probe | Endpoint | Behavior |
|-------|----------|----------|
| Liveness | `GET /health` | Chi heartbeat (200 if alive) |
| Readiness | `GET /ready` | 503 if last collection > 5 minutes ago (`atomic.Value`) |

---

## Alerts

Built-in alerts in `chart/alerts/exporter.yaml`:

| Alert | Severity | Condition |
|---|---|---|
| `KvmNodeLibvirtMetricsMissing` | warning | `up{job="kvm-exporter"} == 0` for 15m |
| `KvmNodeMissingKvmExporter` | critical | Ready node has no kvm-exporter job for 5m |
| `KvmExporterScrapeDurationHigh` | warning | `scrape_duration_seconds > 30` for 15m |
| `KvmNodeLibvirtNotResponding` | critical | GardenLinux node without version_info for 10m |

---

## Dependencies

### Runtime

| Dependency | Purpose |
|---|---|
| `digitalocean/go-libvirt` | Pure Go libvirt RPC client (no CGO bindings) |
| `prometheus/client_golang` | Prometheus metrics |
| `Tinkoff/libvirt-exporter` | Libvirt XML schema types |
| `containerd/cgroups/v3` | Cgroup v2 reader |
| `go-chi/chi/v5` | HTTP router |
| `kelseyhightower/envconfig` | Env-based config |
| `sirupsen/logrus` | Structured logging |
| `shirou/gopsutil/v3` | System info (disk usage) |
| `tklauser/go-sysconf` | Sysconf for clock ticks |
| `coreos/go-systemd/v22` | Systemd unit name escaping |
| `prometheus/procfs` | /proc filesystem helpers |

### Development

| Tool | Version | Purpose |
|---|---|---|
| `golangci-lint` | 1.57.2 | 18 linters enabled |
| `moq` | 0.5.0 | Interface mock generation |
| `kustomize` | 5.4.1 | K8s manifest management |
| `controller-gen` | 0.15.0 | CRD generation |
| `setup-envtest` | release-0.18 | Test environment setup |

---

## Code Patterns

### Interface-Based Design

`LibVirt` and `Cloudhypervisor` interfaces allow mock injection for testing. Mocks generated with `moq`.

### Metric Naming Convention

- Domain-scoped libvirt: `kvm_domain_libvirt_` prefix (via `newLibvirtDesc()`)
- Non-libvirt domain: `kvm_domain_` prefix (via `newRawDesc()`)
- Node-level: `kvm_node_` prefix (via `newRawDesc()`)

### Error Handling

Errors logged with structured fields (runID, domain, collector name). Collection continues for other domains — no panics in collection path.

### Context Cancellation

`ctx.Err()` checked at multiple points in collection for early exit when scrape timeout approaches.

### Delta Calculations

Steal time uses `sync.Map` keyed by `"domainName-PID"`, calculating deltas between scrapes.

### Cache Tiers

| Tier | Lifetime | Examples |
|------|----------|----------|
| Per-scrape | Cleared via `ClearScrapeCache()` | PID, VM counters |
| Cross-scrape (TTL) | 5-minute TTL | XML desc, block I/O tune |
| Persistent | `sync.Once` | Boot time |

### Concurrency Model

| Mechanism | Purpose |
|-----------|---------|
| `sync.Map` | Shared state (steal time history, caches) |
| `sync.Mutex.TryLock()` | Scrape serialization |
| Buffered channel semaphore | Goroutine limiting (50 max) |
| `atomic.Value` | Thread-safe timestamp (readiness probe) |

---

## Testing

### Unit Tests

- Standard Go testing with `testify/assert`
- Mock-based via `moq`-generated `InterfaceMock` (`interface_mock_gen.go`)
- Pattern: create `ServiceImpl` with mocked `virt`, inject metric channel, call collector, verify

### E2E Tests

- Custom Kind cluster image with libvirt + Cloud Hypervisor (`test/kind/Dockerfile`)
- Test VMs created on worker nodes
- `make test-all` — build image, set up cluster, deploy DaemonSets, create VMs, validate metrics
- `test/test-metrics.sh` — validates expected metrics in HTTP response
- Separate `test-qemu` and `test-ch` targets

---

## CI/CD Workflows

| Workflow | Purpose |
|---|---|
| `app-test.yaml` | Go tests |
| `app-push.yaml` | Build and push container image |
| `app-test-image-build.yaml` | Build test Kind node image |
| `chart-push.yaml` / `chart-validate.yaml` | Helm chart CI |
| `validate-pr.yaml` | PR validation |
| `validate-prometheus-alerts.yaml` | Alert rule validation |
| `bump.yaml` | Automated version bumping |
| `release.yaml` | Release creation |
| `reuse.yaml` | REUSE compliance |
| `stale.yaml` | Stale issue cleanup |

### Versioning

SemVer in `VERSION` file. PR title markers for automated bumps:
- `[BUGFIX]` — patch bump
- `[FEATURE]` — minor bump
- `[BREAKING_CHANGE]` — major bump
