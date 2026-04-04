# Shopping Cart Patterns Reference
<!-- Loaded by nextjs-ecommerce-engineer when task involves cart state, add-to-cart, quantity updates, cart persistence, or abandoned cart -->

The shopping cart is the most stateful part of any e-commerce site. The fundamental tension: guests have no server identity, authenticated users want their cart everywhere.

## Cart State Architecture
**When to use:** Deciding where cart state lives. The answer depends on whether the user is authenticated.

```
Guest user:     localStorage -> sync to DB on login
Authenticated:  DB is source of truth, cached in React state
Both:           Cart ID in cookie survives browser refresh without login
```

```typescript
// lib/cart.ts — server-side cart resolution
import { cookies } from 'next/headers'
import { db } from '@/lib/db'

export async function getCart() {
  const cookieStore = cookies()
  const cartId = cookieStore.get('cart-id')?.value

  if (!cartId) return null

  return db.cart.findUnique({
    where: { id: cartId },
    include: {
      items: {
        include: { product: true },
        orderBy: { createdAt: 'asc' },
      },
    },
  })
}

export async function getOrCreateCart() {
  const existing = await getCart()
  if (existing) return existing

  const cart = await db.cart.create({ data: {} })

  // Set cart cookie — persists across page navigations
  cookies().set('cart-id', cart.id, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: 60 * 60 * 24 * 30, // 30 days
  })

  return cart
}
```

---

## Context vs Server State
**When to use:** Context for UI-only cart state (drawer open/closed, item count badge). Server state (React Query, SWR, or Server Actions with revalidation) for actual cart data.

```typescript
// context/CartContext.tsx — UI state only, not cart data
'use client'
import { createContext, useContext, useState } from 'react'

interface CartUIState {
  isOpen: boolean
  openCart: () => void
  closeCart: () => void
}

const CartUIContext = createContext<CartUIState | null>(null)

export function CartUIProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <CartUIContext.Provider value={{
      isOpen,
      openCart:  () => setIsOpen(true),
      closeCart: () => setIsOpen(false),
    }}>
      {children}
    </CartUIContext.Provider>
  )
}

export function useCartUI(): CartUIState {
  const ctx = useContext(CartUIContext)
  if (!ctx) throw new Error('useCartUI must be used within CartUIProvider')
  return ctx
}
```

Actual cart data comes from a Server Component via `getCart()`, not from context.

---

## Optimistic Updates
**When to use:** Adding/removing items. The UI should respond instantly — don't wait for the server roundtrip to update the count or remove the item.

```typescript
// components/AddToCartButton.tsx
'use client'
import { useOptimistic, useTransition } from 'react'
import { addToCartAction } from '@/actions/cart'

interface CartItem {
  productId: string
  quantity: number
}

interface AddToCartButtonProps {
  productId: string
  initialCount: number
}

export function AddToCartButton({ productId, initialCount }: AddToCartButtonProps) {
  const [isPending, startTransition] = useTransition()
  const [optimisticCount, addOptimistic] = useOptimistic(
    initialCount,
    (state: number, delta: number) => state + delta
  )

  function handleClick(): void {
    addOptimistic(1) // Update UI immediately
    startTransition(async () => {
      await addToCartAction(productId) // Server mutation
    })
  }

  return (
    <button
      onClick={handleClick}
      disabled={isPending}
      aria-busy={isPending}
    >
      Add to cart {optimisticCount > 0 && `(${optimisticCount})`}
    </button>
  )
}
```

---

## Quantity Changes
**When to use:** Cart page where users can increase/decrease quantities.

```typescript
// actions/cart.ts
'use server'
import { revalidatePath } from 'next/cache'
import { db } from '@/lib/db'
import { getOrCreateCart } from '@/lib/cart'
import { z } from 'zod'

const UpdateQuantitySchema = z.object({
  productId: z.string().cuid(),
  quantity:  z.number().int().min(0).max(99),
})

export async function updateCartQuantity(
  productId: string,
  quantity: number
): Promise<{ success: boolean; error?: string }> {
  const parsed = UpdateQuantitySchema.safeParse({ productId, quantity })
  if (!parsed.success) {
    return { success: false, error: 'Invalid quantity' }
  }

  const cart = await getOrCreateCart()

  if (quantity === 0) {
    // Remove the item
    await db.cartItem.deleteMany({
      where: { cartId: cart.id, productId },
    })
  } else {
    await db.cartItem.upsert({
      where: { cartId_productId: { cartId: cart.id, productId } },
      update: { quantity },
      create: { cartId: cart.id, productId, quantity },
    })
  }

  revalidatePath('/cart')
  return { success: true }
}
```

---

## Cart Persistence (Cookies + localStorage Strategy)
**When to use:** Hybrid approach for maximum resilience — cookie for server-side reads, localStorage for offline/fast client-side access.

```typescript
// lib/cart-client.ts — client-side cart operations
const CART_STORAGE_KEY = 'cart-items-preview'

interface CartPreview {
  count: number
  updatedAt: number
}

export function saveCartPreview(count: number): void {
  try {
    const preview: CartPreview = { count, updatedAt: Date.now() }
    localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(preview))
  } catch {
    // localStorage unavailable (private browsing, storage full) — non-fatal
  }
}

export function getCartPreview(): number {
  try {
    const raw = localStorage.getItem(CART_STORAGE_KEY)
    if (!raw) return 0
    const preview = JSON.parse(raw) as CartPreview
    // Treat as stale after 1 hour
    if (Date.now() - preview.updatedAt > 3600_000) return 0
    return preview.count
  } catch {
    return 0
  }
}
```

---

## Abandoned Cart Detection
**When to use:** When email automation is configured. Track the last cart activity timestamp; trigger a reminder email after a configurable inactivity window.

```typescript
// actions/cart.ts — track last activity on every mutation
async function touchCartActivity(cartId: string): Promise<void> {
  await db.cart.update({
    where: { id: cartId },
    data: { lastActivityAt: new Date() },
  })
}

// Cron job or scheduled function — find abandoned carts
export async function findAbandonedCarts(inactiveMinutes = 60) {
  const cutoff = new Date(Date.now() - inactiveMinutes * 60_000)

  return db.cart.findMany({
    where: {
      lastActivityAt: { lt: cutoff },
      abandonedEmailSentAt: null,
      items: { some: {} },       // has at least one item
      user: { isNot: null },     // must have email to notify
    },
    include: {
      user: { select: { email: true, name: true } },
      items: { include: { product: true } },
    },
  })
}
```

---

## Cart Race Conditions
**When to use:** Any time two tabs or two requests could modify the same cart simultaneously.

Use Prisma transactions for atomic check-and-modify:

```typescript
// actions/cart.ts — atomic add with stock check
export async function addToCart(productId: string, quantity = 1) {
  const cart = await getOrCreateCart()

  await db.$transaction(async (tx) => {
    // Check stock inside the transaction
    const product = await tx.product.findUniqueOrThrow({
      where: { id: productId },
      select: { stock: true, name: true },
    })

    if (product.stock < quantity) {
      throw new Error(`Insufficient stock for ${product.name}`)
    }

    await tx.cartItem.upsert({
      where: { cartId_productId: { cartId: cart.id, productId } },
      update: { quantity: { increment: quantity } },
      create: { cartId: cart.id, productId, quantity },
    })
  })

  revalidatePath('/cart')
}
```
