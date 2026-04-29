# Next.js / React Secure Implementation Patterns

Secure-by-default patterns for Next.js App Router and React applications. Each section shows what correct code looks like and why it matters. Load this reference when the task involves security, auth, XSS, CSRF, SSRF, Server Actions, middleware, or any vulnerability-related code.

---

## Verify Auth in Every Server Action

Every Server Action must verify the session independently. Page-level auth checks do not extend to Server Actions defined within the page. Server Actions are POST endpoints that any HTTP client can invoke directly.

```ts
// Correct: auth verified inside the action
'use server';
import { auth } from '@/auth';

export async function deleteUser(userId: string) {
    const session = await auth();
    if (!session?.user?.isAdmin) {
        throw new Error('unauthorized');
    }
    await db.user.delete({ where: { id: userId } });
}

// Correct: inline Server Action with ownership re-verification
async function cancelOrder() {
    'use server';
    const session = await auth();
    // Re-verify ownership — closure-captured params.id is attacker-controllable
    const order = await db.order.findFirst({
        where: { id: params.id, userId: session.userId },
    });
    if (!order) throw new Error('unauthorized');
    await db.order.update({ where: { id: order.id }, data: { status: 'cancelled' } });
}
```

**Why this matters**: Next.js Server Actions are RPC endpoints. An attacker who knows the action's exported name can invoke it with any arguments without visiting the page. Page-level `redirect('/login')` does nothing for the action. Inline actions that capture page `params` in their closure look scoped but the captured values are serialized into action metadata and are attacker-controllable. CVE-2025-55182 documents this class.

**Detection**:
```bash
rg -n "'use server'" .
rg -A5 "'use server'" . | rg -v 'auth\(\)|getSession\(\)|getServerSession'
```

---

## Use Middleware as Defense-in-Depth, Not Sole Auth Layer

Implement auth checks in both middleware and in each route handler or Server Action. Middleware alone is bypassable.

```ts
// middleware.ts — defense-in-depth, not sole protection
import { auth } from '@/auth';
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export async function middleware(req: NextRequest) {
    const session = await auth();
    if (!session && req.nextUrl.pathname.startsWith('/dashboard')) {
        return NextResponse.redirect(new URL('/login', req.url));
    }
    return NextResponse.next();
}

export const config = {
    // Cover both pages and API routes
    matcher: ['/dashboard/:path*', '/api/dashboard/:path*'],
};
```

```ts
// app/api/dashboard/settings/route.ts — re-verify auth in the handler
import { auth } from '@/auth';

export async function GET() {
    const session = await auth();
    if (!session) return new Response('unauthorized', { status: 401 });
    // ...proceed with verified session
}
```

**Why this matters**: CVE-2025-29927 allowed bypassing Next.js middleware entirely by sending the `x-middleware-subrequest` header. Fixed in Next.js 15.2.3, but the lesson stands: middleware is a single enforcement surface. Route handlers and Server Actions are independent surfaces that need their own checks. Middleware matcher patterns can also miss paths (`/admin` vs `/admin/`, `/api/admin/*` not covered by `/admin/:path*`).

**Detection**:
```bash
rg -n 'matcher' middleware.ts
find . -path '*/app/api/*/route.ts' -o -path '*/app/api/*/route.tsx' | xargs rg -L 'auth\(\)|getSession'
jq '.dependencies.next' package.json
```

---

## Protect API Route Handlers With Auth Checks

Every `app/api/**/route.ts` handler must verify authentication. Route handlers are HTTP endpoints accessible to any client.

```ts
// app/api/invoices/route.ts
import { auth } from '@/auth';

export async function GET() {
    const session = await auth();
    if (!session) {
        return Response.json({ error: 'unauthorized' }, { status: 401 });
    }

    // Scope queries to the authenticated user
    const invoices = await db.invoice.findMany({
        where: { userId: session.user.id },
        select: { id: true, amount: true, status: true, createdAt: true },
    });
    return Response.json(invoices);
}
```

**Why this matters**: Route handlers are independent enforcement surfaces. Even if the corresponding page has auth in `getServerSideProps` or the page component, the API route is a separate endpoint. A page that scopes data by `session.userId` provides no protection when the route handler does `db.invoice.findMany()` without scoping.

**Detection**:
```bash
find . -path '*/app/api/*/route.ts' -o -path '*/app/api/*/route.tsx' | xargs rg -L 'auth\(\)|getSession'
```

---

## Select Explicit Fields at the RSC Boundary

When passing data from Server Components to Client Components, select only the fields the UI needs. Full database rows are serialized into the HTML response.

```tsx
// Correct: select specific fields at the query level
export default async function Profile() {
    const session = await auth();
    const user = await db.user.findUnique({
        where: { id: session.userId },
        select: { id: true, displayName: true, avatarUrl: true },
    });
    return <ProfileView user={user} />;
}

// Correct: use a DTO type to enforce the boundary
type UserPublic = {
    id: string;
    displayName: string;
    avatarUrl: string | null;
};

function ProfileView({ user }: { user: UserPublic }) {
    return <div>{user.displayName}</div>;
}
```

**Why this matters**: React Server Components serialize all props into the HTML page source. A full database row includes password hashes, API tokens, internal flags, and any column added by future migrations. Even fields not rendered in the UI are visible in the page source and network response.

**Detection**:
```bash
rg -n 'findUnique\(|findFirst\(|findMany\(' . --type ts --type tsx | rg -v 'select'
rg -n 'getServerSideProps' . --type ts --type tsx | rg -v 'select'
```

---

## Configure Content Security Policy

Set a Content Security Policy that restricts script and resource sources. Next.js supports CSP via `next.config.js` headers or middleware.

