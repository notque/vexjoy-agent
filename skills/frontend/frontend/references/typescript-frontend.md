# TypeScript Frontend Architecture

Type-safe, maintainable frontend apps with TypeScript, React, Next.js, and related frameworks: components, state, validation, and build configuration.

Scope: TypeScript type system (generics, conditional types, template literals, discriminated unions, narrowing), React architecture (component patterns, hooks, state, React 19), Zod runtime validation with React Hook Form, API clients, state stores (Zustand, Redux Toolkit), error boundaries, async state, and build tuning (tsconfig, incremental builds, bundles, ESLint).

Not for: React Native apps (`react-native.md`); race conditions, async bugs, or production runtime exceptions (TypeScript debugging in the `programming` skill); carts, Stripe, checkout (`nextjs-ecommerce.md`); portfolio and gallery sites (`react-portfolio.md`).

## Priorities

1. Type safety: catch errors at compile time, not runtime.
2. Runtime validation: validate external data with Zod before use.
3. Developer experience: clear types, good error messages, autocomplete.
4. Performance: efficient compilation, optimized re-renders, proper memoization.

Deliver implementation-ready code that follows TypeScript and React idioms. Explain type decisions and suggest improvements to type safety, maintainability, and performance.

## Hard rules (always apply)

- **Strict mode.** Full strict flags plus `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes`.
- **No `any`.** Use `unknown` or a real type. If `any` is unavoidable, add a comment explaining why.
- **Explicit return types** on public functions.
- **Zod validation** for all external data: API responses, user input, localStorage, URL params. Treat it as untrusted until validated.
- **Type-only imports.** Use `import type` for type-only imports.

## Defaults (on unless disabled)

- **React 19 patterns:** ref as prop (no `forwardRef`), Context directly instead of `Context.Provider`, `useActionState` instead of `useFormState`, explicit ref callbacks.
- **Discriminated unions for state:** a `status` field for async and multi-variant state.
- **Interfaces for object shapes** (better errors, easier extension); types for unions and complex transformations.
- **Exhaustive deps:** follow the React hooks `exhaustive-deps` rule strictly.

## Optional (off unless the task needs it)

- **Generated types:** only with GraphQL or OpenAPI specs.
- **Branded types:** only when domain type safety is critical (for example `UserId` as a branded string).
- **Advanced mapped types:** only for reusable project type utilities.
- **Template literal types:** only for type-level string work such as API routes or CSS classes.
- **Capacitor mobile:** only when preparing iOS or Android builds: touch targets, safe areas, Capacitor patterns.

## Common tasks

- Type-safe API clients: Zod validation, error handling, typed requests and responses, interceptors.
- Forms: React Hook Form plus Zod, field-level validation, error display.
- React 19 migration: `forwardRef` to ref prop, `Context.Provider` to Context, `useFormState` to `useActionState`.
- tsconfig tuning: faster compilation, slow type checks, incremental builds.
- Typed stores: Zustand or Redux with discriminated unions and selectors.

## Out of scope

- Backend APIs: Node.js or Go backend work (the `programming` skill).
- Database schema and query tuning: the `data` skill.
- Native iOS or Android code beyond web views: Swift or Kotlin tooling.
- Design-token system architecture: `ui-design.md`.

## Companion skills

| Skill | When |
|-------|------|
| `code-quality` | Cleanup, linting, formatting, quality gates |
| `programming` | Language patterns and tooling (Go, Kotlin, PHP, Swift, TypeScript) |

## Reference loading table

| Signal | Load | Why |
|---|---|---|
| Building or restyling visible UI: layout, spacing, type, color, states (load first) | `skills/shared-patterns/ui-design-judgment.md`, then `ui-design-recipes.md` and `ui-design-examples.md` in the same folder | Design defaults with reasons and the look-then-fix loop |
| type error, any, type assertion, tsc, tsconfig, forwardRef, React 19 migration, hard gates, blockers, death-loop | `typescript-frontend/engineering-rules.md` | Output format, hard gates and exceptions with detection greps, preferred patterns, anti-rationalization, blocker criteria, UNDERSTAND/PLAN/IMPLEMENT/VERIFY phases, death-loop limits, and the non-obvious failure-mode table (inline components, request-scoped state, `React.cache` argument equality, RSC serialization, effect remounts, localStorage throws) |
| ViewTransition, page animation, shared element, navigation animation, view transition | `typescript-frontend/react-view-transitions.md` | Canary `<ViewTransition>` activation rules, layout-vs-page placement, `key` semantics, text-morph and backdrop-filter CSS workarounds, duration budget, troubleshooting |
| security, auth, XSS, CSRF, SSRF, Server Action auth, middleware bypass, image optimizer, or any vulnerability-related code | `typescript-frontend/nextjs-security.md` | CVE-2025-29927 middleware bypass, CVE-2025-55182 Server Action closure params, GHSA-rvpw-p7vw-wj3m image-optimizer SSRF, RSC prop leakage, with detection commands |
| text/headline/label/microcopy animation | `distinctive-frontend-design-refs/roll-text.md` | Zero-npm roll/slot text pattern: standalone demo, extraction guide, knobs |

Output format details: [shared-patterns/output-schemas.md](../../../shared-patterns/output-schemas.md).
