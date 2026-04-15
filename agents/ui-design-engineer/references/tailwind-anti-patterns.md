# Tailwind CSS Anti-Patterns Reference
<!-- Loaded by ui-design-engineer when task involves Tailwind configuration, class composition, theme customization, or build-time CSS issues -->

> **Scope**: Tailwind-specific pitfalls that cause style breakage, build bloat, or maintenance debt. Does not cover general CSS anti-patterns.
> **Version range**: Tailwind CSS v3.0+
> **Generated**: 2026-04-15 — verify against current Tailwind v3/v4 release notes

Tailwind's utility-first model creates a specific class of bugs that don't appear in traditional CSS: dynamic class construction that gets purged, specificity fights from `@apply`, and responsive prefix ordering that silently does nothing.

---

## Anti-Pattern Catalog

### ❌ Dynamic Class Construction (Purge Trap)

**Detection**:
```bash
# Find string-concatenated Tailwind classes
grep -rn "text-\${" --include="*.tsx" --include="*.ts" --include="*.jsx"
grep -rn "\`bg-\${" --include="*.tsx" --include="*.jsx"
rg 'className=\{.*\$\{.*\}' --type tsx
```

**What it looks like**:
```tsx
// WRONG: Tailwind cannot statically detect these classes at build time
const color = 'red'
<div className={`text-${color}-500`}>Error</div>

// Also wrong: computed key lookups
const variantClasses = { primary: 'blue', danger: 'red' }
<button className={`bg-${variantClasses[variant]}-600`}>Click</button>
```

**Why wrong**: Tailwind's content scanner extracts class names at build time by looking for complete strings. Partial strings like `` `text-${'red'}-500` `` are never seen as `text-red-500` — the final class does not exist in the generated CSS and renders as unstyled.

**Fix**:
```tsx
// CORRECT: Map to complete class strings
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

**Version note**: Tailwind v3 uses `content` config to scan files for class names. v4 uses a Vite plugin with automatic detection, but dynamic construction still fails in both versions.

---

### ❌ Overusing `@apply` for Component Styles

**Detection**:
```bash
grep -rn "@apply" --include="*.css" --include="*.scss"
# Count @apply lines per file — flag files with >8 occurrences
grep -c "@apply" src/**/*.css 2>/dev/null | awk -F: '$2 > 8 {print $1": "$2" @apply lines"}'
```

**What it looks like**:
```css
/* WRONG: Recreating component abstractions in CSS using @apply */
.card {
  @apply bg-white rounded-lg shadow-md p-6 border border-gray-200
         hover:shadow-lg transition-shadow duration-200
         dark:bg-gray-800 dark:border-gray-700;
}
```

**Why wrong**: `@apply` re-couples design to CSS files, defeats the utility model, and loses the ability to conditionally compose classes in JSX. Each `@apply` expands to the full property set rather than sharing utility classes, increasing final CSS bundle size.

**Fix**:
```tsx
// CORRECT: Extract to React component with class strings
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

**Acceptable `@apply` uses**: Base element resets in global CSS, third-party component overrides where JSX access is unavailable.

---

### ❌ Wrong Responsive Prefix Order (Mobile-Last)

**Detection**:
```bash
# Find lines where xl: or lg: appears but sm: or md: does not — likely desktop-first
grep -rn "xl:text-\|xl:w-\|xl:flex" --include="*.tsx" | grep -v "sm:\|md:"
# Lines with larger breakpoint before smaller on the same property
rg 'lg:\S+\s+sm:\S+' --type tsx
```

**What it looks like**:
```tsx
// WRONG: Starting with desktop size, patching down to mobile
<h1 className="text-4xl sm:text-2xl md:text-xl">
  {/* mobile gets text-4xl (the bare class), sm gets text-2xl — opposite of intent */}
</h1>

// Also wrong: bare class after responsive prefix (bare always applies at all widths)
<div className="sm:flex block">
  {/* block applies at ALL widths, sm:flex applies at sm+ — but block wins at sm+ too
      because both have equal specificity and source order determines winner */}
</div>
```

**Why wrong**: Tailwind breakpoints are `min-width` media queries. `sm:` means "at sm and above". A bare class has no breakpoint and applies at every width. When you write `text-4xl sm:text-2xl`, mobile gets `text-4xl` (the bare class) and sm+ gets `text-2xl` — the opposite of mobile-first intent.

**Fix**:
```tsx
// CORRECT: Bare class = mobile default, breakpoints scale up
<h1 className="text-xl sm:text-2xl lg:text-4xl">
  {/* mobile: xl, sm+: 2xl, lg+: 4xl */}
</h1>

// Responsive show/hide
<div className="hidden sm:block">Only visible sm+</div>
<div className="block sm:hidden">Only visible below sm</div>
```

---

### ❌ Hardcoded Arbitrary Values Instead of Theme Extension

**Detection**:
```bash
# Find arbitrary hex colors — should be in Tailwind theme
grep -rn "\[#[0-9a-fA-F]\{3,6\}\]" --include="*.tsx" --include="*.jsx"
# Find arbitrary px values (except standard touch target sizes)
grep -rn "\[[0-9]\+px\]" --include="*.tsx" | grep -v "44px\|48px"
```

**What it looks like**:
```tsx
// WRONG: Brand color repeated as arbitrary value across multiple files
<header className="bg-[#1a237e]">
<button className="bg-[#1a237e] hover:bg-[#283593]">
<div className="border-[#1a237e]">
```

**Why wrong**: Arbitrary values scatter magic numbers across files. A brand color change requires finding every `[#1a237e]` instance. Tailwind's JIT cannot deduplicate arbitrary values with different syntax for the same color.

**Fix**:
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
// CORRECT: Named token, single source of truth
<header className="bg-brand">
<button className="bg-brand hover:bg-brand-hover">
```

**Acceptable arbitrary values**: One-off layout values for unusual compositions, third-party integration styles that appear exactly once.

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
