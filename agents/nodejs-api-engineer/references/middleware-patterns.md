---
description: Error handling middleware, validation, rate limiting, and security header patterns for Node.js APIs
---

# Express/Next.js Middleware Patterns

> **Scope**: Express 4.x/5.x and Next.js 14+ API route middleware — error handling, Zod validation, rate limiting, CORS, and security headers.
> **Version range**: Express 4.18+, Next.js 14+, `zod` 3.22+, `express-rate-limit` 7.x
> **Generated**: 2026-04-08

---

## Overview

Middleware order in Express is execution-critical. Error-handling middleware (4-argument signature) must come last. Rate limiting before authentication avoids leaking timing data about valid users. Validation middleware that returns early on bad input prevents downstream handlers from processing untrusted data. Missing any of these produces APIs that are either broken or insecure in non-obvious ways.

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| Error middleware `(err, req, res, next)` | Express 4+ | All error handling | 3-arg function — not called by Express for errors |
| `zod.safeParse()` | zod 3+ | Collecting all field errors | `zod.parse()` — throws on first error |
| `express-rate-limit` with Redis store | express-rate-limit 7+ | Multi-process / multi-instance deployments | Single-process (memory store OK) |
| `helmet()` | helmet 7+ | All Express apps | Manually setting individual security headers |
| Next.js `middleware.ts` | Next.js 12+ | Edge-level auth/redirect | Heavy computation — runs on every request |

---

## Correct Patterns

### Centralized Error Handling Middleware

```typescript
import { Request, Response, NextFunction } from 'express';

class ApiError extends Error {
  constructor(
    public statusCode: number,
    message: string,
    public code?: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

// MUST have exactly 4 parameters — Express identifies error middleware by arity
function errorHandler(
  err: Error,
  req: Request,
  res: Response,
  next: NextFunction // Required even if unused
): void {
  if (err instanceof ApiError) {
    res.status(err.statusCode).json({
      error: err.message,
      code: err.code,
      requestId: req.id, // From request ID middleware
    });
    return;
  }

  // Zod validation errors
  if (err.name === 'ZodError') {
    res.status(422).json({
      error: 'Validation failed',
      fields: JSON.parse(err.message),
    });
    return;
  }

  // Unknown errors — sanitize before sending
  console.error('[error]', err);
  res.status(500).json({
    error: 'Internal server error',
    requestId: req.id,
    // DO NOT include err.message or err.stack in production
  });
}

// Register LAST in middleware chain
app.use(errorHandler);
```

**Why**: Express identifies error-handling middleware by the 4-argument signature. A 3-argument function with `err` as the first parameter is treated as a regular middleware and never called for errors.

---

### Zod Request Validation Middleware

```typescript
import { z, ZodSchema } from 'zod';
import { Request, Response, NextFunction } from 'express';

function validateBody<T>(schema: ZodSchema<T>) {
  return (req: Request, res: Response, next: NextFunction): void => {
    const result = schema.safeParse(req.body);
    if (!result.success) {
      // Collect ALL field errors, not just the first
      const errors = result.error.issues.reduce<Record<string, string[]>>(
        (acc, issue) => {
          const field = issue.path.join('.');
          acc[field] = [...(acc[field] ?? []), issue.message];
          return acc;
        },
        {}
      );
      res.status(422).json({ error: 'Validation failed', fields: errors });
      return;
    }
    // Replace req.body with validated + type-safe data
    req.body = result.data;
    next();
  };
}

// Usage:
const CreateUserSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8).max(128),
  name: z.string().min(1).max(100),
});

app.post('/users', validateBody(CreateUserSchema), async (req, res) => {
  // req.body is now typed as z.infer<typeof CreateUserSchema>
  const { email, password, name } = req.body;
  // ...
});
```

**Why**: `safeParse` collects all validation errors in one pass. `parse()` throws on the first error — users get one error at a time, requiring multiple form submissions to fix all issues.

---

### Rate Limiting with Redis Store

```typescript
import rateLimit from 'express-rate-limit';
import RedisStore from 'rate-limit-redis';
import { createClient } from 'redis';

const redis = createClient({ url: process.env.REDIS_URL });

// General API rate limit
const apiLimiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute
  limit: 100,
  standardHeaders: 'draft-7', // Sends RateLimit-* headers
  legacyHeaders: false,
  store: new RedisStore({
    sendCommand: (...args: string[]) => redis.sendCommand(args),
  }),
  keyGenerator: (req) => req.user?.id ?? req.ip ?? 'anonymous',
  message: { error: 'Too many requests', retryAfter: 60 },
});

// Strict limit for auth endpoints
const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  limit: 5,
  store: new RedisStore({
    sendCommand: (...args: string[]) => redis.sendCommand(args),
  }),
  skipSuccessfulRequests: true, // Only count failed auth attempts
});

app.use('/api', apiLimiter);
app.use('/api/auth/login', authLimiter);
app.use('/api/auth/forgot-password', authLimiter);
```

**Why**: In-memory store doesn't work across multiple Node.js processes (PM2 cluster, K8s pods). Process 1 and Process 2 have separate limits — attackers bypass limits by distributing requests across pods. Redis store is shared across all processes.

---

### Security Headers with Helmet

