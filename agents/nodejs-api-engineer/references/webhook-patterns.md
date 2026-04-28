---
description: Webhook processing patterns — signature verification, idempotency, retry handling, and queue integration
---

# Webhook Patterns for Node.js APIs

> **Scope**: Receiving and processing webhooks from Stripe, GitHub, and generic HTTP POST webhooks. Signature verification, idempotency keys, retry-safe handlers, and queue offloading.
> **Version range**: Node.js 18+, Express 4.x/5.x
> **Generated**: 2026-04-08

---

## Overview

Webhooks fail in two distinct phases: verification (signature check, replay prevention) and processing (idempotency, error handling). A webhook handler that crashes mid-processing causes the sender to retry — which may execute the same business logic twice. The correct architecture separates acknowledgment (fast HTTP 200) from processing (durable queue).

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| Raw body middleware before JSON parse | Express 4+ | Stripe/GitHub signature verification | After `express.json()` — body already consumed |
| Idempotency key deduplication | Always | Retry-prone events (payments, emails) | Fire-and-forget notifications |
| Queue offloading (BullMQ) | BullMQ 3+ | Processing > 2 seconds | Sub-100ms handlers |
| `rawBody` middleware | Express 4+ | HMAC signature verification | When body is already parsed |

---

## Correct Patterns

### Raw Body Preservation for Signature Verification

Stripe and GitHub sign the raw request body. Once `express.json()` parses it, the original bytes are gone and the signature check fails.

```typescript
import express from 'express';
import { createHmac, timingSafeEqual } from 'crypto';

// MUST register raw body middleware BEFORE express.json() for webhook routes
app.use('/webhooks/stripe', express.raw({ type: 'application/json' }));
app.use('/webhooks/github', express.raw({ type: 'application/json' }));

// All other routes get JSON parsing
app.use(express.json());

// Stripe webhook handler
app.post('/webhooks/stripe', (req, res) => {
  const sig = req.headers['stripe-signature'] as string;
  const rawBody = req.body as Buffer; // Buffer, not object

  if (!verifyStripeSignature(rawBody, sig, process.env.STRIPE_WEBHOOK_SECRET!)) {
    res.status(400).json({ error: 'Invalid signature' });
    return;
  }

  const event = JSON.parse(rawBody.toString('utf-8'));
  // Acknowledge immediately, process asynchronously
  res.status(200).json({ received: true });
  processWebhookEvent(event).catch(console.error);
});
```

**Why**: `express.raw()` captures the original bytes. After `express.json()` runs, `req.body` is a parsed object — re-serializing it changes whitespace and ordering, breaking the HMAC.

---

### Idempotency with Redis

Store processed event IDs to prevent duplicate processing on retry.

```typescript
import { createClient } from 'redis';

const redis = createClient({ url: process.env.REDIS_URL });

async function processIdempotent(
  eventId: string,
  handler: () => Promise<void>
): Promise<{ processed: boolean; duplicate: boolean }> {
  const key = `webhook:processed:${eventId}`;
  const ttl = 24 * 60 * 60; // 24 hours — longer than retry window

  // SET NX: only set if key doesn't exist (atomic)
  const acquired = await redis.set(key, '1', { NX: true, EX: ttl });

  if (!acquired) {
    // Already processed — safe to return 200 without re-processing
    return { processed: false, duplicate: true };
  }

  try {
    await handler();
    return { processed: true, duplicate: false };
  } catch (err) {
    // Delete key so retry can attempt processing again
    await redis.del(key);
    throw err;
  }
}

// Usage in webhook handler:
app.post('/webhooks/stripe', async (req, res) => {
  const event = parseStripeEvent(req.body, req.headers['stripe-signature'] as string);

  res.status(200).json({ received: true }); // ACK first

  const { duplicate } = await processIdempotent(event.id, async () => {
    await handleStripeEvent(event);
  });

  if (duplicate) {
    console.log(`[info] duplicate event ${event.id} — skipped`);
  }
});
```

**Why**: Without idempotency, a failed handler causes Stripe to retry. On retry, `payment.succeeded` fires again — duplicate charge fulfillment. Redis `SET NX` is atomic: no two workers can claim the same event ID.

---

### Queue Offloading for Slow Handlers

For handlers > 2 seconds: respond 200 immediately, push to BullMQ.

```typescript
import { Queue } from 'bullmq';

const webhookQueue = new Queue('webhook-events', {
  connection: { url: process.env.REDIS_URL },
  defaultJobOptions: {
    attempts: 3,
    backoff: { type: 'exponential', delay: 1000 },
    removeOnComplete: 100, // Keep last 100 for debugging
    removeOnFail: 1000,
  },
});

app.post('/webhooks/stripe', async (req, res) => {
  // Verify signature synchronously (fast)
  const sig = req.headers['stripe-signature'] as string;
  if (!verifyStripeSignature(req.body, sig, process.env.STRIPE_WEBHOOK_SECRET!)) {
    res.status(400).json({ error: 'Invalid signature' });
    return;
  }

  const event = JSON.parse((req.body as Buffer).toString('utf-8'));

  // Push to queue — returns in < 5ms
  await webhookQueue.add(event.type, event, {
    jobId: event.id, // Deduplication: BullMQ skips duplicate jobIds
  });

  res.status(200).json({ received: true }); // Within Stripe's 30s timeout
});
```

