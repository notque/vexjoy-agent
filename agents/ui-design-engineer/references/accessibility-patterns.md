# Accessibility Patterns Reference
<!-- Loaded by ui-design-engineer when task involves WCAG compliance, ARIA, keyboard navigation, screen readers, or focus management -->

Accessibility is a baseline requirement for production UI, not a post-launch concern. WCAG 2.1 AA is the standard for most commercial and government applications.

## WCAG 2.1 AA Color Contrast
**When to use:** Every text/background color combination in the design system.

Requirements:
- Normal text (under 18pt / 14pt bold): ratio >= 4.5:1
- Large text (18pt+ / 14pt+ bold): ratio >= 3:1
- UI components and icons: ratio >= 3:1 against adjacent colors

```tsx
// Validated contrast pairs (use a tool like https://webaim.org/resources/contrastchecker/)

// Primary button: white on blue-600 = 4.54:1 (passes AA)
<button className="bg-blue-600 text-white">Save</button>

// Danger: white on red-500 = 3.95:1 (FAILS AA for normal text)
// Fix: use red-700 (white on red-700 = 5.74:1)
<button className="bg-red-700 text-white">Delete</button>

// Muted text: gray-500 on white = 3.95:1 (FAILS AA)
// Fix: gray-600 on white = 5.74:1 (passes)
<p className="text-gray-600">Secondary information</p>
```

**Tool to use in CI:** `@double-great/remark-lint-no-empty-alt-text` or axe-core for automated contrast testing.

---

## Focus Management
**When to use:** Any time a user action changes the content or context — opening modals, navigating to new views, completing async operations.

### Visible focus indicators

```css
/* Never suppress outlines without replacement */
/* Without replacement: */
:focus { outline: none; }

/* Good: custom ring that works on all backgrounds */
:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: 2px;
  border-radius: 2px;
}
```

Tailwind equivalent:

```tsx
<button className="focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2">
  Submit
</button>
```

### Moving focus after async operations

```tsx
// After a form submission, move focus to the result message
const resultRef = useRef<HTMLParagraphElement>(null)

async function handleSubmit(e: React.FormEvent): Promise<void> {
  e.preventDefault()
  await submitForm()
  resultRef.current?.focus()
}

// The element must be focusable — add tabIndex="-1"
<p ref={resultRef} tabIndex={-1} role="status" className="focus:outline-none">
  Form submitted successfully.
</p>
```

### Opening and closing modals

```tsx
// Save the trigger element before opening
const triggerRef = useRef<HTMLButtonElement>(null)

function openModal(): void {
  setModalOpen(true)
  // Focus moves into modal via useFocusTrap
}

function closeModal(): void {
  setModalOpen(false)
  // Return focus to where it was before the modal opened
  requestAnimationFrame(() => triggerRef.current?.focus())
}

<button ref={triggerRef} onClick={openModal}>Open settings</button>
```

---

## ARIA Labels and Roles
**When to use:** When the visual context provides meaning that the HTML element alone does not convey to screen readers.

```tsx
// Icon-only button — label is mandatory
<button aria-label="Close dialog">
  <svg aria-hidden="true" .../>
</button>

// Button with visible text — no aria-label needed (text IS the label)
<button>Save changes</button>

// Link that describes destination vs action
<a href="/work/2024" aria-label="View 2024 portfolio collection">
  View collection
</a>

// Form group with shared label
<fieldset>
  <legend>Shipping address</legend>
  <label htmlFor="street">Street</label>
  <input id="street" type="text" />
  <label htmlFor="city">City</label>
  <input id="city" type="text" />
</fieldset>

// Status messages that screen readers should announce
<div role="status" aria-live="polite">
  {loading ? 'Loading...' : ''}
  {error ? `Error: ${error}` : ''}
  {success ? 'Saved successfully.' : ''}
</div>

// Alert messages that interrupt immediately
<div role="alert" aria-live="assertive">
  {criticalError}
</div>
```

---

## Keyboard Navigation
**When to use:** All interactive components. Every action achievable by mouse must be achievable by keyboard.

