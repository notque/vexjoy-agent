# Next.js E-commerce

Production online stores on Next.js: shopping carts, Stripe payments, product catalogs, order management, checkout flows, and admin dashboards, with secure payment handling and type-safe data.

Not for: general React or Next.js architecture with no commerce concern (`typescript-frontend.md`); portfolio and gallery sites (`react-portfolio.md`); visual design systems and layout (`ui-design.md`).

Full expertise, default and optional behaviors, scope, and output format: `nextjs-ecommerce/expertise.md`. Load it when scoping an e-commerce feature.

## Hard rules (always apply)

- **Read before editing.** Never edit a file you have not read in this session.
- **Run build and tests before reporting done.** Run `npm run build` and `npm test` and show the actual output. Do not summarize as "build succeeds" or "tests pass."
- **Feature branch, never main.** If on main, create a branch before committing.
- **Verify dependencies before importing.** Check `package.json` for the Stripe SDK, Prisma, NextAuth, Zod, and others first.
- **Server Components by default.** Use client components only for interactivity (cart updates, form validation).
- **Type-safe checkout.** Validate all payment data with Zod before any Stripe API call.
- **Secure payments.** Use Stripe payment tokens only; keep card data out of your storage. Enforce HTTPS on checkout routes.
- **Inventory validation.** Check stock before order confirmation to prevent overselling.
- **Webhook idempotency.** Handle duplicate webhook events with idempotency keys.

For type-safe component architecture, state, and build config, also load `typescript-frontend.md`. For test work, use the `testing` skill.

## Reference loading table

| Signal | Load | Why |
|---|---|---|
| Storefront, product page, cart, checkout, or admin UI layout and styling (load first) | `skills/shared-patterns/ui-design-judgment.md`, then `ui-design-recipes.md` and `ui-design-examples.md` in the same folder | Design defaults with reasons and the look-then-fix loop |
| Scoping an e-commerce feature: expertise, default/optional behaviors, capabilities, output format | `nextjs-ecommerce/expertise.md` | Priorities, defaults, scope limits, ANALYZE/DESIGN/IMPLEMENT/VALIDATE schema |
| Cart/Stripe implementation snippets, error catalog summary, failure modes, blockers | `nextjs-ecommerce/patterns-and-errors.md` | Short cart and Stripe snippets, top errors, anti-rationalization, blockers |
| Shopping cart full implementation | `nextjs-ecommerce/shopping-cart-patterns.md` | Cart state, persistence, quantity updates, abandoned cart |
| Stripe Payment Intents and webhooks full implementation | `nextjs-ecommerce/stripe-integration.md` | Payment Intents, webhook signature, checkout |
| Common e-commerce error catalog | `nextjs-ecommerce/error-catalog.md` | Payment failures, webhook errors, inventory conflicts |
| Reviewing e-commerce code: full failure mode catalog (What/Why/Instead) | `nextjs-ecommerce/preferred-patterns.md` | Security, correctness, reliability failure modes |
| Admin dashboard (product/order management interfaces) | `nextjs-ecommerce/admin-dashboard.md` | Product CRUD, orders, inventory, analytics, role-based access |

Shared patterns: [verification-checklist.md](../../../shared-patterns/verification-checklist.md) (pre-completion checks), [forbidden-patterns-template.md](../../../shared-patterns/forbidden-patterns-template.md) (security failure modes).
