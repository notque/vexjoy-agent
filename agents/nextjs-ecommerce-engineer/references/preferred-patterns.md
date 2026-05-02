# E-commerce Review Patterns
<!-- Loaded by nextjs-ecommerce-engineer when reviewing e-commerce code for security, correctness, or reliability issues -->

E-commerce mistakes that cause real damage. Each has a canonical fix.

## Client-Side Price Calculation
**What it looks like:**

```typescript
// WRONG: Price calculated in the browser
function CartSummary({ items }: { items: CartItem[] }) {
  const total = items.reduce(
    (sum, item) => sum + item.price * item.quantity, 0
  )
  return (
    <form action="/api/checkout" method="POST">
      <input type="hidden" name="total" value={total} />
      <button type="submit">Pay ${total}</button>
    </form>
  )
}
```

**Why wrong:** User opens DevTools, modifies hidden input, pays $0.01 for any order.

**Fix:** Calculate all prices server-side. Never trust client-provided prices.

```typescript
// CORRECT: Price calculated server-side from product IDs
// app/api/checkout/route.ts
export async function POST(req: Request) {
  const { cartId } = await req.json()

  // Fetch prices from database — never use client-provided amounts
  const cart = await db.cart.findUniqueOrThrow({
    where: { id: cartId },
    include: { items: { include: { product: { select: { price: true } } } } },
  })

  const amount = cart.items.reduce(
    (sum, item) => sum + item.product.price * item.quantity, 0
  )

  const paymentIntent = await stripe.paymentIntents.create({
    amount: Math.round(amount * 100),
    currency: 'usd',
  })

  return Response.json({ clientSecret: paymentIntent.client_secret })
}
```

---

## Missing Webhook Idempotency
**What it looks like:**

```typescript
// WRONG: No idempotency check — fulfills order every time webhook fires
export async function POST(req: Request) {
  const event = await verifyWebhook(req)

  if (event.type === 'payment_intent.succeeded') {
    const { orderId } = event.data.object.metadata
    await fulfillOrder(orderId)           // runs again on retry
    await sendConfirmationEmail(orderId)  // user gets duplicate emails
    await decrementInventory(orderId)     // inventory decremented twice
  }

  return Response.json({ received: true })
}
```

**Why wrong:** Stripe retries on timeout or 5xx. Without idempotency: duplicate orders, double inventory depletion, email floods.

**Fix:** Check order status before fulfilling.

```typescript
// CORRECT: Idempotency guard
if (event.type === 'payment_intent.succeeded') {
  const orderId = event.data.object.metadata.orderId
  const order = await db.order.findUnique({ where: { id: orderId } })

  if (!order || order.status === 'fulfilled') return Response.json({ received: true })

  await db.$transaction(async (tx) => {
    await tx.order.update({ where: { id: orderId }, data: { status: 'fulfilled' } })
    await decrementInventory(tx, orderId)
  })

  await sendConfirmationEmail(orderId) // outside transaction — non-critical
}
```

---

## Cart Race Conditions
**What it looks like:**

```typescript
// WRONG: Read-then-write without atomicity
export async function addToCart(productId: string) {
  const product = await db.product.findUnique({ where: { id: productId } })

  if (product.stock < 1) throw new Error('Out of stock')

  // RACE: another request can run here, also seeing stock > 0
  await db.cartItem.create({ data: { productId, quantity: 1 } })
  await db.product.update({
    where: { id: productId },
    data: { stock: { decrement: 1 } },
  })
}
```

**Why wrong:** Two simultaneous requests both see stock = 1, both pass the check, both decrement to stock = -1.

**Fix:** Database transaction with atomic update and constraint check.

```typescript
// CORRECT: Atomic check-and-decrement
await db.$transaction(async (tx) => {
  const result = await tx.product.updateMany({
    where: { id: productId, stock: { gt: 0 } }, // guard in the WHERE clause
    data: { stock: { decrement: 1 } },
  })

  if (result.count === 0) throw new Error('Out of stock')

  await tx.cartItem.create({ data: { cartId, productId, quantity: 1 } })
})
```