**Why**: Stripe requires an HTTP 200 response within 30 seconds. Database operations, email sending, or external API calls can exceed this. Queue offloading guarantees fast acknowledgment. BullMQ's `jobId` deduplication handles retries.

---

## Pattern Catalog

### Preserve Raw Body for Signature Verification
**Detection**:
```bash
grep -rn 'express\.json()' --include="*.ts" src/
# Check if webhook routes are registered after app.use(express.json())
grep -rn 'app\.post.*webhook' --include="*.ts" src/ -B20 | grep 'express\.json'
```

**Signal**:
```typescript
app.use(express.json()); // Parses ALL bodies first

app.post('/webhooks/stripe', (req, res) => {
  // req.body is now a JS object, not the original bytes
  const sig = req.headers['stripe-signature'];
  stripe.webhooks.constructEvent(req.body, sig, secret); // Always fails!
});
```

**Why this matters**: `express.json()` consumes the request stream and replaces `req.body` with a parsed object. The original bytes are gone. `stripe.webhooks.constructEvent()` requires the raw body to recompute the HMAC — it will always throw `No signatures found matching the expected signature for payload`.

**Preferred action**: Register `express.raw({ type: 'application/json' })` on webhook paths before `express.json()` on the general middleware stack.

---

### Acknowledge Webhooks Immediately, Process via Queue
**Detection**:
```bash
# Look for awaited DB calls or email sends inside webhook handlers
grep -rn 'app\.post.*webhook' --include="*.ts" src/ -A30 | grep -E 'await.*db|await.*email|await.*stripe|sendMail'
```

**Signal**:
```typescript
app.post('/webhooks/stripe', async (req, res) => {
  const event = JSON.parse(req.body.toString());

  if (event.type === 'payment_intent.succeeded') {
    // Doing heavy work before responding — may exceed 30s timeout
    await db.orders.update({ where: { paymentId: event.data.object.id }, data: { status: 'paid' } });
    await emailService.sendReceipt(event.data.object.customer_email);
    await fulfillmentService.triggerShipment(event.data.object.metadata.orderId);
  }

  res.status(200).json({ received: true }); // May never reach this if above fails
});
```

**Why this matters**: If any operation throws or takes > 30 seconds, Stripe retries the webhook. Without idempotency, the order gets updated twice, two receipts are sent, two shipments triggered. The `res.status(200)` after the operations also means a timeout sends no response at all.

**Preferred action**: Respond 200 immediately, push to BullMQ for processing.

---

### Respond Before Queue Push
**Detection**:
```bash
grep -rn 'await.*queue\.add\|await.*enqueue' --include="*.ts" src/
# Queue push before res.status(200) — blocks acknowledgment
grep -rn 'queue\.add' --include="*.ts" src/ -A5 | grep 'res\.status'
```

**Signal**:
```typescript
app.post('/webhooks', async (req, res) => {
  await webhookQueue.add('event', req.body); // Blocks if Redis is slow
  res.status(200).json({ received: true }); // Only after queue push
});
```

**Why this matters**: If Redis is slow or down, the queue push blocks and may exceed the webhook sender's timeout. The sender retries, causing duplicate queue entries.

**Preferred action**: Respond first, queue second. If Redis is unavailable, log and still return 200 (accept the event, process manually later via retry mechanism):
```typescript
res.status(200).json({ received: true });
// Fire-and-forget the queue push — errors logged but don't affect HTTP response
webhookQueue.add('event', event).catch((err) => {
  console.error(`[error] webhook queue push failed for ${event.id}: ${err.message}`);
  // Consider dead-letter storage or alerting here
});
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `No signatures found matching the expected signature` | Body parsed by `express.json()` before raw capture | Register `express.raw()` before `express.json()` on webhook routes |
| `Webhook timestamp too old` | Event timestamp > tolerance (default 300s) | Check server clock sync (`ntpdate`); don't replay old test events |
| `Invalid signature` | Wrong webhook secret in env | Verify `STRIPE_WEBHOOK_SECRET` matches dashboard signing secret |
| `BullMQ: Job already exists` | Duplicate job ID on retry | Expected behavior — BullMQ deduplication working correctly |
| Duplicate fulfillment | No idempotency key check | Implement `SET NX` pattern before processing payment events |
| `ECONNREFUSED` on Redis | Redis not running for queue | Check Redis health; implement fallback logging for critical webhooks |

---

## Detection Commands Reference

```bash
# express.json() before webhook routes
grep -n 'express\.json\|app\.post.*webhook' --include="*.ts" src/ -r

# Missing raw body for webhook routes
grep -rn 'app\.post.*webhook' --include="*.ts" src/ -B10 | grep -v 'raw\|express\.raw'

# String comparison for webhook signatures
grep -rn 'signature.*===\|hmac.*===' --include="*.ts" src/

# Heavy processing before 200 response
grep -rn 'await.*db\.\|await.*email\.\|await.*send' --include="*.ts" src/ | grep -i webhook

# Missing idempotency check
grep -rn 'webhook\|stripe\.event\|github\.event' --include="*.ts" src/ | grep -v 'idempotent\|eventId\|processed'
```

---

## See Also

- `auth-patterns.md` — `timingSafeEqual` for signature verification detail
- BullMQ docs: https://docs.bullmq.io/
- Stripe webhook docs: https://docs.stripe.com/webhooks
