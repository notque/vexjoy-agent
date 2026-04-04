# Stripe Integration Reference
<!-- Loaded by nextjs-ecommerce-engineer when task involves Stripe, payment processing, Payment Intents, webhooks, or checkout -->

Stripe's cardinal rule: the client never sees raw card data. The browser collects card details directly into Stripe's systems via Elements; your server only ever handles payment tokens and intents.

## Stripe Elements Setup
**When to use:** Building a custom checkout form embedded in your UI (vs. redirecting to Stripe-hosted Checkout).

```typescript
// app/checkout/page.tsx — server component wraps client checkout
import { stripe } from '@/lib/stripe'
import { CheckoutForm } from './CheckoutForm'
import { getCart } from '@/lib/cart'

export default async function CheckoutPage() {
  const cart = await getCart()
  if (!cart || cart.items.length === 0) redirect('/cart')

  // Create Payment Intent on the server before rendering
  const total = cart.items.reduce(
    (sum, item) => sum + item.product.price * item.quantity, 0
  )

  const paymentIntent = await stripe.paymentIntents.create({
    amount: Math.round(total * 100), // Stripe uses cents
    currency: 'usd',
    metadata: { cartId: cart.id },
    automatic_payment_methods: { enabled: true },
  })

  return (
    <CheckoutForm
      clientSecret={paymentIntent.client_secret!}
      total={total}
    />
  )
}
```

```typescript
// app/checkout/CheckoutForm.tsx
'use client'
import { useState } from 'react'
import { loadStripe } from '@stripe/stripe-js'
import { Elements, PaymentElement, useStripe, useElements } from '@stripe/react-stripe-js'

const stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY!)

interface CheckoutFormProps {
  clientSecret: string
  total: number
}

export function CheckoutForm({ clientSecret, total }: CheckoutFormProps) {
  return (
    <Elements stripe={stripePromise} options={{ clientSecret }}>
      <CheckoutFormInner total={total} />
    </Elements>
  )
}

function CheckoutFormInner({ total }: { total: number }) {
  const stripe = useStripe()
  const elements = useElements()
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent): Promise<void> {
    e.preventDefault()
    if (!stripe || !elements) return

    setProcessing(true)
    setError(null)

    const { error: stripeError } = await stripe.confirmPayment({
      elements,
      confirmParams: {
        return_url: `${window.location.origin}/checkout/success`,
      },
    })

    if (stripeError) {
      setError(stripeError.message ?? 'Payment failed')
      setProcessing(false)
    }
    // On success, Stripe redirects to return_url
  }

  return (
    <form onSubmit={handleSubmit}>
      <PaymentElement />
      {error && <p role="alert" className="text-red-700 text-sm mt-2">{error}</p>}
      <button type="submit" disabled={processing || !stripe}>
        {processing ? 'Processing...' : `Pay ${new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(total)}`}
      </button>
    </form>
  )
}
```

---

## Payment Intents
**When to use:** One-time payments. Create the intent server-side, confirm client-side via Elements.

```typescript
// lib/stripe.ts — Stripe singleton
import Stripe from 'stripe'

export const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
  apiVersion: '2024-06-20',
  typescript: true,
})
```

```typescript
// app/api/payment-intent/route.ts — alternative: create via API route
import { NextResponse } from 'next/server'
import { stripe } from '@/lib/stripe'
import { z } from 'zod'

const CreateIntentSchema = z.object({
  cartId: z.string().cuid(),
})

export async function POST(req: Request) {
  const body = await req.json()
  const parsed = CreateIntentSchema.safeParse(body)

  if (!parsed.success) {
    return NextResponse.json({ error: 'Invalid request' }, { status: 400 })
  }

  // Fetch cart and compute total server-side — never trust client-provided amounts
  const cart = await db.cart.findUniqueOrThrow({
    where: { id: parsed.data.cartId },
    include: { items: { include: { product: true } } },
  })

  const amount = cart.items.reduce(
    (sum, item) => sum + item.product.price * item.quantity, 0
  )

  const paymentIntent = await stripe.paymentIntents.create({
    amount: Math.round(amount * 100),
    currency: 'usd',
    metadata: { cartId: cart.id },
    automatic_payment_methods: { enabled: true },
  })

  return NextResponse.json({ clientSecret: paymentIntent.client_secret })
}
```

---

## Checkout Sessions (Stripe-Hosted)
**When to use:** When you want Stripe to handle the entire checkout UI — faster to implement, less control.