```tsx
// Dropdown menu — roving tabindex pattern
// Only one item in the list is in the tab order at a time

interface MenuItem {
  id: string
  label: string
  action: () => void
}

export function DropdownMenu({ items }: { items: MenuItem[] }) {
  const [focusedIndex, setFocusedIndex] = useState(0)
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([])

  function handleKeyDown(e: React.KeyboardEvent, index: number): void {
    switch (e.key) {
      case 'ArrowDown': {
        e.preventDefault()
        const next = (index + 1) % items.length
        setFocusedIndex(next)
        itemRefs.current[next]?.focus()
        break
      }
      case 'ArrowUp': {
        e.preventDefault()
        const prev = (index - 1 + items.length) % items.length
        setFocusedIndex(prev)
        itemRefs.current[prev]?.focus()
        break
      }
      case 'Home': {
        e.preventDefault()
        setFocusedIndex(0)
        itemRefs.current[0]?.focus()
        break
      }
      case 'End': {
        e.preventDefault()
        const last = items.length - 1
        setFocusedIndex(last)
        itemRefs.current[last]?.focus()
        break
      }
    }
  }

  return (
    <ul role="menu">
      {items.map((item, index) => (
        <li key={item.id} role="none">
          <button
            ref={el => { itemRefs.current[index] = el }}
            role="menuitem"
            tabIndex={index === focusedIndex ? 0 : -1}
            onClick={item.action}
            onKeyDown={e => handleKeyDown(e, index)}
          >
            {item.label}
          </button>
        </li>
      ))}
    </ul>
  )
}
```

---

## Screen Reader Announcements
**When to use:** Loading states, async results, validation errors, and any content that changes without a page navigation.

```tsx
// Live region for status updates
export function LiveRegion({ message, type = 'polite' }: {
  message: string
  type?: 'polite' | 'assertive'
}) {
  return (
    <div
      role="status"
      aria-live={type}
      aria-atomic="true"
      className="sr-only" // visually hidden but readable by screen readers
    >
      {message}
    </div>
  )
}

// Usage
<LiveRegion message={loading ? 'Loading results...' : `${results.length} results found`} />
```

Visually-hidden utility (for screen reader only content):

```css
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
```

---

## Reduced Motion
**When to use:** Any component with animations or transitions. Users with vestibular disorders can experience motion sickness from animated UI.

```tsx
// CSS approach — works for all animations
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

```tsx
// React hook for conditional animation
function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const handler = (e: MediaQueryListEvent): void => setReduced(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  return reduced
}

// Usage in Framer Motion component
const reducedMotion = useReducedMotion()

<motion.div
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: reducedMotion ? 0 : 0.3 }}
>
```

---

## Skip Links
**When to use:** Every page with a navigation header. Skip links let keyboard users jump directly to the main content, bypassing repeated navigation on every page.

```tsx
// Place this as the first element inside <body>
export function SkipLink() {
  return (
    <a
      href="#main-content"
      className={[
        'sr-only',             // hidden by default
        'focus:not-sr-only',   // visible when focused
        'focus:absolute focus:top-4 focus:left-4',
        'focus:z-50 focus:px-4 focus:py-2',
        'focus:bg-white focus:text-blue-700',
        'focus:rounded focus:shadow-lg',
        'focus:outline-none focus:ring-2 focus:ring-blue-600',
      ].join(' ')}
    >
      Skip to main content
    </a>
  )
}

// Target — the main content area
<main id="main-content" tabIndex={-1}>
  {children}
</main>
```

---

## Form Validation Accessibility
**When to use:** Any form with validation. Errors must be programmatically associated with their fields.

```tsx
export function ValidatedInput({
  id,
  label,
  error,
  ...inputProps
}: {
  id: string
  label: string
  error?: string
} & React.InputHTMLAttributes<HTMLInputElement>) {
  const errorId = `${id}-error`

  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-gray-700">
        {label}
      </label>
      <input
        id={id}
        aria-describedby={error ? errorId : undefined}
        aria-invalid={error ? 'true' : undefined}
        className={`mt-1 block w-full rounded border px-3 py-2 ${
          error ? 'border-red-600' : 'border-gray-300'
        } focus:outline-none focus:ring-2 focus:ring-blue-600`}
        {...inputProps}
      />
      {error && (
        <p id={errorId} role="alert" className="mt-1 text-sm text-red-700">
          {error}
        </p>
      )}
    </div>
  )
}
```