```typescript
import helmet from 'helmet';
import cors from 'cors';

// Helmet sets: X-Frame-Options, X-Content-Type-Options, HSTS, CSP, etc.
app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      scriptSrc: ["'self'", "'nonce-{nonce}'"], // Replace nonce per request
      imgSrc: ["'self'", 'data:', 'https:'],
      connectSrc: ["'self'", process.env.API_URL!],
    },
  },
  hsts: {
    maxAge: 31536000, // 1 year
    includeSubDomains: true,
    preload: true,
  },
}));

// CORS: explicit allowlist, not '*'
app.use(cors({
  origin: (origin, callback) => {
    const allowList = (process.env.CORS_ORIGINS ?? '').split(',');
    if (!origin || allowList.includes(origin)) {
      callback(null, true);
    } else {
      callback(new Error(`CORS blocked: ${origin}`));
    }
  },
  methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  credentials: true,
  maxAge: 86400, // Cache preflight for 24 hours
}));
```

**Why**: `cors({ origin: '*' })` allows any site to make credentialed requests. Explicit allowlist prevents CSRF via cross-origin requests from malicious sites.

---

## Pattern Catalog

### Use 4-Argument Signature for Error Middleware
**Detection**:
```bash
grep -rn 'app\.use.*function.*err' --include="*.ts" --include="*.js" src/
# Find error handlers with only 3 params
grep -rn 'function.*err.*req.*res\b' --include="*.ts" src/
rg '\(err,\s*req,\s*res\)' --type ts src/
```

**Signal**:
```typescript
// 3 args — Express treats this as REGULAR middleware, not error middleware
app.use((err: Error, req: Request, res: Response) => {
  res.status(500).json({ error: err.message });
});
```

**Why this matters**: Express identifies error-handling middleware by arity (argument count). A 3-argument function is a regular middleware. When `next(err)` is called or an error is thrown, Express skips all 3-argument middlewares looking for a 4-argument error handler. Errors propagate unhandled to Express's default error handler, which sends HTML error pages.

**Preferred action**: Always use exactly 4 arguments: `(err, req, res, next)`.

---

### Use an Explicit CORS Origin Allowlist
**Detection**:
```bash
grep -rn "origin.*'\*'\|origin.*\"\\*\"" --include="*.ts" src/
rg "cors\(\{.*origin.*\*" --type ts src/
```

**Signal**:
```typescript
app.use(cors({ origin: '*', credentials: true }));
```

**Why this matters**: `origin: '*'` with `credentials: true` is rejected by browsers (CORS spec prohibits it), but `origin: '*'` without credentials still allows any malicious site to read API responses. Attack: attacker hosts `evil.com`, victim visits it, victim's browser sends cookies to your API, attacker reads the response.

**Preferred action**: Explicit origin allowlist. If truly public (no auth), `origin: '*'` without `credentials` is acceptable.

---

### Validate Input Before Any Side Effects
**Detection**:
```bash
# Find validation that comes after DB calls or side effects
grep -rn 'parse\|safeParse\|validate' --include="*.ts" src/ -B10 | grep -E 'await.*db|await.*createUser|sendEmail'
```

**Signal**:
```typescript
app.post('/users', async (req, res) => {
  // Creates user BEFORE validating input
  const user = await db.users.create({ data: req.body });
  const validated = UserSchema.safeParse(req.body);
  if (!validated.success) {
    res.status(422).json({ error: 'Invalid' });
  }
  res.json(user);
});
```

**Why this matters**: If `req.body.email` is `undefined`, `db.users.create()` may throw a database constraint error that leaks schema details, or worse — insert NULL values. Validation must run before any side effects.

**Preferred action**: Validate first with middleware, then call handlers.

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `Cannot set headers after they are sent` | `next(err)` called after `res.json()` | Check all code paths; ensure single response per request |
| `Error: CORS blocked: https://example.com` | Origin not in allowlist | Add to `CORS_ORIGINS` env var |
| `ValidationError` bypassed in production | Zod errors not caught by error middleware | Register `errorHandler` after all routes |
| Rate limit not applied across pods | Using in-memory store in multi-instance deployment | Switch to Redis store |
| `res.status is not a function` | Middleware called without `next(err)` | Ensure all async handlers have try/catch calling `next(err)` |
| 500 on validation failure | `schema.parse()` throws, unhandled | Use `schema.safeParse()` and handle result |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| Express 5.0 | Async errors automatically forwarded to error middleware | No manual try/catch needed in async handlers |
| `express-rate-limit` 7.0 | `max` option renamed to `limit` | Update config keys |
| `helmet` 7.0 | CSP defaults updated; `frameguard` renamed | Review CSP directives after upgrade |
| `zod` 3.22 | `z.coerce` added for string→number coercion | Useful for query params (`z.coerce.number()`) |
| Next.js 13 | `middleware.ts` moved to project root | Path changed from `pages/_middleware.ts` |

---

## Detection Commands Reference

```bash
# 3-argument error handlers (missing next param)
rg '\(err,\s*req,\s*res\)' --type ts src/

# Wildcard CORS
grep -rn "origin.*'\\*'" --include="*.ts" src/

# In-memory rate limit store (not Redis)
grep -rn 'rateLimit\|rate-limit' --include="*.ts" src/ | grep -v RedisStore | grep -v redis

# Validation after DB operations
grep -rn 'safeParse\|schema\.parse' --include="*.ts" src/ -B5 | grep 'await.*db\|await.*create\|await.*insert'

# Missing error middleware registration
grep -rn 'app\.use.*errorHandler\|app\.use.*error' --include="*.ts" src/
```

---

## See Also

- `auth-patterns.md` — JWT middleware and authentication patterns
- `webhook-patterns.md` — Webhook-specific middleware (raw body, signature verification)
