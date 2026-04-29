# Node.js Secure Implementation Patterns

Secure-by-default patterns for Node.js backend applications. Each section shows what correct code looks like and why it matters. Load this reference when the task involves security, auth, injection, XSS, CSRF, SSRF, prototype pollution, or any vulnerability-related code.

---

## Use execFile Instead of exec for Process Spawning

Use `execFile` or `spawn` (with `shell: false`, the default) for subprocess calls. These pass arguments as separate argv entries without invoking a shell.

```ts
import { execFile, execFileSync, spawn } from 'child_process';

// Correct: execFile passes args directly to the binary
execFile('git', ['clone', '--', userUrl], (err, stdout) => {
    if (err) console.error('clone failed:', err.message);
});

// Correct: spawn with default shell: false
const child = spawn('convert', [userInput, 'output.png']);

// Correct: execFileSync for synchronous operations
const output = execFileSync('git', ['log', '--oneline', '-5']);
```

**Why this matters**: `exec` and `execSync` always invoke a shell, where metacharacters (`;`, `|`, `&`, `$()`) are interpreted. On Windows, `spawn`/`execFile` targeting `.bat`/`.cmd` files implicitly route through `cmd.exe` regardless of the `shell` option (CVE-2024-27980, fixed in Node 18.20.0 / 20.12.0 / 21.7.0).

**Detection**:
```bash
rg -n '\bexec\(|\bexecSync\(' . --type ts --type js
rg -n 'shell:\s*true' . --type ts --type js
```

---

## Prevent Prototype Pollution With Safe Object Handling

Use Zod or similar schema validation before merging user input into objects. For key-value stores with user-controlled keys, use `Map` or `Object.create(null)`.

```ts
import { z } from 'zod';

// Correct: validate shape with Zod before any merge
const ConfigSchema = z.object({
    theme: z.enum(['light', 'dark']).optional(),
    language: z.string().max(5).optional(),
});
const validated = ConfigSchema.parse(req.body);
const merged = { ...defaultConfig, ...validated };

// Correct: use Map for user-controlled keys
const userSettings = new Map<string, unknown>();
for (const [key, value] of Object.entries(validatedInput)) {
    userSettings.set(key, value);
}

// Correct: prototype-free object for lookups
const lookup = Object.create(null) as Record<string, string>;
```

**Why this matters**: Deep-merging `req.body` into objects without filtering `__proto__`, `constructor`, or `prototype` keys pollutes `Object.prototype`. Downstream code that reads properties from shared objects (template engines, HTTP clients, auth checks) picks up attacker-injected values. CVE-2019-10744 (lodash `defaultsDeep`), CVE-2019-19919 (Handlebars compile-time RCE), and CVE-2026-40175 (axios header injection bypassing IMDSv2) demonstrate the full attack chain.

**Detection**:
```bash
rg -n '_\.(merge|defaultsDeep|set|setWith)\(.*req\.' . --type ts --type js
rg -n 'Object\.assign\(.*req\.' . --type ts --type js
rg -n 'for\s*\(.*Object\.keys\(.*req\.' . --type ts --type js
```

---

## Order Express Middleware for Auth Before Routes

Mount authentication middleware before route handlers. Middleware executes in registration order; auth mounted after a route leaves that route unprotected.

```ts
import express from 'express';
import helmet from 'helmet';
import rateLimit from 'express-rate-limit';

const app = express();

// 1. Security headers first
app.use(helmet());

// 2. Body parsing
app.use(express.json({ strict: true }));

// 3. Rate limiting
app.use('/api/', rateLimit({
    windowMs: 60_000,
    max: 100,
    standardHeaders: true,
}));

// 4. Auth middleware BEFORE routes
app.use('/api/', authMiddleware);

// 5. Routes come last
app.use('/api/users', userRouter);
app.use('/api/invoices', invoiceRouter);

// 6. Error handler at the end
app.use(errorHandler);
```

**Why this matters**: Express processes middleware in the order registered. If a route is mounted before auth middleware, requests to that route bypass authentication entirely. This is the Express-equivalent of "forced browsing."

**Detection**:
```bash
rg -n 'app\.use\(' . --type ts --type js | head -30
```

---

## Pin JWT Algorithms and Verify Claims

