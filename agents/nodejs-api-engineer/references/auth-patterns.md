---
description: JWT, OAuth, session management, and token refresh implementations with security-correct patterns
---

# Authentication Patterns for Node.js APIs

> **Scope**: JWT-based auth, OAuth 2.0 integration, session management, and password security for Express/Next.js APIs. Does not cover frontend auth flows or mobile OAuth.
> **Version range**: Node.js 18+, `jsonwebtoken` 9.0+, `bcrypt` 5.0+
> **Generated**: 2026-04-08

---

## Overview

Authentication in Node.js APIs fails in two predictable ways: insecure defaults (long-lived tokens, weak secrets, missing expiry) and broken error handling (timing attacks via username enumeration, stack traces in 401 responses). The patterns below cover production-safe JWT issuance, refresh token rotation, and OAuth callback handling.

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| `jwt.sign()` with `expiresIn` | jsonwebtoken 9+ | All access token issuance | Never omit — tokens live forever |
| `jwt.verify()` with `algorithms` | jsonwebtoken 9+ | Token validation | `jwt.decode()` — no signature check |
| `bcrypt.hash()` with cost 12 | bcrypt 5+ | Password storage | `md5`, `sha1`, any fast hash |
| `crypto.timingSafeEqual()` | Node 16+ | Webhook signature comparison | `===` string comparison |
| Refresh token rotation | — | Session persistence beyond 15min | Single long-lived access token |

---

## Correct Patterns

### JWT Issuance with Short Expiry and Refresh

```typescript
import jwt from 'jsonwebtoken';
import { randomUUID } from 'crypto';

const ACCESS_TOKEN_TTL = '15m';
const REFRESH_TOKEN_TTL = '7d';

interface TokenPair {
  accessToken: string;
  refreshToken: string;
  expiresIn: number; // seconds
}

function issueTokenPair(userId: string, roles: string[]): TokenPair {
  const accessToken = jwt.sign(
    { sub: userId, roles },
    process.env.JWT_SECRET!,
    {
      algorithm: 'HS256',
      expiresIn: ACCESS_TOKEN_TTL,
      issuer: 'api.example.com',
      jwtid: randomUUID(), // Unique ID for revocation
    }
  );

  const refreshToken = jwt.sign(
    { sub: userId, type: 'refresh' },
    process.env.REFRESH_SECRET!,
    { algorithm: 'HS256', expiresIn: REFRESH_TOKEN_TTL }
  );

  return { accessToken, refreshToken, expiresIn: 15 * 60 };
}
```

**Why**: 15-minute access tokens limit breach window. Refresh tokens enable seamless UX without long-lived access tokens. `jwtid` enables per-token revocation if needed.

---

### JWT Middleware with Explicit Algorithm Pinning

```typescript
import { Request, Response, NextFunction } from 'express';

export function requireAuth(req: Request, res: Response, next: NextFunction): void {
  const authHeader = req.headers.authorization;
  if (!authHeader?.startsWith('Bearer ')) {
    res.status(401).json({ error: 'Missing authorization header' });
    return;
  }

  const token = authHeader.slice(7);
  try {
    const payload = jwt.verify(token, process.env.JWT_SECRET!, {
      algorithms: ['HS256'], // Explicit — prevents alg:none attack
      issuer: 'api.example.com',
    }) as { sub: string; roles: string[] };

    req.user = { id: payload.sub, roles: payload.roles };
    next();
  } catch (err) {
    if (err instanceof jwt.TokenExpiredError) {
      res.status(401).json({ error: 'Token expired', code: 'TOKEN_EXPIRED' });
    } else {
      res.status(401).json({ error: 'Invalid token' });
      // Do NOT leak err.message — reveals token structure to attackers
    }
  }
}
```

**Why**: `algorithms: ['HS256']` prevents the "algorithm none" attack where attackers forge tokens by setting `alg: "none"`. Without this, `jsonwebtoken` < 9 accepted unsigned tokens.

---

### Webhook Signature Verification (Stripe/GitHub pattern)

```typescript
import { createHmac, timingSafeEqual } from 'crypto';

export function verifyWebhookSignature(
  payload: Buffer,
  signature: string,
  secret: string,
  tolerance = 300 // 5 minutes
): boolean {
  // Stripe format: t=timestamp,v1=signature
  const parts = Object.fromEntries(
    signature.split(',').map((p) => p.split('=') as [string, string])
  );
  const timestamp = parseInt(parts['t'] ?? '0', 10);

  // Reject stale webhooks (replay attack prevention)
  const age = Math.floor(Date.now() / 1000) - timestamp;
  if (age > tolerance) return false;

  const signedPayload = `${timestamp}.${payload.toString('utf-8')}`;
  const expected = createHmac('sha256', secret)
    .update(signedPayload)
    .digest('hex');

  // Timing-safe comparison — prevents timing oracle attacks
  return timingSafeEqual(
    Buffer.from(parts['v1'] ?? '', 'hex'),
    Buffer.from(expected, 'hex')
  );
}
```

**Why**: `timingSafeEqual` takes constant time regardless of where strings differ. Regular `===` returns early on first mismatch, leaking signature bytes via timing measurements (timing oracle attack).

---

## Pattern Catalog

### ❌ Using jwt.decode() Instead of jwt.verify()

**Detection**:
```bash
grep -rn 'jwt\.decode(' --include="*.ts" --include="*.js" src/
rg 'jwt\.decode\(' --type ts src/
```

**What it looks like**:
```typescript
// "decode" sounds like "verify" — it isn't
const payload = jwt.decode(req.headers.authorization?.split(' ')[1] ?? '');
if (payload && payload.sub) {
  req.user = { id: payload.sub };
  next();
}
```

