# Interaction State Coverage

<!-- Loaded by ui-design-engineer when task involves interaction states, hover, focus, disabled, loading, active, or pressed -->

Cover every interaction state for every interactive element before shipping. A button with only default and hover states is incomplete — users encounter disabled, loading, focused, and pressed states in normal workflows. Missing states create moments where the interface feels broken or unresponsive.

## The 6-State Matrix

Every interactive element (buttons, links, inputs, toggles, cards-as-interactions, tabs, dropdowns) must implement all 6 states:

| State | Requirements | CSS/HTML Example |
|-------|-------------|------------------|
| Default | Clear affordance, correct position in visual hierarchy | Base styles — `background-color`, `color`, `border`, `cursor: pointer` |
| Hover | Visible change beyond just cursor, communicates interactivity | `background-color` shift, `opacity: 0.9`, `transform: scale(1.02)`, `box-shadow` increase |
| Active/Pressed | Immediate feedback confirming the press registered | `transform: scale(0.98)`, darker `background-color`, reduced `box-shadow` |
| Disabled | Visually muted, interaction blocked, accessible | `opacity: 0.6`, `cursor: not-allowed`, no hover effect, `aria-disabled="true"` |
| Focus | Visible ring for keyboard navigation, WCAG compliant | `:focus-visible` with `outline: 2px solid`, `outline-offset: 2px`, 3:1 contrast ratio |
| Loading | Progress indicator, interaction blocked, accessible | Inline spinner or skeleton, `aria-busy="true"`, disabled interaction |

## State Implementation Patterns

### Default + Hover + Active

```css
.btn-primary {
  background-color: #2563eb;
  color: white;
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.2s, transform 0.15s;
}

.btn-primary:hover {
  background-color: #1d4ed8;
}

.btn-primary:active {
  background-color: #1e40af;
  transform: scale(0.98);
}
```

### Disabled State

Disabled elements must suppress hover effects. Use `aria-disabled="true"` instead of the `disabled` HTML attribute when the element needs to remain focusable for screen readers to announce why it is disabled.

```css
.btn-primary:disabled,
.btn-primary[aria-disabled="true"] {
  opacity: 0.6;
  cursor: not-allowed;
  pointer-events: none;
}
```

```tsx
<button
  aria-disabled={!isValid}
  onClick={isValid ? handleSubmit : undefined}
  className={cn("btn-primary", !isValid && "btn-disabled")}
>
  Submit
</button>
```

### Focus State

Use `:focus-visible` (not `:focus`) so mouse users do not see the focus ring while keyboard users do. The ring must have a 3:1 contrast ratio against the adjacent background.

```css
.btn-primary:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: 2px;
}
```

### Loading State

Replace the button label with a spinner or show a spinner alongside text. Block interaction to prevent double-submission.

```tsx
<button
  disabled={isLoading}
  aria-busy={isLoading}
  className="btn-primary"
>
  {isLoading ? (
    <>
      <Spinner size={16} aria-hidden="true" />
      <span>Saving...</span>
    </>
  ) : (
    "Save"
  )}
</button>
```

## Transition Timing Bounds

All state transitions must fall within these timing ranges:

| Transition Type | Duration | Rationale |
|----------------|----------|-----------|
| Hover enter/exit | 0.15s - 0.3s | Fast enough to feel responsive, slow enough to see |
| Active/Pressed | 0.1s - 0.15s | Near-instant feedback confirms the press |
| Focus ring | Instant or 0.1s | Keyboard users need immediate visibility |
| Modal/drawer open | 0.3s - 0.5s | Complex layout changes need readable motion |
| Dropdown expand | 0.2s - 0.3s | Fast reveal with slight ease-out |
| Loading transition | 0.2s | Smooth swap between label and spinner |

Timing outside these bounds creates specific problems:
- Below 0.1s: motion is imperceptible, wasted rendering work
- Above 0.5s: interface feels sluggish, user wonders if the action registered

```css
/* Correct: transitions within bounds */
.interactive {
  transition: background-color 0.2s ease, transform 0.15s ease;
}
```

## The 5-Second Test

After implementing all states: can a first-time user identify the primary action within 5 seconds? Load the page, start a timer, and see if the primary CTA (call to action) is obvious. If not, the visual hierarchy needs work — the primary action should be the most visually prominent interactive element through size, color weight, and position.

## Element-by-Element Checklist

Walk through every interactive element and check each state. Use this format:

```
Element: [name, e.g., "Submit button"]
  [ ] Default — clear affordance, correct hierarchy position
  [ ] Hover — visible change (not just cursor), within 0.15-0.3s
  [ ] Active — press feedback, within 0.1-0.15s
  [ ] Disabled — opacity 0.6, no hover, aria-disabled, cursor not-allowed
  [ ] Focus — :focus-visible ring, 2px solid, 3:1 contrast
  [ ] Loading — spinner or skeleton, aria-busy, interaction blocked

Element: [name, e.g., "Navigation link"]
  [ ] Default — ...
  [ ] Hover — ...
  ...
```

### Elements to Check

Walk through every one of these element types that appears on the page:

1. **Primary buttons** (submit, save, create) — all 6 states, loading state is critical
2. **Secondary buttons** (cancel, back, reset) — all 6 states, disabled often overlooked
3. **Icon buttons** (close, menu, settings) — hover must be visible despite small size
4. **Links** — default, hover, visited (if applicable), focus
5. **Text inputs** — default, hover, focus (highlight border), disabled, error, filled
6. **Toggles/switches** — default (on/off), hover, disabled, focus
7. **Checkboxes/radio buttons** — default, checked, hover, disabled, focus, indeterminate (checkbox)
8. **Tabs** — default, active/selected, hover, focus, disabled
9. **Dropdown triggers** — default, hover, open, focus, disabled
10. **Cards as interactions** — default, hover (if clickable), active, focus, selected (if selectable)

## Missing State Indicators

Symptoms that states are missing:

- User clicks a button and nothing visually happens for 200ms+ (missing active/loading)
- Tab key produces no visible indicator of current position (missing focus)
- Greyed-out element still responds to hover (disabled state incomplete)
- Button can be clicked twice during async operation (missing loading state)
- Touch device shows no press feedback (missing active state, relies on hover only)

**Detection:** Inspect every interactive element with browser DevTools. Tab through the page to verify focus visibility. Use `:hover`, `:active`, `:focus-visible`, and `[disabled]` pseudo-class toggles in DevTools to verify each state exists and looks intentional.