Always pass an explicit `algorithms` allowlist when verifying JWTs. Verify `exp`, `aud`, and `iss` claims. Use short-lived access tokens with refresh tokens for revocability.

```ts
import jwt from 'jsonwebtoken';

// Correct: pin algorithm, verify standard claims
const payload = jwt.verify(token, publicKey, {
    algorithms: ['RS256'],        // Pin to a single algorithm family
    audience: 'api.example.com',  // Verify audience
    issuer: 'auth.example.com',   // Verify issuer
});

// Correct: sign with explicit algorithm and short expiry
const token = jwt.sign(
    { sub: user.id, role: user.role },
    privateKey,
    {
        algorithm: 'RS256',
        expiresIn: '15m',         // Short-lived access token
        audience: 'api.example.com',
        issuer: 'auth.example.com',
    },
);
```

**Why this matters**: `jwt.verify(token, key)` without `algorithms` allows the attacker to choose the algorithm. CVE-2022-23540 and CVE-2022-23541 (jsonwebtoken < 9.0.0) allowed `alg: none` verification and RS-to-HS key confusion. CVE-2022-29217 (PyJWT) had the same class of bug. Never include `"none"` in the algorithms list. Never mix HS and RS algorithms with a single key.

**Detection**:
```bash
rg -n 'jwt\.verify\(' . --type ts --type js | rg -v 'algorithms'
rg -n 'jwt\.decode\(' . --type ts --type js
rg -n "algorithms.*none" . --type ts --type js
```

---

## Validate Outbound URLs to Prevent SSRF

Resolve hostnames to IPs and validate against private/internal ranges before making outbound requests. Disable redirect following or re-validate on each hop.

```ts
import { lookup } from 'dns/promises';
import ipaddr from 'ipaddr.js';

const DISALLOWED_RANGES = ['private', 'linkLocal', 'loopback', 'uniqueLocal', 'unspecified'];

async function safeFetch(userUrl: string): Promise<Response> {
    const url = new URL(userUrl);
    if (url.protocol !== 'https:' && url.protocol !== 'http:') {
        throw new Error('disallowed scheme');
    }
    const { address } = await lookup(url.hostname);
    const ip = ipaddr.parse(address);
    if (DISALLOWED_RANGES.includes(ip.range())) {
        throw new Error('disallowed IP range');
    }
    return fetch(url, { redirect: 'manual' });
}
```

**Why this matters**: User-controlled URLs reach internal services including cloud metadata endpoints (`169.254.169.254`). The Capital One breach (2019) stole IAM credentials via SSRF. String-based blocklists fail against DNS rebinding, IP encoding tricks, and redirects. CVE-2020-28168 (axios redirect bypass) and CVE-2026-40175 (axios header pollution to IMDS bypass) are Node-specific examples.

**Detection**:
```bash
rg -n 'fetch\(.*req\.|axios\.\w+\(.*req\.|got\(.*req\.' . --type ts --type js
rg -n "redirect.*'follow'|redirect.*'manual'" . --type ts --type js
```

---

## Validate All Input With Zod Schemas

Validate request body, query parameters, and path parameters with Zod schemas before processing. Treat all client data as untrusted.

```ts
import { z } from 'zod';

const CreateUserSchema = z.object({
    email: z.string().email(),
    displayName: z.string().min(1).max(100),
    role: z.enum(['user', 'editor']),  // Allowlist, not arbitrary string
});

app.post('/api/users', async (req, res) => {
    const result = CreateUserSchema.safeParse(req.body);
    if (!result.success) {
        return res.status(422).json({
            errors: result.error.flatten().fieldErrors,
        });
    }
    const { email, displayName, role } = result.data;
    // ...proceed with validated data
});
```

**Why this matters**: `req.body` without validation enables type confusion (string where number expected), mass assignment (extra fields like `isAdmin: true`), and prototype pollution (nested `__proto__` keys). Zod schemas reject unexpected fields by default and coerce types safely.

**Detection**:
```bash
rg -n 'req\.body\b' . --type ts --type js | rg -v 'parse\|safeParse\|validate'
rg -n 'req\.query\b|req\.params\b' . --type ts --type js | rg -v 'parse\|safeParse'
```

---

## Configure Security Headers With Helmet

Use Helmet middleware for security headers. Configure Content Security Policy explicitly for your application.

