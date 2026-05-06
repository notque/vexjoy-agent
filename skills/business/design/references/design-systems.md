# Design Systems Reference

Domain knowledge for design token architecture, component API design, and system governance. Concrete patterns that change model behavior.

---

## Design Token Architecture

### Token Layers

Tokens organize into three layers. Each layer serves a different audience.

| Layer | Purpose | Example | Consumer |
|-------|---------|---------|----------|
| **Global** | Raw values | `blue-500: #3B82F6` | System maintainers only |
| **Semantic** | Meaning-mapped | `color-primary: {blue-500}` | Component authors |
| **Component** | Context-specific | `button-bg-primary: {color-primary}` | Implementation detail |

**Key rule**: Components reference semantic tokens. Semantic tokens reference global tokens. Components do not reference global tokens directly. This indirection enables theming.

### Color Token System

| Category | Tokens | Usage |
|----------|--------|-------|
| **Brand** | `color-brand-primary`, `color-brand-secondary`, `color-brand-accent` | Brand identity, primary CTAs, key UI accents |
| **Semantic** | `color-success`, `color-warning`, `color-error`, `color-info` | Status communication, form validation, alerts |
| **Neutral** | `color-neutral-50` through `color-neutral-900` | Text, backgrounds, borders, dividers |
| **Surface** | `color-surface-primary`, `color-surface-secondary`, `color-surface-elevated` | Background layers, cards, modals |
| **Interactive** | `color-interactive-default`, `color-interactive-hover`, `color-interactive-active`, `color-interactive-disabled` | Buttons, links, form controls |
| **Text** | `color-text-primary`, `color-text-secondary`, `color-text-disabled`, `color-text-inverse` | Typography hierarchy |

**Contrast rule**: Every text/background pairing must meet WCAG 2.1 AA. Document the contrast ratio for each pairing in the token spec.

### Typography Token System

| Token | Purpose | Example Value |
|-------|---------|---------------|
| `font-family-sans` | UI text | Inter, system-ui, sans-serif |
| `font-family-mono` | Code, data | JetBrains Mono, monospace |
| `font-size-xs` | Captions, badges | 12px / 0.75rem |
| `font-size-sm` | Helper text, metadata | 14px / 0.875rem |
| `font-size-md` | Body text | 16px / 1rem |
| `font-size-lg` | Section headings | 18px / 1.125rem |
| `font-size-xl` | Page headings | 24px / 1.5rem |
| `font-size-2xl` | Hero text | 30px / 1.875rem |
| `font-size-3xl` | Display | 36px / 2.25rem |
| `font-weight-regular` | Body text | 400 |
| `font-weight-medium` | Emphasis, labels | 500 |
| `font-weight-semibold` | Headings, buttons | 600 |
| `font-weight-bold` | Strong emphasis | 700 |
| `line-height-tight` | Headings | 1.25 |
| `line-height-normal` | Body text | 1.5 |
| `line-height-relaxed` | Long-form content | 1.75 |

**Type scale**: Use a consistent ratio (1.25 major third or 1.333 perfect fourth). Every size derives from base * ratio^n. This creates visual harmony and prevents arbitrary sizing.

### Spacing Token System

| Token | Value | Usage |
|-------|-------|-------|
| `space-0` | 0 | Reset |
| `space-1` | 4px | Tight grouping (icon + label) |
| `space-2` | 8px | Related elements within a group |
| `space-3` | 12px | Between form fields |
| `space-4` | 16px | Standard component padding |
| `space-5` | 20px | Section content padding |
| `space-6` | 24px | Between related sections |
| `space-8` | 32px | Between distinct sections |
| `space-10` | 40px | Major section separation |
| `space-12` | 48px | Page-level spacing |
| `space-16` | 64px | Layout columns, major gaps |

**Base unit**: 4px. All spacing values are multiples of 4. This creates a consistent rhythm and prevents "just add 3px" drift.

### Elevation Token System

| Token | Shadow | Usage |
|-------|--------|-------|
| `elevation-0` | none | Flat elements, inline content |
| `elevation-1` | `0 1px 2px rgba(0,0,0,0.05)` | Cards, raised surfaces |
| `elevation-2` | `0 4px 6px rgba(0,0,0,0.07)` | Dropdowns, popovers |
| `elevation-3` | `0 10px 15px rgba(0,0,0,0.1)` | Modals, dialogs |
| `elevation-4` | `0 20px 25px rgba(0,0,0,0.15)` | Notifications, toasts |

**Rule**: Higher elevation = closer to user = more important. Elevation communicates layer hierarchy. Two elements at the same elevation should not overlap.

### Motion Token System

