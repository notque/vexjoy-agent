# RabbitMQ Performance Tuning Reference

> **Scope**: Throughput optimization, prefetch tuning, lazy queues, and connection pooling. Does not cover cluster hardware sizing or OS-level tuning.
> **Version range**: RabbitMQ 3.8+ for quorum queues and lazy queues; 3.6+ for lazy queue flag
> **Generated**: 2026-04-09

---

## Overview

RabbitMQ performance problems cluster around four root causes: unbounded prefetch (uneven consumer load), eager queue storage (memory pressure from large backlogs), connection-per-operation (TCP overhead dominates throughput), and missing flow control (publisher outpaces consumer). Each has a concrete detection path and a measurable fix.

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| `prefetch_count=10-100` | All | CPU-bound consumers | I/O-bound consumers (may need higher) |
| `x-queue-mode: lazy` | 3.6+ | Queue backlog > 1M messages | Low-latency queues (lazy increases deliver latency) |
| `x-queue-type: quorum` | 3.8+ | HA required | Single-node dev setup (quorum needs 3+ nodes) |
| Connection pool (3-10 conns) | All | Multi-threaded producers | Single-threaded scripts |
| Batch ack (`multiple=True`) | All | High-throughput consumers | Low-latency pipelines (delays ack by batch interval) |

---

## Correct Patterns

### Consumer Prefetch (Python/pika)

Set prefetch before starting consume. Default is 0 (unlimited), which lets one consumer hoard all messages.

```python
channel = connection.channel()

# Limit to 20 unacked messages per consumer
# RabbitMQ 3.9+: global=False is now the only supported mode (per-consumer)
channel.basic_qos(prefetch_count=20)

channel.basic_consume(
    queue='tasks',
    on_message_callback=handle_message,
    auto_ack=False,
)
```

**Why**: `prefetch_count=0` means the broker pushes all available messages to the first connected consumer. Other consumers starve. With `prefetch_count=20`, each consumer holds at most 20 unacked messages, distributing work fairly.

**Tuning guide**:
- Start at `prefetch_count=1` for correctness, then increase
- CPU-bound tasks: `prefetch_count=2-10` (prevent starvation while limiting memory)
- I/O-bound tasks: `prefetch_count=20-100` (overlap I/O with next message processing)
- Monitor: `rabbitmqctl list_consumers` — look at `prefetch_count` and `ack_required`

---

### Lazy Queues for Large Backlogs (RabbitMQ 3.6+)

```python
channel.queue_declare(
    queue='bulk-tasks',
    durable=True,
    arguments={
        'x-queue-mode': 'lazy',         # Move messages to disk immediately
        'x-message-ttl': 86400000,       # 24h TTL to prevent unbounded growth
        'x-max-length': 10_000_000,      # Safety cap
        'x-overflow': 'reject-publish',  # Backpressure on overflow
    }
)
```

**Why**: Default (non-lazy) queues keep messages in memory until consumer pressure forces paging. A 10M message backlog can consume 10+ GB of RAM and trigger memory alarms. Lazy queues write to disk immediately and read on demand, capping memory to ~1 MB per queue regardless of depth.

**Note**: Lazy queues add ~1-2ms deliver latency. Only use when backlog can grow large.

---

### Connection Pooling (Go)

```go
type Pool struct {
    connections []*amqp.Connection
    mu          sync.Mutex
    idx         int
}

func NewPool(dsn string, size int) (*Pool, error) {
    p := &Pool{connections: make([]*amqp.Connection, size)}
    for i := range size {
        conn, err := amqp.Dial(dsn)
        if err != nil {
            return nil, fmt.Errorf("dial[%d]: %w", i, err)
        }
        p.connections[i] = conn
    }
    return p, nil
}

func (p *Pool) Get() *amqp.Connection {
    p.mu.Lock()
    defer p.mu.Unlock()
    conn := p.connections[p.idx%len(p.connections)]
    p.idx++
    return conn
}
```

**Why**: Each AMQP connection is a TCP socket. Opening/closing a connection per publish involves TCP handshake + TLS negotiation + AMQP Start/StartOk sequence (~5-10 RTTs). At 1000 msg/s this is 5000-10000 RTTs/s of pure overhead. A pool of 5 connections reduces this to zero.

**Sizing**: 3-10 connections for most workloads. More than 10 rarely helps due to broker-side connection handling overhead.

---

### Batch Consumer Ack

```python
def handle_message(ch, method, properties, body):
    process(body)
    # Ack this and all prior unacked messages on this channel
    ch.basic_ack(delivery_tag=method.delivery_tag, multiple=True)
```

**Why**: Each `basic_ack` is an AMQP frame sent to the broker. At 10,000 msg/s, individual acks add 10,000 broker writes/s. `multiple=True` acks all messages up to this delivery_tag in one frame, cutting ack overhead by 5-10x.

**Trade-off**: If consumer crashes between messages, all unacked messages requeue. Acceptable for idempotent consumers; avoid for exactly-once semantics.

---

## Anti-Pattern Catalog

### ❌ Prefetch 0 (Unlimited)

**Detection**:
```bash
# Python: basic_qos not called, or called with 0
grep -rn 'basic_qos' --include="*.py" | grep 'prefetch_count=0'
# Also check for missing qos entirely — no basic_qos before basic_consume
rg 'basic_consume' --type py -B 10 | grep -v 'basic_qos'

# Go: no QoS set before Consume
rg '\.Consume\(' --type go -B 10 | grep -v 'Qos\('
```

