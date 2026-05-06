# Design Handoff Reference

Spec documentation patterns for developer handoff. Every section here represents a category developers need to build from a design without guessing.

---

## Handoff Artifact Checklist

Use this checklist to verify completeness before delivering a spec.

| Category | Artifact | Status |
|----------|----------|--------|
| **Layout** | Grid system documented | |
| | Breakpoints defined | |
| | Responsive behavior per breakpoint | |
| | Content area max-width | |
| **Tokens** | Color tokens mapped to usage | |
| | Typography tokens mapped to elements | |
| | Spacing tokens mapped to gaps/padding | |
| | Elevation tokens mapped to surfaces | |
| | Motion tokens mapped to transitions | |
| **Components** | Component name and variant for each element | |
| | Props/configuration for each instance | |
| | Custom overrides documented | |
| **States** | Default state for all interactive elements | |
| | Hover state | |
| | Focus state (keyboard) | |
| | Active/pressed state | |
| | Disabled state | |
| | Loading state | |
| | Error state | |
| | Selected state (where applicable) | |
| | Empty state | |
| **Interaction** | Click/tap behavior | |
| | Hover behavior (desktop) | |
| | Transitions and animations | |
| | Gesture support (mobile) | |
| | Drag behavior (if applicable) | |
| **Content** | Character limits per field | |
| | Truncation rules (ellipsis, line clamp, fade) | |
| | Empty state content and layout | |
| | Loading state treatment (skeleton, spinner, placeholder) | |
| | Error state content and layout | |
| **Edge Cases** | Minimum content (single item, short text) | |
| | Maximum content (overflow, long text, many items) | |
| | International text (30-40% expansion) | |
| | Slow/offline connection behavior | |
| | Missing/null data handling | |
| | Permission variations (what changes by role) | |
| **Accessibility** | Focus order documented | |
| | ARIA labels and roles specified | |
| | Keyboard interactions defined | |
| | Screen reader announcements noted | |
| | Color contrast verified for all pairings | |

---

## Spec Documentation Patterns

### Layout Specification

| Property | What to Specify | Example |
|----------|----------------|---------|
| Grid | Column count, gutter width, margins | 12-col grid, 24px gutter, 32px margins |
| Max width | Content area maximum | max-width: 1200px, centered |
| Sidebar | Width (fixed or percentage), collapse behavior | 280px fixed, collapses to icon-only at <1024px |
| Stacking order | z-index layers for overlapping elements | nav: 100, dropdown: 200, modal: 300, toast: 400 |
| Overflow | Scroll behavior per container | Content area scrolls independently, sidebar fixed |

### Responsive Behavior Specification

| Breakpoint | Name | Layout Changes |
|-----------|------|---------------|
| >= 1280px | Desktop Large | Full layout, sidebar expanded |
| 1024-1279px | Desktop | Full layout, sidebar collapsed |
| 768-1023px | Tablet | Single column, bottom navigation |
| < 768px | Mobile | Stacked layout, hamburger menu, full-width cards |

For each breakpoint, document:
- What elements reflow, hide, or change behavior
- Touch target size adjustments (44px minimum on touch devices)
- Typography scale changes (if any)
- Spacing adjustments (tighter on mobile)
- Navigation pattern changes

### Token-to-Value Mapping

| Token | Value | Where Used |
|-------|-------|-----------|
| `color-primary` | `#3B82F6` | CTA buttons, active tab, links |
| `color-primary-hover` | `#2563EB` | CTA hover state |
| `color-surface-primary` | `#FFFFFF` | Main background |
| `color-surface-secondary` | `#F9FAFB` | Card backgrounds, alternating rows |
| `color-border-default` | `#E5E7EB` | Card borders, dividers |
| `color-text-primary` | `#111827` | Headings, body text |
| `color-text-secondary` | `#6B7280` | Metadata, helper text |
| `font-heading-lg` | `24px/1.25 Inter 600` | Page titles |
| `font-body` | `16px/1.5 Inter 400` | Body text |
| `font-caption` | `12px/1.5 Inter 400` | Timestamps, badges |
| `spacing-section` | `32px` | Between major sections |
| `spacing-card-padding` | `16px` | Inside cards |
| `radius-card` | `8px` | Card corners |
| `radius-button` | `6px` | Button corners |

**Rule**: Every visual value in the spec references a token. If a value has no token, flag it as "needs token" — this prevents design system drift.

---

## Interaction Documentation

### State Transitions

Document each interactive element as a state machine:

