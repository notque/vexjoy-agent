# Node.js backend APIs

Scope: Node.js server-side APIs: Next.js API routes, Express routers,
middleware, auth (JWT, OAuth, sessions, bcrypt), file uploads (validation,
S3/Cloudinary, Sharp), webhooks (signature verification, idempotency, retry),
email (SendGrid, Resend), payments (Stripe), background jobs (Bull, BullMQ,
node-cron), structured logging, Zod validation, security headers.

Not here: React/Next.js client code (`frontend` skill,
`references/typescript-frontend.md`); schema design, query tuning, migrations
(`data` skill, `references/database.md`); deployment, scaling, monitoring
(`kubernetes` skill); mobile native code.

Priorities, in order: security (validation, authn, authz, headers),
reliability (error handling, idempotency, retries, logging), performance
(efficient queries, caching, async), maintainability (clear errors,
structure, API docs).

## Hard rules (always apply)

- **Validate all input with Zod** before processing: body, params, and query.
  Treat all client data as untrusted.
- **Error-handling middleware**: try/catch with structured `ApiError`
  responses. Catch and format every error consistently.
- **JWT verification on protected routes**, with proper token validation and
  user context.
- **Security headers** (CORS, CSP, and the rest) on every API response.
- **Rate-limit public endpoints**: default 100 req/min per IP, stricter on
  auth endpoints (5 req/min). Use `express-rate-limit` or
  `upstash-ratelimit`.

## Defaults (on unless disabled)

- Structured logging with request IDs, user context, and error details.
- JSDoc on every public endpoint with request/response examples.
- Full stack traces in development only; sanitize in production.
- Explicit Zod schemas for body, params, and query.

## Optional (off unless asked)

- GraphQL schema generation: only when GraphQL is requested instead of REST.
- Microservices patterns (event bus, service mesh): only when distributed
  architecture is the focus.
- WebSockets: only for real-time features (chat, notifications, live updates).
- Migration scripts (Prisma, Drizzle, TypeORM): only when deploying schema
  changes.

## Verification stops

Mandatory, even when confident.

- After writing code: run the test suite and show the output.
- After claiming a fix: confirm it addresses the root cause; re-read the
  original error and confirm it can't recur.
- Before reporting done: run `npx tsc --noEmit` (if TypeScript) and the test
  suite; show the output.
- Before editing a file: read it first.
- Before committing: never commit to main; use a feature branch.

## Output shape

Before implementing, state: requirements, security considerations (auth,
validation, rate limits), external services (APIs, storage, email), and edge
cases to handle. During: show endpoint code, validation schemas, middleware,
test results. After: list what was completed and this checklist:

- [ ] Input validated with Zod
- [ ] Authentication required
- [ ] Rate limiting enabled
- [ ] Security headers configured

Pair with the `review` skill for code review of the result.

## Common errors

| Error | Cause | Fix |
|---|---|---|
| Validation failure | Input doesn't match the Zod schema (missing field, wrong type, bad format) | Return 422 with field errors: `safeParse`, collect all errors, format as `{field: [errors]}` |
| Authentication failure | Missing, invalid, expired, or malformed JWT / Authorization header | Return 401 with a clear message. Verify signature, expiry, structure. Implement a refresh flow for expired tokens |
| Rate limit exceeded | Client over the limit (default 100 req/min) | Return 429 with `Retry-After`. Sliding window or token bucket, keyed by IP or user ID, stored in Redis when distributed |

## Preferred patterns

- **Validate all user input.** Zod schemas, sanitize HTML, parameterized
  queries. Trusting `req.body` enables SQL injection, XSS, and logic errors.
- **Generic errors in production.** Log details server-side and use error
  tracking (Sentry). Sending `error.stack` to clients leaks paths, structure,
  and dependencies.
- **Rate-limit public endpoints.** Unlimited login, signup, and contact
  endpoints enable brute force, DoS, resource exhaustion, and spam.

## Rationalizations to reject

| Rationalization | Why it's wrong | Do this |
|---|---|---|
| "Input validation slows responses" | Validation prevents breaches | Always validate with Zod; cache schemas |
| "Authenticated endpoints don't need rate limits" | Authenticated users can still abuse APIs | Rate-limit all public endpoints |
| "We'll add security headers later" | Easy to forget; they prevent attacks | Configure CORS and CSP from the start |
| "Long JWT expiry is convenient" | Long tokens increase breach impact | 15-minute expiry plus refresh tokens |
| "Detailed errors help users" | Details leak system info | Generic messages in production; log details server-side |

## Hard gate patterns

Before writing API code, check for these. If found: stop, report, fix before
continuing.

| Pattern | Why blocked | Do instead |
|---|---|---|
| `req.body` without validation | Security hole | `const data = RequestSchema.parse(req.body)` |
| Plain-text passwords | Breach | `await bcrypt.hash(password, 10)` |
| Hardcoded secrets | Credential exposure | `process.env.SECRET_KEY` from env |
| SQL string concatenation | SQL injection | Parameterized queries or an ORM |
| Async without error handling | Unhandled rejections crash the server | try/catch or error middleware |

Detection:

```bash
# Unvalidated inputs
grep -r "req.body\|req.query\|req.params" src/ | grep -v "parse\|safeParse"

# Hardcoded secrets
grep -r "password.*=.*['\"]" src/ --include="*.ts" --include="*.js"

# SQL injection risks
grep -r "SELECT.*\${" src/ --include="*.ts"
```

Exception: internal service-to-service calls with shared types may skip
validation (still recommended).

## When to stop and ask

Resolve routine issues from repo evidence and existing authorization; record
assumptions and continue. Ask Jev when genuinely unsure. Rows marked
**(owner)** guard production, destructive, credential, public-exposure, or
persistence actions: get explicit owner confirmation first.

| Situation | Ask |
|---|---|
| Auth strategy unclear **(owner)** | "Use JWT tokens, sessions, or OAuth?" |
| File storage destination unknown | "Store files locally or in cloud (S3, Cloudinary)?" |
| Rate-limit requirements unclear | "What limits for public and auth endpoints?" |
| External service credentials needed **(owner)** | "Need API keys for [service]: where are they?" |
| Schema changes required | Load the `data` skill's `references/database.md` and plan the migration |

Decide explicitly before acting on: auth strategy (owner confirms), external
API keys (owner confirms), rate-limit values, production error-message content.

## Reference loading table

| When | Load |
|---|---|
| JWT auth, OAuth, password security, token refresh | [nodejs-api/auth-patterns.md](nodejs-api/auth-patterns.md) |
| Stripe/GitHub webhooks, signature verification, idempotency, queue offloading | [nodejs-api/webhook-patterns.md](nodejs-api/webhook-patterns.md) |
| Error middleware, Zod validation, rate limiting, CORS, security headers | [nodejs-api/middleware-patterns.md](nodejs-api/middleware-patterns.md) |
| Security, auth, injection, XSS, CSRF, SSRF, any vulnerability-related code | [nodejs-api/nodejs-security.md](nodejs-api/nodejs-security.md) |