| Token | Value | Usage |
|-------|-------|-------|
| `duration-instant` | 100ms | Micro-interactions (hover, focus ring) |
| `duration-fast` | 150ms | Toggles, color changes |
| `duration-normal` | 250ms | Modals, panels, expand/collapse |
| `duration-slow` | 400ms | Page transitions, complex animations |
| `easing-default` | `ease-in-out` | Most transitions |
| `easing-enter` | `ease-out` | Elements appearing (modal enters) |
| `easing-exit` | `ease-in` | Elements leaving (modal exits) |
| `easing-spring` | `cubic-bezier(0.34, 1.56, 0.64, 1)` | Playful, bouncy interactions |

---

## Component API Design Patterns

### Naming Conventions

| Entity | Convention | Examples |
|--------|-----------|----------|
| Components | PascalCase, noun-based | `Button`, `TextField`, `DataTable` |
| Variants | Descriptive adjective or purpose | `primary`, `secondary`, `ghost`, `destructive` |
| Sizes | T-shirt sizing | `sm`, `md`, `lg` (avoid `small`, `medium`, `large` — more characters, same info) |
| States | Present participle or adjective | `disabled`, `loading`, `selected`, `expanded` |
| Slots | Noun describing the content | `icon`, `label`, `description`, `badge` |
| Events | `on` + PascalCase verb | `onClick`, `onChange`, `onDismiss` |
| Booleans | `is` or `has` prefix | `isDisabled`, `hasError`, `isOpen` |

**Consistency rule**: Pick one convention and apply it everywhere. A component that uses `variant` while another uses `type` for the same concept creates confusion.

### Variant Strategies

| Strategy | When to Use | Example |
|----------|-------------|---------|
| **Prop-based** | Few, orthogonal variations | `<Button variant="primary" size="md">` |
| **Compound** | Complex components with sub-parts | `<Select><Select.Option>` |
| **Composition** | Maximum flexibility needed | `<Card><CardHeader><CardBody>` |
| **Polymorphic** | Component renders different elements | `<Button as="a" href="...">` |

### State Management

Every interactive component defines these states:

| State | Visual Treatment | Behavior |
|-------|-----------------|----------|
| Default | Base appearance | Interactive |
| Hover | Subtle highlight (background or border shift) | Shows interactivity |
| Focus | Visible focus ring (2px offset, high contrast) | Keyboard accessible |
| Active/Pressed | Darker/depressed appearance | Confirms activation |
| Disabled | Reduced opacity (0.5), muted colors | Non-interactive, cursor: not-allowed |
| Loading | Spinner or skeleton, text preserved for layout | Non-interactive during load |
| Error | Error color border/outline, error icon | Shows validation failure |
| Selected | Distinct background or check indicator | Shows current selection |

---

## Composition Patterns

### Slot-Based Composition

Components expose named slots for content injection:

```
<Card>
  <Card.Header>       → title area
  <Card.Media>         → image/video area
  <Card.Body>          → main content
  <Card.Actions>       → button area
</Card>
```

**Rule**: Slots define where content goes. The component controls layout. The consumer controls content.

### Render Prop Pattern

For components that need to expose internal state:

```
<Combobox>
  {({ isOpen, selectedItem }) => (
    <Combobox.Input />
    <Combobox.Options />
  )}
</Combobox>
```

### Provider Pattern

For cross-cutting concerns (theme, locale, feature flags):

```
<ThemeProvider theme={darkTheme}>
  <App />    → all descendants access theme tokens
</ThemeProvider>
```

---

## Theme Architecture

| Concern | Implementation | Example |
|---------|---------------|---------|
| Light/dark mode | Swap semantic token values | `color-surface-primary: white` (light) / `#1a1a1a` (dark) |
| Brand theming | Override brand tokens | `color-brand-primary: {partner-blue}` |
| Density | Adjust spacing and sizing tokens | `space-4: 12px` (compact) / `16px` (default) / `20px` (comfortable) |
| Color scheme | Semantic tokens map to different global palettes | `color-primary: {indigo-600}` (default) / `{teal-600}` (alt) |

**Theme structure**: Themes override semantic tokens only. Global tokens remain stable. Components do not need to know which theme is active.

---

## Documentation Standards

Every component's documentation includes:

| Section | Contents |
|---------|----------|
| Description | What it is, when to use it, when to use something else |
| Props table | Name, type, default, description for every prop |
| Variants gallery | Visual example of every variant |
| States reference | Visual example of every state |
| Accessibility | ARIA role, keyboard behavior, screen reader announcements |
| Usage guidelines | Do's (with rationale) and alternatives (with context) |
| Code examples | Minimum viable, common patterns, edge cases |
| Related components | What's similar and when to pick which |

**Do/Instead pattern for documentation**:

| Do | Instead of |
|------|-----------|
| Use `Button variant="destructive"` for delete actions | Using `variant="primary"` with a red color override |
| Compose `Card` with `Card.Header` for titled content | Passing `title` as a string prop (limits formatting) |
| Use `TextField` with `type="email"` for email inputs | Building a custom input with regex validation |
