# RabbitMQ Error Handling & Reliability Reference

> **Scope**: Publisher confirms, consumer acknowledgment patterns, dead letter exchanges, and retry logic. Does not cover cluster failover or network partition handling.
> **Version range**: All AMQP 0-9-1 clients; quorum queue notes apply to RabbitMQ 3.8+
> **Generated**: 2026-04-09

---

## Overview

RabbitMQ delivers at-least-once semantics when configured correctly. The three mechanisms that enforce delivery guarantees are: publisher confirms (broker acknowledges receipt), consumer manual acks (broker retains message until consumer confirms processing), and dead letter exchanges (failed messages routed to a holding queue instead of dropped). Missing any one of these creates a silent message loss vector.

---

## Pattern Table

| Pattern | When Required | Performance Cost |
|---------|---------------|-----------------|
| Publisher confirms | Critical messages (orders, payments, events) | ~10-15% throughput reduction |
| Manual consumer ack | All production consumers | None (default behavior, `auto_ack=False`) |
| Dead letter exchange | Any queue where message loss is unacceptable | None at publish time |
| Nack + requeue=False | Poison messages that fail repeatedly | Requires DLX or message is dropped |
| Retry with TTL queue | Transient failures (DB down, network blip) | Extra queue + TTL overhead |

---

## Correct Patterns

### Publisher Confirms (Python/pika)

```python
import pika

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

# Enable publisher confirms on this channel
channel.confirm_delivery()

try:
    channel.basic_publish(
        exchange='orders',
        routing_key='order.created',
        body=json.dumps(order).encode(),
        properties=pika.BasicProperties(
            delivery_mode=2,       # persistent — survives broker restart
            content_type='application/json',
            message_id=str(order['id']),
        ),
        mandatory=True,            # return message if no queue bound
    )
    # Blocks until broker acks or nacks
except pika.exceptions.UnroutableError:
    # mandatory=True and no binding found
    log.error("message unroutable — check exchange bindings")
    raise
except pika.exceptions.NackError:
    # Broker nacked (disk full, quorum not reached)
    log.error("broker nacked message — check node health")
    raise
```

**Why**: Without `confirm_delivery()`, `basic_publish` returns immediately. If the broker crashes before writing to disk, the message is lost. Confirms add a synchronous acknowledgment from the broker's storage layer.

---

### Consumer Manual Acknowledgment (Python/pika)

```python
def handle_message(channel, method, properties, body):
    try:
        result = process(body)
        # Ack only after successful processing
        channel.basic_ack(delivery_tag=method.delivery_tag)
    except TransientError as e:
        # Requeue for retry — message goes back to queue head
        log.warning("transient error, requeueing: %s", e)
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    except PoisonMessageError as e:
        # Don't requeue — send to dead letter exchange
        log.error("poison message, rejecting: %s", e)
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

channel.basic_qos(prefetch_count=10)
channel.basic_consume(queue='orders', on_message_callback=handle_message)
```

**Why**: `auto_ack=True` tells the broker to delete the message the moment it's delivered to the consumer. If the consumer crashes during `process()`, the message is gone. Manual ack means the broker retains the message until the consumer sends `basic_ack`.

---

### Dead Letter Exchange Setup

Configure the queue to route failed messages to a DLX on declaration:

```python
# 1. Declare the dead letter exchange
channel.exchange_declare(
    exchange='dlx.orders',
    exchange_type='direct',
    durable=True,
)

# 2. Declare the dead letter queue
channel.queue_declare(
    queue='orders.dead',
    durable=True,
    arguments={
        'x-message-ttl': 604_800_000,  # 7 days retention for investigation
    }
)
channel.queue_bind(queue='orders.dead', exchange='dlx.orders', routing_key='order.created')

# 3. Declare the main queue with DLX pointer
channel.queue_declare(
    queue='orders',
    durable=True,
    arguments={
        'x-dead-letter-exchange': 'dlx.orders',
        'x-dead-letter-routing-key': 'order.created',
        'x-message-ttl': 3_600_000,   # Messages expire to DLX after 1h if unprocessed
    }
)
```

**Why**: Without a DLX, rejected messages (`basic_nack` with `requeue=False`) and expired messages are silently discarded. The DLX creates an audit trail and lets you replay failed messages after fixing the consumer bug.

---

### Retry Queue Pattern (Delayed Retry Without Plugin)

Use a secondary queue with TTL to re-route messages back to the main queue after a delay:

```python
# Retry queue: messages expire back to main queue
channel.queue_declare(
    queue='orders.retry',
    durable=True,
    arguments={
        'x-message-ttl': 30_000,                  # 30s retry delay
        'x-dead-letter-exchange': '',              # default exchange
        'x-dead-letter-routing-key': 'orders',    # route back to main queue
    }
)

# In consumer: route to retry queue on transient failure
def handle_message(channel, method, properties, body):
    retry_count = int(properties.headers.get('x-retry-count', 0)) if properties.headers else 0

    try:
        process(body)
        channel.basic_ack(delivery_tag=method.delivery_tag)
    except TransientError:
        if retry_count >= 3:
            # Exhausted retries — send to dead letter
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

        channel.basic_ack(delivery_tag=method.delivery_tag)  # ack original
        channel.basic_publish(
            exchange='',
            routing_key='orders.retry',
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=2,
                headers={'x-retry-count': retry_count + 1},
            ),
        )
```