```typescript
// app/api/checkout-session/route.ts
import { stripe } from '@/lib/stripe'
import { getCart } from '@/lib/cart'

export async function POST() {
  const cart = await getCart()
  if (!cart) return new Response('No cart', { status: 400 })

  const session = await stripe.checkout.sessions.create({
    mode: 'payment',
    line_items: cart.items.map(item => ({
      price_data: {
        currency: 'usd',
        product_data: {
          name: item.product.name,
          images: [item.product.imageUrl],
        },
        unit_amount: Math.round(item.product.price * 100),
      },
      quantity: item.quantity,
    })),
    success_url: `${process.env.NEXT_PUBLIC_BASE_URL}/checkout/success?session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${process.env.NEXT_PUBLIC_BASE_URL}/cart`,
    metadata: { cartId: cart.id },
  })

  return Response.json({ url: session.url })
}
```

---

## Webhook Signature Verification
**When to use:** Every Stripe webhook handler, without exception. Unverified webhooks can be spoofed.

```typescript
// app/api/webhooks/stripe/route.ts
import { headers } from 'next/headers'
import { stripe } from '@/lib/stripe'

// CRITICAL: disable Next.js body parsing — Stripe needs the raw body string
export const config = { api: { bodyParser: false } }

export async function POST(req: Request) {
  const body = await req.text()   // raw body, not parsed JSON
  const signature = headers().get('stripe-signature')

  if (!signature) {
    return new Response('Missing stripe-signature header', { status: 400 })
  }

  let event: Stripe.Event

  try {
    event = stripe.webhooks.constructEvent(
      body,
      signature,
      process.env.STRIPE_WEBHOOK_SECRET!
    )
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error'
    console.error('Webhook signature verification failed:', message)
    return new Response(`Webhook error: ${message}`, { status: 400 })
  }

  // Handle events
  switch (event.type) {
    case 'payment_intent.succeeded':
      await handlePaymentSucceeded(event.data.object)
      break
    case 'payment_intent.payment_failed':
      await handlePaymentFailed(event.data.object)
      break
    case 'checkout.session.completed':
      await handleCheckoutCompleted(event.data.object)
      break
    default:
      // Unhandled event type — not an error, just ignore
  }

  return Response.json({ received: true })
}
```

---

## Idempotency Keys
**When to use:** Any Stripe API call that creates a resource — prevents duplicate charges if the request is retried.

```typescript
import { randomUUID } from 'crypto'

// Store idempotency key with the order to allow safe retries
const order = await db.order.create({
  data: {
    cartId: cart.id,
    idempotencyKey: randomUUID(),
    status: 'pending',
  },
})

const paymentIntent = await stripe.paymentIntents.create(
  {
    amount: Math.round(total * 100),
    currency: 'usd',
    metadata: { orderId: order.id },
  },
  {
    idempotencyKey: order.idempotencyKey, // Pass as Stripe request option
  }
)
```

---

## Webhook Idempotency
**When to use:** All webhook handlers. Stripe guarantees at-least-once delivery — your handler must be safe to run twice.

```typescript
async function handlePaymentSucceeded(
  paymentIntent: Stripe.PaymentIntent
): Promise<void> {
  const orderId = paymentIntent.metadata.orderId

  // Check if already processed — idempotency guard
  const order = await db.order.findUnique({
    where: { id: orderId },
    select: { status: true },
  })

  if (!order) {
    console.error(`Order not found: ${orderId}`)
    return
  }

  if (order.status === 'fulfilled') {
    // Already processed — safe to return without action
    return
  }

  // Use a transaction to update order + decrement inventory atomically
  await db.$transaction(async (tx) => {
    await tx.order.update({
      where: { id: orderId },
      data: {
        status: 'fulfilled',
        fulfilledAt: new Date(),
        stripePaymentIntentId: paymentIntent.id,
      },
    })
    // Decrement inventory, send confirmation email, etc.
  })
}
```

---

## Test Mode vs Live Mode
**When to use:** Test mode for all development and staging; live mode only for production.

```bash
# .env.local — development
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...   # from: stripe listen --forward-to localhost:3000/api/webhooks/stripe
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_...

# .env.production — production
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...   # from Stripe dashboard webhook endpoint
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_live_...
```

Test cards for development:
- `4242 4242 4242 4242` — succeeds
- `4000 0000 0000 0002` — card declined
- `4000 0025 0000 3155` — requires 3D Secure authentication
- `4000 0000 0000 9995` — insufficient funds

Local webhook testing:
```bash
stripe listen --forward-to localhost:3000/api/webhooks/stripe
```