| Element | Trigger | From State | To State | Transition | Notes |
|---------|---------|-----------|----------|-----------|-------|
| CTA Button | Mouse enter | Default | Hover | `background-color 150ms ease` | Darken 10% |
| CTA Button | Mouse down | Hover | Active | `transform 100ms ease` | Scale to 0.98 |
| CTA Button | Click | Active | Loading | `opacity 150ms ease` | Show spinner, disable |
| CTA Button | API success | Loading | Default | Instant | Show success toast |
| CTA Button | API error | Loading | Default | Instant | Show error message |
| Sidebar | Toggle click | Expanded | Collapsed | `width 250ms ease-in-out` | Icons remain visible |
| Modal | Trigger click | Closed | Open | `opacity 250ms ease-out` + backdrop | Focus first element |
| Modal | Escape/backdrop | Open | Closed | `opacity 200ms ease-in` | Return focus to trigger |
| Accordion | Header click | Collapsed | Expanded | `max-height 250ms ease-out` | Scroll into view if needed |

### Gesture Documentation (Mobile)

| Gesture | Element | Action | Threshold | Feedback |
|---------|---------|--------|-----------|----------|
| Swipe left | List item | Reveal delete action | 80px | Red background slides in |
| Swipe right | List item | Reveal archive action | 80px | Green background slides in |
| Pull down | List view | Refresh content | 60px + release | Spinner at top |
| Long press | Card | Enter selection mode | 500ms | Haptic + visual selection indicator |
| Pinch | Image | Zoom in/out | Two fingers | 1x to 3x range, spring back at limits |

---

## Edge Case Documentation

### Content Extremes

| Scenario | How to Handle | Example |
|----------|---------------|---------|
| Empty text field | Show placeholder, not broken layout | "No description provided" in muted text |
| Single character name | Layout holds with minimal content | "A" in avatar, card width unchanged |
| 200-character name | Truncate with ellipsis | "Alexandra Constantino..." at max-width |
| 0 items in list | Show empty state with CTA | Illustration + "No items yet" + [Create first item] |
| 1 item in list | Layout works with single item | Same card layout, no "showing 1 of 1" |
| 10,000 items | Virtualized list or pagination | Show first 50, load more on scroll |
| Mixed content lengths | Consistent card height or flexible grid | Cards align to grid regardless of content |

### Data States

| State | Visual Treatment | Content |
|-------|-----------------|---------|
| Loading (initial) | Skeleton placeholders matching content shape | No text, pulsing gray rectangles |
| Loading (more) | Spinner at bottom of list | Existing content visible |
| Loading (action) | Button spinner, disabled state | "Saving..." text optional |
| Error (page) | Full-page error with retry | "Something went wrong. [Try again]" |
| Error (inline) | Inline error below the failing element | Specific error message + fix suggestion |
| Error (toast) | Toast notification | Brief error + action if applicable |
| Offline | Banner at top of page | "You're offline. Changes will sync when you reconnect." |
| Stale data | Subtle indicator | "Last updated 5 min ago. [Refresh]" |

### Internationalization

| Factor | Spec Requirement |
|--------|-----------------|
| Text expansion | All text containers handle 40% longer strings |
| Number formatting | Use locale-aware formatting (`1,234.56` vs `1.234,56`) |
| Date formatting | Use locale-aware dates (use date formatting libraries instead of hardcoded month names) |
| RTL support | Layout mirrors for RTL locales (flex-direction, text-align, icon placement) |
| Currency | Symbol position varies by locale (`$100` vs `100 $`) |
| Pluralization | Support plural rules beyond singular/plural (some languages have 6 forms) |

---

## Developer Q&A Template

Include with every handoff spec. Pre-answer the questions developers always ask.

| Question | Answer |
|----------|--------|
| What component library/framework? | [React / Vue / Angular / SwiftUI / etc.] |
| Which design tokens file? | [Path or URL to tokens] |
| Where do I find the icons? | [Icon library + specific icon names used] |
| What happens when [element] overflows? | [Truncation rule, scroll behavior, or wrap behavior] |
| What are the loading states? | [Per-element loading treatment] |
| What happens on error? | [Error display strategy per context] |
| What animations are needed? | [Token references, durations, easings] |
| Is there a mobile-specific behavior? | [Per-breakpoint differences] |
| What's the focus order? | [Tab order specification] |
| What ARIA attributes are needed? | [Per-component ARIA spec] |
| Where does the data come from? | [API endpoint or data source for each dynamic element] |
| What are the permission levels? | [What changes based on user role] |
| What are the feature flags? | [Any conditional rendering based on flags] |

---

## Handoff Quality Checks

Before delivering, verify:

| Check | Method |
|-------|--------|
| Every interactive element has all states | Cross-reference against state checklist |
| Token references used throughout | Search for raw hex/px values — flag any found |
| Responsive behavior explicit | Each breakpoint has documented changes |
| Edge cases documented | Empty, loading, error, overflow, missing data all addressed |
| Accessibility requirements stated | Focus order, ARIA, keyboard, screen reader all specified |
| Developer questions pre-answered | Q&A template filled out |
| Content specs complete | Character limits, truncation rules, placeholder text defined |
| Animation specs include token references | Duration and easing use token names |
