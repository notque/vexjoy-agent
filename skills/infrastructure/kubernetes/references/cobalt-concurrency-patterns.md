# CobaltCore concurrency invariants

The exporter deliberately uses three different synchronization mechanisms:

- Collector fan-out is semaphore-limited; never launch one unbounded goroutine per domain/device.
- Prometheus `Collect` uses `TryLock`, not blocking `Lock`: overlapping scrapes must fail/skip rather than queue and amplify scrape latency.
- Cross-scrape delta state uses `sync.Map`; per-scrape ephemeral cache is cleared with `defer ClearScrapeCache()` at the start of collection.

Propagate the scrape context into collection loops and check cancellation before expensive libvirt/Cloud Hypervisor calls and before sending metrics.

When reviewing a change, inspect every new `go` launch for semaphore acquire/release, every scrape lock for blocking behavior, and every shared map for synchronization. Then run:

```bash
go test -race ./...
rg 'go func|\.Lock\(|TryLock|ClearScrapeCache|map\[' .
```

Do not replace these mechanisms merely for stylistic uniformity; they encode different latency and lifetime requirements.