```ts
import helmet from 'helmet';

app.use(helmet({
    contentSecurityPolicy: {
        directives: {
            defaultSrc: ["'self'"],
            scriptSrc: ["'self'"],
            styleSrc: ["'self'", "'unsafe-inline'"],  // Only if CSS-in-JS requires it
            imgSrc: ["'self'", "https://cdn.example.com"],
            connectSrc: ["'self'", "https://api.example.com"],
        },
    },
    crossOriginEmbedderPolicy: true,
    crossOriginOpenerPolicy: true,
    crossOriginResourcePolicy: { policy: "same-site" },
    hsts: { maxAge: 31536000, includeSubDomains: true },
}));
```

**Why this matters**: Security headers prevent entire vulnerability classes: CSP blocks inline script injection (XSS), `X-Frame-Options`/`frame-ancestors` prevents clickjacking, HSTS forces HTTPS, and CORP/COEP prevent speculative execution side-channel attacks.

**Detection**:
```bash
rg -n 'helmet|Content-Security-Policy|X-Frame-Options' . --type ts --type js
```

---

## Serve Files With Path Containment

When serving user-requested files, resolve the path and verify it stays within the intended base directory.

```ts
import path from 'path';
import fs from 'fs';

const BASE = path.resolve('/var/app/exports');

app.get('/download', (req, res) => {
    const name = String(req.query.name);
    const target = path.resolve(BASE, name);

    // Containment check: resolved path must start with base directory
    if (!target.startsWith(BASE + path.sep)) {
        return res.sendStatus(403);
    }

    res.sendFile(target);
});

// Alternative: use Express root option (has built-in traversal rejection)
app.get('/download/:name', (req, res) => {
    res.sendFile(req.params.name, { root: '/var/app/exports' });
});
```

**Why this matters**: `path.join('/base', userInput)` returns `/etc/passwd` if `userInput` is `/etc/passwd` (absolute path replaces base). `../` sequences escape the directory. CVE-2023-26111 (node-static) leaked `/etc/passwd` and `.env` files through path traversal.

**Detection**:
```bash
rg -n 'res\.sendFile|fs\.(readFile|createReadStream).*req\.' . --type ts --type js
rg -n "express\.static\(\s*['\"]\.['\"]\s*\)" . --type ts --type js
```

---

## Return Generic Error Messages in Production

Return generic error messages to clients. Log detailed errors server-side with structured logging.

```ts
// Correct: global error handler with production/dev split
const errorHandler: ErrorRequestHandler = (err, req, res, _next) => {
    // Log full details server-side
    logger.error('request failed', {
        error: err.message,
        stack: err.stack,
        method: req.method,
        path: req.path,
        requestId: req.headers['x-request-id'],
    });

    // Return generic message to client
    const statusCode = err.statusCode ?? 500;
    res.status(statusCode).json({
        error: statusCode === 500 ? 'internal server error' : err.message,
    });
};
```

**Why this matters**: `res.json({ error: err.message, stack: err.stack })` leaks SQL fragments, internal paths, dependency versions, and configuration details. These help attackers map application internals and craft targeted exploits.

**Detection**:
```bash
rg -n 'err\.stack|e\.stack' . --type ts --type js | rg 'res\.\|json\.\|send'
rg -n 'err\.message' . --type ts --type js | rg 'res\.json\|res\.send'
```

---

## Use Select Clauses When Returning ORM Data

Always specify which columns to return from the database. Never send raw ORM rows to the client.

```ts
// Correct: Prisma select
const user = await prisma.user.findUnique({
    where: { id: userId },
    select: { id: true, displayName: true, avatarUrl: true },
});
return res.json(user);

// Correct: Sequelize attributes
const user = await User.findByPk(userId, {
    attributes: ['id', 'displayName', 'avatarUrl'],
});

// Correct: Drizzle select
const users = await db.select({
    id: usersTable.id,
    displayName: usersTable.displayName,
}).from(usersTable);
```

**Why this matters**: ORMs default to `SELECT *`. A raw row includes password hashes, API tokens, internal flags, and any column added by future migrations. Explicit select clauses act as a data-boundary filter.

**Detection**:
```bash
rg -n 'findUnique\(|findFirst\(|findMany\(' . --type ts | rg -v 'select'
rg -n 'res\.json\(.*await' . --type ts --type js
```
