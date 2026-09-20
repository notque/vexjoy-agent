# CobaltCore test contract

- Interfaces are mocked with `moq`; regenerate after interface changes through `make generate` (or the repository's pinned `go generate` command). Never hand-edit generated mocks.
- Run unit tests with the race detector: `go test -race ./...`.
- Metric tests assert required metric families/labels, not an exact total count; collectors evolve independently.
- Every new collector must be represented in `test/test-metrics.sh` and the documented `DISABLED_COLLECTORS` set.
- E2E covers both QEMU and Cloud Hypervisor paths. Use the Makefile/CI targets from the repository rather than reconstructing Kind/libvirt setup ad hoc.

When a collector changes, verify unit behavior, race cleanliness, mock freshness, emitted metric presence, disabled-collector behavior, and both hypervisor paths where applicable.