---

## Unsanitized Product Data in Rendered HTML
**What it looks like:**

```tsx
// WRONG: Rendering product description as raw HTML
function ProductDescription({ description }: { description: string }) {
  return <div dangerouslySetInnerHTML={{ __html: description }} />
}
```

**Why wrong:** Product descriptions from CMS or user input are XSS vectors.

**Fix:** Sanitize or render as plain text. Only use `dangerouslySetInnerHTML` with trusted, sanitized content.

```typescript
// CORRECT: Sanitize before rendering
import DOMPurify from 'isomorphic-dompurify'

function ProductDescription({ description }: { description: string }) {
  const clean = DOMPurify.sanitize(description, {
    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li'],
    ALLOWED_ATTR: [],
  })
  return <div dangerouslySetInnerHTML={{ __html: clean }} />
}

// Or better — use a Markdown renderer with restricted output
import ReactMarkdown from 'react-markdown'

function ProductDescription({ description }: { description: string }) {
  return <ReactMarkdown>{description}</ReactMarkdown>
}
```

---

## Storing Stripe Secret Key Client-Side
**What it looks like:**

```typescript
// WRONG: Secret key exposed in NEXT_PUBLIC_ variable
const stripe = new Stripe(process.env.NEXT_PUBLIC_STRIPE_SECRET_KEY!)
```

**Why wrong:** `NEXT_PUBLIC_` variables are bundled into client JS. Anyone can read the secret key from the browser.

**Fix:** Never prefix Stripe secret key with `NEXT_PUBLIC_`. Only the publishable key goes to the client.

```typescript
// CORRECT: Secret key server-side only
// lib/stripe.ts (server-only file)
import Stripe from 'stripe'
export const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!) // no NEXT_PUBLIC_

// components/CheckoutForm.tsx (client component)
const stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY!) // pk_ key only
```

---

## Skipping Inventory Validation Before Order Creation
**What it looks like:**

```typescript
// WRONG: Create order then check stock
async function createOrder(cartId: string) {
  const order = await db.order.create({ data: { cartId, status: 'pending' } })

  // Check stock AFTER creating the order — too late
  const stockIssues = await checkStock(cartId)
  if (stockIssues.length > 0) {
    await db.order.delete({ where: { id: order.id } })
    throw new Error('Out of stock')
  }
}
```

**Why wrong:** Creates/deletes records unnecessarily. Between create and delete, another process may act on the "pending" order.

**Fix:** Validate stock before creating anything.

```typescript
// CORRECT: Validate first, create after
async function createOrder(cartId: string) {
  const { valid, outOfStock } = await validateCartStock(cartId)
  if (!valid) throw new Error(`Out of stock: ${outOfStock.map(i => i.name).join(', ')}`)

  return db.$transaction(async (tx) => {
    // Decrement stock atomically with order creation
    for (const item of cartItems) {
      await tx.product.updateMany({
        where: { id: item.productId, stock: { gte: item.quantity } },
        data: { stock: { decrement: item.quantity } },
      })
    }
    return tx.order.create({ data: { cartId, status: 'confirmed' } })
  })
}
```

---

## Exposing Order Details Without Authorization
**What it looks like:**

```typescript
// WRONG: Any authenticated user can view any order
export default async function OrderPage({ params }: { params: { id: string } }) {
  const order = await db.order.findUnique({ where: { id: params.id } })
  return <OrderDetail order={order} />
}
```

**Why wrong:** User can enumerate order IDs and view other customers' data.

**Fix:** Always scope queries to the current user's ID.

```typescript
// CORRECT: Scope to current user
export default async function OrderPage({ params }: { params: { id: string } }) {
  const session = await getServerSession(authOptions)
  if (!session?.user?.id) redirect('/login')

  const order = await db.order.findFirst({
    where: {
      id: params.id,
      userId: session.user.id, // scope to current user
    },
  })

  if (!order) notFound() // same response for not found and unauthorized — prevents enumeration

  return <OrderDetail order={order} />
}
```
