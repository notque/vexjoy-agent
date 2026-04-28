# Tailwind CSS Patterns Guide
<!-- Loaded by ui-design-engineer when task involves Tailwind configuration, class composition, theme customization, or build-time CSS issues -->

> **Scope**: Tailwind-specific patterns for class composition, responsive design, theme management, and build optimization. Does not cover general CSS patterns.
> **Version range**: Tailwind CSS v3.0+
> **Generated**: 2026-04-15 — verify against current Tailwind v3/v4 release notes

Tailwind's utility-first model creates a specific class of bugs that don't appear in traditional CSS: dynamic class construction that gets purged, specificity fights from `@apply`, and responsive prefix ordering that silently does nothing. The patterns below show the correct approach for each.

---

## Pattern Catalog

### Map Variants to Complete Class Strings

Use object maps or conditional expressions with complete Tailwind class strings. Never interpolate partial class names with template literals — Tailwind's content scanner cannot detect dynamically constructed class names.

```tsx
// Map to complete class strings
const variantClasses = {
  primary: 'bg-blue-600 hover:bg-blue-700 text-white',
  danger:  'bg-red-700  hover:bg-red-800  text-white',
}
<button className={variantClasses[variant]}>Click</button>

// Or use cn() with full class names
<div className={cn(
  isError && 'text-red-500',
  isSuccess && 'text-green-600',
)}>
```

**Why this matters**: Tailwind's content scanner extracts class names at build time by looking for complete strings. Partial strings like `` `text-${'red'}-500` `` are never seen as `text-red-500` — the final class does not exist in the generated CSS and renders as unstyled. This affects both v3 (`content` config) and v4 (Vite plugin).

**Detection**:
```bash
grep -rn "text-\${" --include="*.tsx" --include="*.ts" --include="*.jsx"
grep -rn "\`bg-\${" --include="*.tsx" --include="*.jsx"
```

---

### Extract Component Abstractions in JSX, Not CSS

When reusing a set of utility classes, extract them into a React component that accepts `className` for composition. Reserve `@apply` for base element resets and third-party component overrides where JSX access is unavailable.

```tsx
function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn(
      'bg-white rounded-lg shadow-md p-6 border border-gray-200',
      'hover:shadow-lg transition-shadow duration-200',
      'dark:bg-gray-800 dark:border-gray-700',
      className,
    )}>
      {children}
    </div>
  )
}
```

**Why this matters**: `@apply` re-couples design to CSS files, defeats the utility model, and loses the ability to conditionally compose classes in JSX. Each `@apply` expands to the full property set rather than sharing utility classes, increasing final CSS bundle size.

**Detection**:
```bash
grep -rn "@apply" --include="*.css" --include="*.scss"
grep -c "@apply" src/**/*.css 2>/dev/null | awk -F: '$2 > 8 {print $1": "$2" @apply lines"}'
```

---

### Order Responsive Prefixes Mobile-First

Set the bare class as the mobile default and use breakpoint prefixes to scale up. Tailwind breakpoints are `min-width` media queries: `sm:` means "at sm and above."

```tsx
// Bare class = mobile default, breakpoints scale up
<h1 className="text-xl sm:text-2xl lg:text-4xl">
  {/* mobile: xl, sm+: 2xl, lg+: 4xl */}
</h1>

// Responsive show/hide
<div className="hidden sm:block">Only visible sm+</div>
<div className="block sm:hidden">Only visible below sm</div>
```

**Why this matters**: Writing `text-4xl sm:text-2xl` gives mobile `text-4xl` (the bare class applies at every width) and sm+ gets `text-2xl` — the opposite of mobile-first intent. A bare class has no breakpoint and applies at every width, so it must be the smallest size.

**Detection**:
```bash
# Find lines where xl: or lg: appears but sm: or md: does not
grep -rn "xl:text-\|xl:w-\|xl:flex" --include="*.tsx" | grep -v "sm:\|md:"
# Lines with larger breakpoint before smaller on the same property
rg 'lg:\S+\s+sm:\S+' --type tsx
```

---

### Extend the Theme for Repeated Values

When a color, spacing value, or font appears more than once, add it to `tailwind.config.js` as a named token. Use arbitrary values (`[#1a237e]`) only for one-off layout values that appear exactly once.

```javascript
// tailwind.config.js — extend with named tokens
module.exports = {
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: '#1a237e',
          hover:   '#283593',
        },
      },
    },
  },
}
```
```tsx
// Named token, single source of truth
<header className="bg-brand">
<button className="bg-brand hover:bg-brand-hover">
```

**Why this matters**: Arbitrary values scatter magic numbers across files. A brand color change requires finding every `[#1a237e]` instance. Tailwind's JIT cannot deduplicate arbitrary values with different syntax for the same color. Named tokens provide a single source of truth.

**Detection**:
```bash
# Find arbitrary hex colors that should be theme tokens
grep -rn "\[#[0-9a-fA-F]\{3,6\}\]" --include="*.tsx" --include="*.jsx"
# Find arbitrary px values (except standard touch target sizes)
grep -rn "\[[0-9]\+px\]" --include="*.tsx" | grep -v "44px\|48px"
```

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| Class present in dev, missing in production build | Dynamic class construction purged at build time | Use complete class strings, never interpolate Tailwind class segments |
| Responsive breakpoint class has no effect | Mobile-last ordering — bare class overrides the breakpoint prefix at all widths | Reorder: bare class = mobile default, breakpoints scale up |
| `@apply` rule not found | Class not in Tailwind's generated output (purged or non-existent) | Ensure class is in `safelist` or in a content-scanned file as a complete string |
| Dark mode background stays light | Missing `dark:` variant on colored element | Add `dark:bg-*` and `dark:text-*` counterparts |
| CSS bundle unexpectedly large | `@apply` expanding full property sets per selector | Replace `@apply`-heavy CSS with React component abstractions |

---

## Detection Commands Reference

```bash
# Dynamic class construction (purge trap)
grep -rn "\`[a-z]*-\${" --include="*.tsx" --include="*.jsx"

# @apply overuse
grep -rn "@apply" --include="*.css"

# Responsive ordering issues
rg 'lg:\S+\s+sm:\S+' --type tsx

# Arbitrary color values that should be theme tokens
grep -rn "\[#[0-9a-fA-F]\{3,6\}\]" --include="*.tsx"
```

---

## See Also

- `design-tokens.md` — Tailwind theme configuration and CSS custom properties
- `component-library-interactive.md` — Button/input class composition patterns
