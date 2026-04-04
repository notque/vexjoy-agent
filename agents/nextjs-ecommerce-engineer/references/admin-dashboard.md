# Admin Dashboard Reference
<!-- Loaded by nextjs-ecommerce-engineer when task involves admin UI, order management, product CRUD, inventory tracking, analytics, or role-based access -->

Admin dashboards are internal tools where correctness and auditability matter more than aesthetic polish. Every destructive action needs confirmation; every mutation needs authorization.

## Role-Based Access Control
**When to use:** Any admin route. Gate at the middleware level and repeat the check in Server Components — defense in depth.

```typescript
// lib/auth.ts — extend NextAuth session with role
import { DefaultSession } from 'next-auth'

declare module 'next-auth' {
  interface Session {
    user: DefaultSession['user'] & {
      id: string
      role: 'customer' | 'admin' | 'staff'
    }
  }
}

export const authOptions: NextAuthOptions = {
  callbacks: {
    session({ session, token }) {
      return {
        ...session,
        user: {
          ...session.user,
          id: token.sub!,
          role: token.role as 'customer' | 'admin' | 'staff',
        },
      }
    },
    jwt({ token, user }) {
      if (user) token.role = (user as any).role
      return token
    },
  },
}
```

```typescript
// middleware.ts — block non-admin at the edge
export async function middleware(request: NextRequest) {
  if (!request.nextUrl.pathname.startsWith('/admin')) return NextResponse.next()

  const token = await getToken({ req: request })
  if (!token || token.role !== 'admin') {
    return NextResponse.redirect(new URL('/', request.url))
  }

  return NextResponse.next()
}

export const config = { matcher: ['/admin/:path*'] }
```

```typescript
// app/admin/layout.tsx — secondary check in Server Component
export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const session = await getServerSession(authOptions)

  // Belt and suspenders — middleware already blocked, but verify again
  if (session?.user?.role !== 'admin') notFound()

  return <div className="admin-shell">{children}</div>
}
```

---

## Order Management
**When to use:** Admin view of all orders with filtering, status updates, and fulfillment tracking.

```typescript
// app/admin/orders/page.tsx
import { db } from '@/lib/db'

interface OrdersPageProps {
  searchParams: { status?: string; page?: string }
}

export default async function OrdersPage({ searchParams }: OrdersPageProps) {
  const page = parseInt(searchParams.page ?? '1')
  const pageSize = 25
  const status = searchParams.status

  const [orders, total] = await Promise.all([
    db.order.findMany({
      where: status ? { status: status as OrderStatus } : undefined,
      include: {
        user: { select: { name: true, email: true } },
        items: {
          include: { product: { select: { name: true } } },
        },
      },
      orderBy: { createdAt: 'desc' },
      skip: (page - 1) * pageSize,
      take: pageSize,
    }),
    db.order.count({ where: status ? { status: status as OrderStatus } : undefined }),
  ])

  return (
    <div>
      <OrderFilters currentStatus={status} />
      <OrderTable orders={orders} />
      <Pagination page={page} total={total} pageSize={pageSize} />
    </div>
  )
}
```

```typescript
// actions/admin/orders.ts — update order status
'use server'
import { z } from 'zod'
import { requireAdmin } from '@/lib/auth-helpers'

const UpdateOrderSchema = z.object({
  orderId: z.string().cuid(),
  status: z.enum(['pending', 'processing', 'shipped', 'delivered', 'refunded', 'cancelled']),
  note: z.string().max(500).optional(),
})

export async function updateOrderStatus(formData: FormData) {
  await requireAdmin() // throws if not admin

  const parsed = UpdateOrderSchema.safeParse({
    orderId: formData.get('orderId'),
    status: formData.get('status'),
    note: formData.get('note'),
  })

  if (!parsed.success) throw new Error('Invalid form data')

  await db.$transaction(async (tx) => {
    await tx.order.update({
      where: { id: parsed.data.orderId },
      data: { status: parsed.data.status },
    })
    // Audit log — every status change is traceable
    await tx.orderAuditLog.create({
      data: {
        orderId: parsed.data.orderId,
        previousStatus: 'unknown', // fetch before update in real usage
        newStatus: parsed.data.status,
        note: parsed.data.note,
        adminId: (await getServerSession(authOptions))!.user.id,
      },
    })
  })

  revalidatePath('/admin/orders')
}
```

---

## Product CRUD
**When to use:** Admin product management — create, edit, archive products. Use `archive` instead of `delete` to preserve order history references.

