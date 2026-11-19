# RabbitMQ Messaging Reference

> **Scope**: RabbitMQ topology and operations: AMQP exchanges (direct, topic, fanout, headers), queues, bindings, routing keys; quorum queues, clustering, federation, shovel, partition handling; lazy queues, TTL, prefetch, connection pooling; publisher confirms, consumer acks, dead-letter exchanges, retries; monitoring, capacity planning, upgrades, backup/restore.
> **Not here**: Kafka, Spark, or stream-processing pipelines (`skills/analysis/data/references/data.md`); running the broker through manifests or Helm (`kubernetes-helm.md`); broker dashboards and alert rules (`prometheus-grafana.md`); producer/consumer application code (`programming` skill). Event schema design and versioning is out of scope.

Priorities, in order: reliability (delivery guarantees, durability), performance (throughput, latency), availability (clustering, failover, partition tolerance), observability (metrics, tracing, error visibility).

## Hard rules

- **Quorum queues for HA**: never classic mirrored queues.
- **Publisher confirms** for critical messages.
- **Consumer acknowledgments** after processing, so crashes don't lose messages.
- **Connection pooling**: no connection per operation.

## Defaults (on unless disabled)

- Dead-letter exchange for failed messages.
- Message TTL to stop unbounded growth.
- Consumer prefetch limits for fair distribution.
- Monitor queue depth, consumer count, message rates.

## Optional (off unless enabled)

- Federation, only to connect clusters.
- Shovel, only to move messages between clusters or queues.
- Delayed message plugin, only for scheduled messages.
- Stream queues, only for append-only log consumption.

## Output

- **Before**: requirements (messaging patterns), current state (queues, exchanges), scale (volume, throughput), reliability needs (delivery guarantees).
- **During**: show queue and exchange definitions, `rabbitmqctl` commands, client config, monitoring queries.
- **After**: queues and exchanges configured, HA configured, monitoring on, performance validated; report message rate, queue depth, consumer count.
- Implementation Schema details: [output-schemas.md](../../../shared-patterns/output-schemas.md).

## Error handling

| Error | Cause | Fix |
|---|---|---|
| Queue depth growing | Consumers slower than publishers (slow processing, too few consumers, slow downstream) | Add consumers, speed up processing, check prefetch (too high or too low), watch ack rate, look for blocked consumers |
| Memory alarm | Large backlog in memory, no lazy queues, unacked messages, watermark too high | Lazy queues, more consumers, find unacked messages, lower the watermark, add nodes |
| Connection refused or closed | Connection limit, auth failure, network, node down | `rabbitmqctl list_connections`, raise the file descriptor limit, verify credentials and network, confirm the node runs and joined the cluster |

## Preferred patterns

- **Manual acks**: signal auto-ack, or ack before processing. A crash mid-processing loses the message. Ack after success with `channel.basic_ack(delivery_tag)`; use `basic.nack` for failures.
- **Connection pooling**: signal a new connection per publish or consume. Keep long-lived connections, one channel per thread, reuse across operations.
- **Quorum queues**: signal `ha-mode: all` or `ha-mode: exactly`. Mirrored queues are deprecated and slow. Use `x-queue-type: quorum`.

## Rationalizations to reject

| Claim | Why it's wrong | Do this |
|---|---|---|
| "Auto-ack is simpler" | Loses messages on crash | Manual acks |
| "Connection per message is cleaner" | Exhausts resources | Connection pooling |
| "Classic queues are fine for HA" | Mirrored queues deprecated, slow | Quorum queues |
| "We don't need publisher confirms" | Silent message loss | Confirms for critical messages |
| "Default prefetch is optimal" | Uneven work distribution | Tune prefetch from processing time |

## Hard gates

Before implementing, check for these. If found: stop, report, fix before continuing.

| Pattern | Why blocked | Fix |
|---|---|---|
| Auto-ack for critical messages | Loss on failure | Manual ack after processing |
| Connection per operation | Resource exhaustion | Connection pooling |
| Mirrored queues (`ha-mode`) | Deprecated, slow | `x-queue-type: quorum` |
| No dead-letter exchange | Failed messages lost | Configure a DLX |
| Unbounded queue growth | Memory exhaustion | Message TTL, monitor depth |

## Verification stops

- After changing queue or exchange config: have I checked the current topology (exchanges, bindings, consumers)? Config built without it causes routing surprises.
- After recommending a performance change (prefetch, lazy queues, pooling): do I give before/after numbers (message rate, depth, consumer use), or say why measurement is impossible?
- After any cluster or HA change: have I checked producers on affected exchanges, consumers on affected queues, and apps that rely on specific routing keys?

## Before destructive or live changes

- Before deleting a queue or exchange, purging, or force-resetting a node: confirm it is reversible or the messages are expendable. Deleting a queue with unprocessed messages loses them; a purge can't be undone.
- Before applying production cluster config: check it against the current cluster. A wrong policy (queue pattern, ha-params) silently changes every matching queue.

## Audit stance

When auditing a deployment, assume at least one misconfiguration. Check each before calling it healthy; a queue that silently loses messages is worse than one that fails visibly:

- Classic mirrored queues instead of quorum queues.
- Auto-ack consumers losing messages on crash.
- No dead-letter exchange.
- Connection-per-operation code slowly exhausting file descriptors.
- No TTL on queues that grow slowly.
- Prefetch 0 (unlimited) causing uneven distribution.

## Recommendation format

Each recommendation names the **component** (queue, exchange, binding, policy, or cluster setting), **current state** (or "new"), **proposed state**, and **risk level** (Low, Medium, High) with a short reason.

## Blockers

Resolve routine issues from repository evidence and existing authorization. When sure, decide, record the assumption, and continue; ask Jev when genuinely unsure.

| Situation | Why stop | Ask |
|---|---|---|
| Message volume unknown | Can't size the cluster | "Expected message rate (msgs/sec) and size?" |
| Reliability unclear | Sets delivery guarantees | "Can you tolerate loss? At-least-once or exactly-once?" |
| HA unknown | Sets cluster design | "How many nodes? How many node failures to tolerate?" |
| Retention unclear | Sets storage and TTL | "How long to keep unprocessed messages?" |

Decide explicitly first: message volume, delivery guarantees, HA (node count, quorum settings), retention.

## Reference loading table

| Signal | Load | Why |
|---|---|---|
| Channel lifecycle, channel pooling, per-thread channels, publisher confirms on a channel | [rabbitmq-messaging/channels.md](rabbitmq-messaging/channels.md) | Channel management |
| Prefetch tuning, lazy queues, connection pooling, throughput, memory alarms | [rabbitmq-messaging/performance.md](rabbitmq-messaging/performance.md) | Performance tuning |
| Publisher confirms, consumer acks, dead-letter exchange, retry logic, poison messages | [rabbitmq-messaging/error-handling.md](rabbitmq-messaging/error-handling.md) | Reliability and failure handling |