**Why**: This avoids the `rabbitmq_delayed_message_exchange` plugin dependency while providing exponential-backoff-compatible retry. The TTL on the retry queue acts as the delay. Extend to multiple retry queues with increasing TTLs for exponential backoff.

---

## Anti-Pattern Catalog

### ❌ Auto-Ack on Production Consumers

**Detection**:
```bash
# Python/pika
grep -rn 'auto_ack\s*=\s*True' --include="*.py"
rg 'basic_consume.*auto_ack=True' --type py

# Node.js/amqplib
grep -rn 'noAck\s*:\s*true' --include="*.js" --include="*.ts"
rg 'channel\.consume.*noAck.*true' --type js --type ts

# Go
rg '\.Consume\(' --type go -A 3 | grep 'autoAck.*true'
```

**What it looks like**:
```python
channel.basic_consume(
    queue='orders',
    on_message_callback=handle_order,
    auto_ack=True,  # Broker deletes message on delivery
)
```

**Why wrong**: Message is deleted from the queue the instant the broker delivers it to the consumer socket buffer — before `handle_order` even starts. Consumer crash, OOM kill, or application exception after delivery means the message is permanently lost.

**Fix**: Remove `auto_ack=True` (defaults to `False`) and call `channel.basic_ack()` after successful processing.

---

### ❌ Infinite Requeue on Failure

**Detection**:
```bash
# Python: nack with requeue=True in exception handler (no retry limit)
rg 'basic_nack' --type py -B 5 | grep 'requeue=True'
grep -rn 'basic_reject.*requeue=True' --include="*.py"

# Go: Nack with requeue=true in error path
rg '\.Nack\(' --type go -A 2 | grep 'true'
```

**What it looks like**:
```python
except Exception as e:
    log.error("processing failed: %s", e)
    channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    # Message goes back to queue head — immediately redelivered — infinite loop
```

**Why wrong**: A poison message (malformed JSON, missing field, encoding error) that always raises an exception will loop: deliver → fail → requeue → deliver → fail → requeue. This drives consumer CPU to 100% and blocks all other messages in the queue.

**Fix**: Track retry count in message headers. After N retries, `requeue=False` to route to DLX instead.

---

### ❌ No Dead Letter Exchange

**Detection**:
```bash
# Queues declared without x-dead-letter-exchange
rg 'queue_declare' --type py -A 10 | grep -v 'x-dead-letter-exchange'

# Check live queues missing DLX
rabbitmqctl list_queues name dead_letter_exchange | grep -v '\S\s\S'
```

**What it looks like**:
```python
channel.queue_declare(queue='payments', durable=True)
# No DLX — rejected/expired messages vanish
```

**Why wrong**: Any `basic_nack(requeue=False)` or expired message is silently dropped. There is no audit trail, no replay capability, no alerting on message failures.

**Fix**: Always declare a DLX for any production queue. At minimum, route to a `{queue}.dead` queue with 7-day TTL for investigation.

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `pika.exceptions.UnroutableError` | `mandatory=True` but no queue bound to exchange+routing key | Declare queue + binding before publishing; check exchange name typo |
| `pika.exceptions.NackError` | Broker nacked confirmed message (quorum not reached, disk full) | Check cluster health; `rabbitmqctl cluster_status`; check disk alarm |
| `Channel closed by broker: 406 PRECONDITION_FAILED` | Queue redeclared with different `durable`/`x-queue-type` args | Delete queue (if empty) and redeclare, or use `passive=True` to verify |
| `Channel closed: 404 NOT_FOUND` | Publishing to non-existent exchange or queue | Declare exchange/queue before publishing; check for typo in name |
| Consumer receives duplicate messages after restart | Consumer crashed after processing but before acking | Idempotent consumer logic required; track processed message IDs |
| DLX queue not receiving rejected messages | Queue missing `x-dead-letter-exchange` argument | Redeclare queue with DLX argument (requires queue delete + recreate) |
| Messages requeued indefinitely | No retry limit in exception handler | Add retry counter in headers; route to DLX after N retries |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| 3.8.0 | Quorum queues support publisher confirms | Publisher confirms now work with quorum queues (blocked before) |
| 3.10.0 | Quorum queues support per-message TTL | `x-message-ttl` header now respected on quorum queues |
| 3.13.0 | `consumer_timeout` default 30 minutes | Consumers holding unacked messages >30min get their channel closed |
| pika 1.0.0 | `basic_publish` raises `UnroutableError`/`NackError` (not return bool) | Update exception handling; old code checking return value is broken |
| amqplib (Node) 0.10+ | `channel.nack()` requires explicit `requeue` param | `false` is not the default; always pass explicit `requeue` argument |

---

## Detection Commands Reference

```bash
# Auto-ack consumers (Python)
grep -rn 'auto_ack=True' --include="*.py"

# Auto-ack consumers (Node.js)
grep -rn 'noAck: true\|noAck:true' --include="*.ts" --include="*.js"

# Missing DLX on queue declarations
rg 'queue_declare' --type py -A 8 | grep -v 'dead.letter'

# Infinite requeue patterns
rg 'basic_nack|basic_reject' --type py -A 2 | grep 'requeue=True'

# Queues with no DLX configured (live check)
rabbitmqctl list_queues name dead_letter_exchange messages_unacknowledged

# Queues with growing unacked message count
rabbitmqctl list_queues name messages messages_unacknowledged consumers
```

---

## See Also

- `channels.md` — publisher confirm flow at the channel level
- `performance.md` — prefetch tuning to prevent unacked message backlog
