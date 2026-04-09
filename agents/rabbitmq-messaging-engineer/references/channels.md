# RabbitMQ Channel Management Reference

> **Scope**: AMQP channel lifecycle, pooling strategies, and channel error recovery. Does not cover connection management or queue topology.
> **Version range**: RabbitMQ 3.8+ (AMQP 0-9-1 protocol)
> **Generated**: 2026-04-09

---

## Overview

AMQP channels are lightweight multiplexed sessions on a single TCP connection. Each channel is independent but shares the connection's socket. The most common production failure is treating channels like connections — creating one per message and discarding it — which exhausts file descriptors and degrades throughput. The second failure is sharing a single channel across threads, which causes undefined behavior due to AMQP framing interleaving.

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| Channel per thread | All | Multi-threaded producers/consumers | Single-threaded code (overkill) |
| Channel pool | All | Short-lived tasks that publish bursts | Long-lived consumers (use dedicated channel) |
| Dedicated consumer channel | All | `basic_consume` subscribers | Publishing (publish and consume channels should be separate) |
| `confirm_select()` | All | Critical message delivery | High-throughput fire-and-forget (adds ~10-15% latency) |

---

## Correct Patterns

### Channel Per Thread (Python/pika)

Each thread must create and own its own channel. Channels are not thread-safe.

```python
import threading
import pika

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))

def producer_thread(routing_key: str, body: bytes) -> None:
    # Each thread creates its own channel from the shared connection
    channel = connection.channel()
    channel.confirm_delivery()  # Enable publisher confirms
    channel.basic_publish(
        exchange='events',
        routing_key=routing_key,
        body=body,
        properties=pika.BasicProperties(delivery_mode=2),  # persistent
    )
    channel.close()
```

**Why**: The AMQP framing protocol requires that each channel's frames arrive in order. Two threads writing to the same channel interleave frames, producing protocol errors or silently corrupt messages.

---

### Separate Channels for Publish and Consume

```python
# Good: separate channels for publish vs consume
publish_channel = connection.channel()
consume_channel = connection.channel()

consume_channel.basic_consume(
    queue='tasks',
    on_message_callback=handle_message,
    auto_ack=False,
)

# publish_channel used independently
publish_channel.basic_publish(exchange='results', routing_key='done', body=result)
```

**Why**: Mixing publish and consume on the same channel creates head-of-line blocking. A slow `basic_publish` with confirms holds up `basic_ack` delivery for the consumer.

---

### Publisher Confirm on Channel (Go/amqp091-go)

```go
ch, err := conn.Channel()
if err != nil {
    return fmt.Errorf("open channel: %w", err)
}
defer ch.Close()

if err := ch.Confirm(false); err != nil {
    return fmt.Errorf("confirm mode: %w", err)
}

confirms := ch.NotifyPublish(make(chan amqp.Confirmation, 1))

err = ch.PublishWithContext(ctx, exchange, routingKey, true, false, amqp.Publishing{
    DeliveryMode: amqp.Persistent,
    Body:         body,
})
if err != nil {
    return fmt.Errorf("publish: %w", err)
}

select {
case confirm := <-confirms:
    if !confirm.Ack {
        return fmt.Errorf("broker nacked message")
    }
case <-ctx.Done():
    return fmt.Errorf("confirm timeout: %w", ctx.Err())
}
```

**Why**: `Confirm(false)` enables publisher confirms on the channel. Without the `NotifyPublish` drain, the confirms buffer fills and the channel blocks.

---

## Anti-Pattern Catalog

### ❌ Channel Per Message (Connection-Scoped Channel Churn)

**Detection**:
```bash
# Python: channel created inside publish function
rg 'def.*publish|def.*send' --type py -A 5 | grep 'channel()'
grep -rn '\.channel()' --include="*.py" | grep -v 'self\._channel\|self\.channel'

# Go: channel opened without assignment to struct field
rg 'conn\.Channel\(\)' --type go | grep -v 'var ch\|:= ch'
```

**What it looks like**:
```python
def publish_event(body: bytes) -> None:
    connection = get_connection()
    channel = connection.channel()  # new channel every call
    channel.basic_publish(exchange='events', routing_key='task', body=body)
    # channel not closed, leaked
```

**Why wrong**: Each `channel()` call opens a new AMQP channel. Default channel limit is 2047 per connection (`channel_max`). Under publish load this exhausts the limit and the broker starts closing channels with a 503 error. Also: opening a channel involves a round-trip handshake (Channel.Open + Channel.OpenOk), adding latency per message.