```typescript
// actions/admin/products.ts
'use server'
import { z } from 'zod'
import { requireAdmin } from '@/lib/auth-helpers'

const ProductSchema = z.object({
  name:        z.string().min(1).max(200),
  description: z.string().max(5000),
  price:       z.number().positive().multipleOf(0.01),
  stock:       z.number().int().min(0),
  categoryId:  z.string().cuid(),
  published:   z.boolean().default(false),
})

export async function createProduct(formData: FormData) {
  await requireAdmin()

  const parsed = ProductSchema.safeParse({
    name:        formData.get('name'),
    description: formData.get('description'),
    price:       parseFloat(formData.get('price') as string),
    stock:       parseInt(formData.get('stock') as string),
    categoryId:  formData.get('categoryId'),
    published:   formData.get('published') === 'true',
  })

  if (!parsed.success) {
    return { success: false, errors: parsed.error.flatten().fieldErrors }
  }

  const product = await db.product.create({ data: parsed.data })

  revalidatePath('/admin/products')
  revalidatePath('/products') // invalidate public product listing

  return { success: true, productId: product.id }
}

export async function archiveProduct(productId: string) {
  await requireAdmin()

  // Soft delete — preserve for order history
  await db.product.update({
    where: { id: productId },
    data: { archivedAt: new Date(), published: false },
  })

  revalidatePath('/admin/products')
  revalidatePath('/products')
}
```

---

## Inventory Tracking
**When to use:** Admin inventory view showing current stock levels, low-stock alerts, and restock history.

```typescript
// app/admin/inventory/page.tsx
export default async function InventoryPage() {
  const LOW_STOCK_THRESHOLD = 5

  const products = await db.product.findMany({
    where: { archivedAt: null },
    select: {
      id: true,
      name: true,
      stock: true,
      sku: true,
    },
    orderBy: { stock: 'asc' }, // lowest stock first
  })

  const lowStock = products.filter(p => p.stock <= LOW_STOCK_THRESHOLD)

  return (
    <div>
      {lowStock.length > 0 && (
        <div role="alert" className="rounded bg-amber-50 border border-amber-200 p-4 mb-6">
          <h2 className="font-semibold text-amber-900">
            {lowStock.length} product{lowStock.length > 1 ? 's' : ''} low on stock
          </h2>
          <ul className="mt-2 text-sm text-amber-800">
            {lowStock.map(p => (
              <li key={p.id}>{p.name} — {p.stock} remaining</li>
            ))}
          </ul>
        </div>
      )}
      <InventoryTable products={products} threshold={LOW_STOCK_THRESHOLD} />
    </div>
  )
}
```

```typescript
// actions/admin/inventory.ts — manual stock adjustment
export async function adjustStock(productId: string, delta: number, reason: string) {
  await requireAdmin()

  await db.$transaction(async (tx) => {
    const product = await tx.product.update({
      where: { id: productId },
      data: { stock: { increment: delta } },
      select: { stock: true },
    })

    if (product.stock < 0) {
      throw new Error('Stock cannot be negative')
    }

    await tx.inventoryLog.create({
      data: {
        productId,
        delta,
        reason,
        adminId: (await getServerSession(authOptions))!.user.id,
      },
    })
  })

  revalidatePath('/admin/inventory')
}
```

---

## Analytics Dashboard
**When to use:** Admin overview of revenue, order volume, and top products. Use aggregation queries rather than loading all records.

```typescript
// app/admin/analytics/page.tsx
export default async function AnalyticsPage() {
  const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)

  const [revenue, orderCount, topProducts] = await Promise.all([
    // Total revenue last 30 days
    db.order.aggregate({
      where: {
        createdAt: { gte: thirtyDaysAgo },
        status: { in: ['fulfilled', 'shipped', 'delivered'] },
      },
      _sum: { total: true },
    }),

    // Order count last 30 days
    db.order.count({
      where: { createdAt: { gte: thirtyDaysAgo } },
    }),

    // Top 5 products by units sold last 30 days
    db.orderItem.groupBy({
      by: ['productId'],
      where: {
        order: { createdAt: { gte: thirtyDaysAgo } },
      },
      _sum: { quantity: true },
      orderBy: { _sum: { quantity: 'desc' } },
      take: 5,
    }),
  ])

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <MetricCard
        label="Revenue (30d)"
        value={new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
          .format(revenue._sum.total ?? 0)}
      />
      <MetricCard label="Orders (30d)" value={orderCount.toString()} />
      <TopProductsList items={topProducts} />
    </div>
  )
}
```

---

## Audit Logging
**When to use:** Any destructive or financial admin action. Audit logs answer "who did what and when" during incident investigation.

```typescript
// lib/audit.ts
interface AuditEntry {
  action: string
  entityType: string
  entityId: string
  adminId: string
  before?: Record<string, unknown>
  after?: Record<string, unknown>
}

export async function auditLog(entry: AuditEntry): Promise<void> {
  await db.auditLog.create({
    data: {
      ...entry,
      before: entry.before ?? undefined,
      after:  entry.after ?? undefined,
      createdAt: new Date(),
    },
  })
}

// Usage
await auditLog({
  action: 'order.status_changed',
  entityType: 'order',
  entityId: orderId,
  adminId: session.user.id,
  before: { status: previousStatus },
  after:  { status: newStatus },
})
```