```ts
// next.config.js
const securityHeaders = [
    {
        key: 'Content-Security-Policy',
        value: [
            "default-src 'self'",
            "script-src 'self' 'unsafe-eval'",  // Required for Next.js dev; remove unsafe-eval in prod
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' https://cdn.example.com data:",
            "connect-src 'self' https://api.example.com",
            "frame-ancestors 'none'",
        ].join('; '),
    },
    { key: 'X-Frame-Options', value: 'DENY' },
    { key: 'X-Content-Type-Options', value: 'nosniff' },
    { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
    { key: 'Strict-Transport-Security', value: 'max-age=31536000; includeSubDomains' },
];

module.exports = {
    async headers() {
        return [{ source: '/:path*', headers: securityHeaders }];
    },
};
```

**Why this matters**: CSP blocks inline script injection (XSS), limits where resources can be loaded from, and prevents clickjacking via `frame-ancestors`. Without CSP, a single XSS vector gives full control of the page.

**Detection**:
```bash
rg -n 'Content-Security-Policy|contentSecurityPolicy' .
rg -n 'X-Frame-Options|frame-ancestors' .
```

---

## Render Content Through React's Built-in Escaping

Use React's default JSX escaping for all user-facing content. When raw HTML rendering is genuinely needed (CMS content, markdown output), sanitize with DOMPurify or a server-side sanitizer first.

```tsx
// Correct: React JSX auto-escapes by default
function Comment({ text }: { text: string }) {
    return <p>{text}</p>;  // "<script>" renders as text, not executable HTML
}

// When raw HTML is genuinely needed (CMS content, markdown output):
import DOMPurify from 'isomorphic-dompurify';

function RichContent({ html }: { html: string }) {
    const sanitized = DOMPurify.sanitize(html, {
        ALLOWED_TAGS: ['p', 'em', 'strong', 'a', 'ul', 'ol', 'li', 'h2', 'h3'],
        ALLOWED_ATTR: ['href'],
    });
    return <div dangerouslySetInnerHTML={{ __html: sanitized }} />;
}
```

**Why this matters**: `dangerouslySetInnerHTML={{ __html: userInput }}` bypasses React's XSS protection entirely. Any `<script>`, `<img onerror=...>`, or event handler attribute in the input executes in the user's browser. React named it "dangerously" for this reason.

**Detection**:
```bash
rg -n 'dangerouslySetInnerHTML' . --type ts --type tsx
rg -n 'DOMPurify|sanitize' . --type ts --type tsx
```

---

## Restrict Image Optimization Remote Patterns

Configure `images.remotePatterns` with explicit hostnames. Never use wildcard patterns.

```ts
// next.config.js
module.exports = {
    images: {
        remotePatterns: [
            { protocol: 'https', hostname: 'cdn.example.com' },
            { protocol: 'https', hostname: 'images.unsplash.com' },
        ],
    },
};
```

**Why this matters**: `remotePatterns: [{ hostname: '**' }]` turns `/_next/image` into an open proxy. `/_next/image?url=http://169.254.169.254/latest/meta-data/` exfiltrates cloud metadata through the image optimization endpoint (GHSA-rvpw-p7vw-wj3m).

**Detection**:
```bash
rg -n 'remotePatterns' next.config.*
rg -n "hostname.*\*\*" next.config.*
```

---

## Validate Server Action Inputs With Zod

Validate all Server Action arguments with Zod schemas. Server Actions receive arbitrary data from any HTTP client.

```ts
'use server';
import { z } from 'zod';
import { auth } from '@/auth';

const UpdateProfileSchema = z.object({
    displayName: z.string().min(1).max(100),
    bio: z.string().max(500).optional(),
});

export async function updateProfile(rawInput: unknown) {
    const session = await auth();
    if (!session) throw new Error('unauthorized');

    const input = UpdateProfileSchema.parse(rawInput);
    await db.user.update({
        where: { id: session.user.id },
        data: input,
    });
}
```

**Why this matters**: Server Action arguments arrive as deserialized form data or JSON. Without validation, type confusion, extra fields (mass assignment), and prototype pollution payloads pass through to the database layer.

**Detection**:
```bash
rg -A10 "'use server'" . | rg 'export async function' | rg -v 'parse\|safeParse\|validate'
```

---

## Validate CSRF in Server Actions

Next.js App Router Server Actions include built-in CSRF protection via the action ID mechanism. Verify you are not bypassing it by accepting plain POST requests to Server Action endpoints.

```ts
// Correct: use Server Actions through the framework's form binding
// The framework automatically includes CSRF protection

// Client component
'use client';
import { updateProfile } from './actions';

export function ProfileForm() {
    return (
        <form action={updateProfile}>
            <input name="displayName" />
            <button type="submit">Save</button>
        </form>
    );
}
```

```ts
// For API routes that accept POST from third parties (webhooks),
// verify the request source via signature
import crypto from 'crypto';

export async function POST(req: Request) {
    const body = await req.text();
    const signature = req.headers.get('x-webhook-signature');
    const expected = crypto
        .createHmac('sha256', process.env.WEBHOOK_SECRET!)
        .update(body)
        .digest('hex');

    if (!crypto.timingSafeEqual(Buffer.from(signature ?? ''), Buffer.from(expected))) {
        return Response.json({ error: 'invalid signature' }, { status: 401 });
    }
    // ...process webhook
}
```

**Why this matters**: Without CSRF protection, any website can submit forms to your endpoints using the visitor's authenticated session. Next.js Server Actions include CSRF tokens automatically when used through the framework. Custom POST handlers need their own protection.

**Detection**:
```bash
rg -n "method.*POST|POST.*req" . --type ts | rg 'route\.ts'
rg -n 'timingSafeEqual|createHmac' . --type ts
```