**What it looks like**:
```python
channel.basic_consume(queue='tasks', on_message_callback=handle)
# No basic_qos call — broker pushes unlimited messages
```

**Why wrong**: Broker pushes all queued messages to the first consumer that connects. Memory on the consumer grows without bound. Other consumers get nothing until the first consumer's buffer drains. Under spike load this causes OOM kills on consumer processes.

**Fix**: Always call `channel.basic_qos(prefetch_count=N)` before `basic_consume`. Start with `prefetch_count=10` and tune upward.

---

### ❌ No Message TTL on Persistent Queues

**Detection**:
```bash
# Python: queue_declare without x-message-ttl
rg 'queue_declare' --type py -A 5 | grep -v 'x-message-ttl\|ttl'

# Check existing queues without TTL policy
rabbitmqctl list_queues name policy | grep -v 'ttl\|expire'
```

**What it looks like**:
```python
channel.queue_declare(
    queue='notifications',
    durable=True,
    # No TTL, no max-length — grows forever if consumers are slow
)
```

**Why wrong**: Queues without TTL or max-length policies grow unboundedly if consumers fall behind. A queue with 10M messages consumes GB of memory/disk. Memory alarm fires at 40% (default watermark), blocking all publishers on the node.

**Fix**:
```python
channel.queue_declare(
    queue='notifications',
    durable=True,
    arguments={
        'x-message-ttl': 3_600_000,      # 1 hour
        'x-max-length': 1_000_000,        # safety cap
        'x-overflow': 'reject-publish',   # backpressure, not drop
        'x-dead-letter-exchange': 'dlx',  # route expired messages
    }
)
```

---

### ❌ Classic Mirrored Queues for HA

**Detection**:
```bash
# Policy using ha-mode (mirrored, deprecated)
rabbitmqctl list_policies | grep 'ha-mode'

# Code setting ha-mode in policy
rg 'ha-mode|ha_mode' --type py --type go --type js
```

**What it looks like**:
```bash
rabbitmqctl set_policy ha-all ".*" '{"ha-mode":"all"}' --apply-to queues
```

**Why wrong**: Classic mirrored queues replicate via synchronous replication to all mirror nodes. This causes write amplification proportional to cluster size. Under high throughput (>10K msg/s), mirrors can't keep up and the queue enters `slave_not_synchronized` state — at which point failover promotes an unsynchronized mirror, losing messages. Deprecated since 3.11, removed in 4.0.

**Fix**:
```bash
# Use quorum queues (Raft-based, stronger guarantees)
rabbitmqctl set_policy quorum-ha "^ha\." \
    '{"x-queue-type":"quorum"}' \
    --apply-to queues
```

Or declare directly:
```python
channel.queue_declare(
    queue='critical-tasks',
    durable=True,
    arguments={'x-queue-type': 'quorum'},
)
```

**Version note**: Quorum queues require RabbitMQ 3.8+ and a 3-node cluster minimum (quorum needs majority). Single-node deployments cannot use quorum queues.

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `AMQP connection heartbeat timeout` | Consumer blocked processing; no heartbeat response | Reduce `prefetch_count`; process messages in separate thread |
| `Memory alarm on node rabbit@host` | Queue backlog in RAM exceeds `vm_memory_high_watermark` (default 40%) | Enable lazy queues; add consumers; increase cluster nodes |
| `Disk alarm on node rabbit@host` | Disk free below `disk_free_limit` (default 50MB) | Add disk; enable lazy queues to spread write load; purge stale queues |
| `basic.return` / mandatory message unroutable | No queue bound to exchange+routing key | Check bindings with `rabbitmqctl list_bindings`; declare queue before publishing |
| Consumer utilization < 50% in management UI | Prefetch too low or consumers processing too slowly | Increase `prefetch_count`; add more consumer instances |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| 3.6.0 | Lazy queues introduced (`x-queue-mode: lazy`) | Use for bulk/batch queues to reduce memory pressure |
| 3.8.0 | Quorum queues GA | Replace mirrored queues with `x-queue-type: quorum` |
| 3.9.0 | `global` QoS flag deprecated | `basic_qos` always per-consumer now; `global=True` silently ignored |
| 3.10.0 | Quorum queue message TTL | TTL now supported natively on quorum queues (was blocked before) |
| 3.11.0 | Classic mirrored queues deprecated | Migration required before 4.0 |
| 3.12.0 | Classic queues v2 storage (CQv2) default | 20-30% less memory for classic queues; backward-compatible |
| 4.0.0 | Classic mirrored queues removed | Existing `ha-mode` policies fail; must migrate to quorum queues |

---

## Detection Commands Reference

```bash
# Prefetch 0 (unlimited) consumers
grep -rn 'prefetch_count=0' --include="*.py"
rg 'basic_consume' --type py -B 15 | grep -v 'basic_qos'

# Queues without TTL
rabbitmqctl list_queues name arguments | grep -v 'x-message-ttl'

# Classic mirrored policies (deprecated)
rabbitmqctl list_policies | grep 'ha-mode'

# Consumer utilization (management API)
curl -u guest:guest http://localhost:15672/api/consumers | python3 -m json.tool | grep utilisation

# Queue memory usage
rabbitmqctl list_queues name memory messages consumers
```

---

## See Also

- `channels.md` — channel lifecycle and per-thread patterns
- `error-handling.md` — publisher confirms, DLX, retry logic