**Why wrong**: `jwt.decode()` does NOT verify the signature. Any attacker can craft a token with any `sub` value by base64-encoding a JSON payload. Authentication is completely bypassed.

**Fix**: Always use `jwt.verify()` with `algorithms` specified.

---

### ❌ Timing-Based Username Enumeration

**Detection**:
```bash
grep -rn 'return.*null\|return.*false' --include="*.ts" src/auth
# Look for early returns before bcrypt.compare
grep -rn 'findUser\|findByEmail' --include="*.ts" src/ -A10 | grep -v 'compare\|bcrypt'
```

**What it looks like**:
```typescript
async function login(email: string, password: string) {
  const user = await db.users.findByEmail(email);
  if (!user) {
    return { error: 'User not found' }; // Responds fast — user doesn't exist
  }
  const valid = await bcrypt.compare(password, user.passwordHash); // Responds slow
  if (!valid) {
    return { error: 'Invalid password' }; // Responds after bcrypt delay
  }
  return { token: issueToken(user.id) };
}
```

**Why wrong**: When user doesn't exist, the response is ~1ms (DB miss). When user exists but password is wrong, response is ~100ms (bcrypt). Attackers enumerate valid email addresses by measuring response time differences.

**Fix**:
```typescript
async function login(email: string, password: string) {
  const user = await db.users.findByEmail(email);

  // Always run bcrypt.compare — constant time regardless of user existence
  const DUMMY_HASH = '$2b$12$invalidhashpaddingtomakeitthelength'; // pre-computed
  const passwordHash = user?.passwordHash ?? DUMMY_HASH;
  const valid = await bcrypt.compare(password, passwordHash);

  if (!user || !valid) {
    return { error: 'Invalid credentials' }; // Same message for both cases
  }
  return { token: issueToken(user.id) };
}
```

**Version note**: `bcrypt` cost factor 12 is the 2024 recommended minimum. Cost 10 (common default) is acceptable but 12 is better for password storage.

---

### ❌ Long-Lived Access Tokens

**Detection**:
```bash
grep -rn 'expiresIn' --include="*.ts" src/
# Flag anything longer than 1 hour
grep -rn "expiresIn.*['\"].*[0-9][dw]\|expiresIn.*3600[0-9]" --include="*.ts" src/
```

**What it looks like**:
```typescript
const token = jwt.sign(
  { sub: userId },
  process.env.JWT_SECRET!,
  { expiresIn: '7d' } // 7-day access token
);
```

**Why wrong**: A 7-day access token means a stolen token gives 7 days of unauthorized access. With no server-side revocation on logout, all active sessions for a user remain valid even after a password change.

**Fix**: `expiresIn: '15m'` for access tokens + `expiresIn: '7d'` for refresh tokens. Implement refresh token rotation and revocation in Redis.

---

### ❌ Storing Refresh Tokens in localStorage

**Detection**: This is a frontend anti-pattern but confirm with client team.
```bash
grep -rn 'localStorage.*refresh\|localStorage.*token' --include="*.ts" --include="*.tsx" src/
```

**Why wrong**: `localStorage` is accessible to any JavaScript running on the page, including XSS-injected scripts. Refresh tokens in localStorage are stolen by any XSS vulnerability.

**Fix**: `httpOnly` cookies for refresh tokens — inaccessible to JavaScript:
```typescript
res.cookie('refreshToken', refreshToken, {
  httpOnly: true,    // Not accessible via document.cookie
  secure: true,      // HTTPS only
  sameSite: 'lax',   // CSRF protection
  maxAge: 7 * 24 * 60 * 60 * 1000, // 7 days in ms
  path: '/api/auth', // Limit scope
});
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `JsonWebTokenError: invalid signature` | Wrong JWT_SECRET in environment | Verify env var matches what signed the token |
| `TokenExpiredError: jwt expired` | Access token past `expiresIn` | Implement refresh token flow; return 401 with `code: 'TOKEN_EXPIRED'` |
| `JsonWebTokenError: jwt malformed` | Not a valid JWT string (missing dots) | Check `Authorization: Bearer <token>` format |
| `JsonWebTokenError: invalid algorithm` | Token signed with different algorithm | Pin `algorithms: ['HS256']` in verify options |
| `bcrypt: invalid password` | Empty or null password passed to `compare()` | Validate password field exists before calling `compare()` |
| `Error: data and hash arguments required` | `bcrypt.compare(undefined, hash)` | Check `password` is defined in request body |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| `jsonwebtoken` 9.0 | Breaking: dropped support for `alg: none` without explicit option | Upgrade fixes algorithm confusion attacks |
| `bcrypt` 5.0 | Native bindings rewritten; `bcryptjs` is pure-JS fallback | Use `bcrypt` for performance; `bcryptjs` for Lambda/edge |
| Node.js 19 | `crypto.timingSafeEqual` accepts strings directly | Previously required Buffer conversion |

---

## Detection Commands Reference

```bash
# jwt.decode() used for auth (no signature check)
grep -rn 'jwt\.decode(' --include="*.ts" src/

# Missing algorithm pinning in jwt.verify()
grep -rn 'jwt\.verify(' --include="*.ts" src/ -A5 | grep -v 'algorithms'

# String comparison for signatures (timing attack)
grep -rn 'signature.*===\|hmac.*===' --include="*.ts" src/

# Long-lived access tokens
grep -rn "expiresIn.*'[0-9][dw]'" --include="*.ts" src/

# Bcrypt cost below 12
grep -rn 'bcrypt\.hash.*[0-9]' --include="*.ts" src/ | grep -E '\b[1-9]\b'
```

---

## See Also

- `webhook-patterns.md` — Idempotency and retry handling for webhooks
- `security-headers.md` — CORS, CSP, and rate limiting patterns