**Fix**:
```python
class Publisher:
    def __init__(self, connection):
        self._channel = connection.channel()
        self._channel.confirm_delivery()

    def publish(self, body: bytes) -> None:
        self._channel.basic_publish(
            exchange='events', routing_key='task', body=body,
            properties=pika.BasicProperties(delivery_mode=2),
        )
```

---

### ❌ Shared Channel Across Threads

**Detection**:
```bash
# Python: channel assigned to class attribute and used in multiple methods
grep -rn 'self\._channel\s*=' --include="*.py" -A 1
rg 'self\.channel\.(basic_publish|basic_ack|basic_nack)' --type py

# Go: channel passed to goroutines by reference
rg 'go func.*ch\s+\*amqp\.Channel' --type go
```

**What it looks like**:
```python
class Worker:
    def __init__(self):
        self.channel = connection.channel()

    def start(self):
        for _ in range(4):
            threading.Thread(target=self._process).start()

    def _process(self):
        while True:
            self.channel.basic_ack(tag)  # multiple threads, same channel!
```

**Why wrong**: AMQP frames from concurrent threads interleave on the wire. The broker sees malformed frames and closes the connection with a 505 (unexpected frame) or 503 error. pika's BlockingConnection is explicitly not thread-safe.

**Fix**: One channel per thread, or use `pika.SelectConnection` with a single IO loop thread and a thread-safe queue to pass messages in.

---

### ❌ Forgetting to Drain Confirm Notifications

**Detection**:
```bash
rg 'confirm_delivery|Confirm\(false\)' --type py --type go -A 3 | grep -v 'NotifyPublish\|wait_for_confirms'
```

**What it looks like**:
```python
channel.confirm_delivery()
for msg in messages:
    channel.basic_publish(...)
    # never calls channel.wait_for_confirms_or_die()
```

**Why wrong**: Unread confirms accumulate in pika's internal buffer. After ~1000 unconfirmed messages the channel stalls waiting for the application to drain the buffer.

**Fix**: Call `channel.wait_for_confirms_or_die()` after each publish batch, or use `channel.basic_publish()` with `mandatory=True` and handle `basic.return` callbacks.

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `CHANNEL_ERROR - expected 'channel.open'` | Channel opened twice or reused after close | Create new channel, don't reuse closed channels |
| `NOT_FOUND - no exchange '{name}'` | Exchange not declared before publishing | Declare exchange with `exchange_declare()` before first publish |
| `RESOURCE_LOCKED - cannot obtain exclusive access` | Exclusive queue consumed by another connection | Each exclusive queue requires its own dedicated connection |
| `PRECONDITION_FAILED - inequivalent arg` | Queue/exchange declared with different params than existing | Use `passive=True` to check existing params before re-declaring |
| `ACCESS_REFUSED - access to queue '...' refused` | User lacks `write` or `read` permission on vhost | Grant permissions with `rabbitmqctl set_permissions` |
| Channel max reached (503) | Too many channels on one connection | Limit channels per connection; default `channel_max=2047` |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| RabbitMQ 3.8.0 | Quorum queues GA | Use `x-queue-type: quorum` for new HA queues; mirrored queues deprecated |
| RabbitMQ 3.9.0 | `global` flag for `basic.qos` deprecated | `prefetch_count` now always per-consumer, not per-channel |
| RabbitMQ 3.12.0 | Classic queue v1 storage removed | Existing classic queues auto-upgrade; check `x-max-length` behavior change |
| pika 1.3.0 | `BlockingChannel.basic_publish` returns `None` not `bool` | Stop checking return value; use `confirm_delivery()` instead |
| amqp091-go 1.7.0 | `PublishWithContext` replaces `Publish` | Use context-aware variant for timeout/cancel support |

---

## Detection Commands Reference

```bash
# Channel churn: new channel per publish call
rg 'def.*publish' --type py -A 8 | grep '\.channel()'

# Shared channel across threads (Python)
grep -rn 'self\._channel\s*=' --include="*.py"

# Confirm mode without drain
rg 'confirm_delivery\(\)' --type py -A 20 | grep -L 'wait_for_confirms'

# Go channel not closed after use
rg 'ch, err := conn.Channel' --type go -A 30 | grep -v 'defer ch.Close()'
```

---

## See Also

- `performance.md` — prefetch tuning, connection pool sizing
- `error-handling.md` — publisher confirms flow, consumer ack patterns
