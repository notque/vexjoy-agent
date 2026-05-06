# Accessibility Review Reference

WCAG 2.1 AA compliance patterns organized by component type. Concrete criteria, ratios, and ARIA patterns that change audit behavior.

---

## WCAG 2.1 AA Quick Reference

### Perceivable

| Criterion | Requirement | Test |
|-----------|-------------|------|
| 1.1.1 Non-text content | All meaningful images have alt text. Decorative images have `alt=""`. | Check every `<img>`, `<svg>`, icon for alt text or aria-label. |
| 1.3.1 Info and relationships | Structure conveyed semantically (headings, lists, tables, landmarks). | Disable CSS — is content still structured? |
| 1.3.4 Orientation | Content works in portrait and landscape. | Rotate device/viewport both ways. |
| 1.4.1 Use of color | Color is not the only means of conveying information. | View in grayscale — is all info still clear? |
| 1.4.3 Contrast (minimum) | Normal text: 4.5:1. Large text (18pt / 14pt bold): 3:1. | Measure every text/background pairing. |
| 1.4.4 Resize text | Content readable at 200% zoom without horizontal scrolling. | Zoom to 200%, check for overflow and overlap. |
| 1.4.11 Non-text contrast | UI components and graphical objects: 3:1 against adjacent colors. | Check button borders, form borders, icons, chart elements. |
| 1.4.12 Text spacing | No loss of content when: line height 1.5x, paragraph spacing 2x, letter spacing 0.12em, word spacing 0.16em. | Apply spacing overrides, check for clipping. |
| 1.4.13 Content on hover/focus | Tooltips/popovers: dismissible, hoverable, persistent until dismissed. | Hover over tooltip, move to its content — does it stay? Press Escape — does it close? |

### Operable

| Criterion | Requirement | Test |
|-----------|-------------|------|
| 2.1.1 Keyboard | All functionality accessible via keyboard. | Tab through entire page. All controls reachable and operable. |
| 2.1.2 No keyboard trap | Focus can always move away from any component. | Tab into every component, verify you can Tab/Escape out. |
| 2.4.1 Bypass blocks | Skip-to-content link available. | First Tab stop should be "Skip to main content." |
| 2.4.3 Focus order | Focus order matches visual layout and logical reading sequence. | Tab through page — does order make sense? |
| 2.4.6 Headings and labels | Headings and labels describe topic or purpose. | Read headings alone — do they tell the page story? |
| 2.4.7 Focus visible | Keyboard focus indicator is visible on all interactive elements. | Tab through — is focus ring visible at every stop? |
| 2.5.5 Target size | Touch targets at least 44x44 CSS pixels. | Measure interactive elements. |

### Understandable

| Criterion | Requirement | Test |
|-----------|-------------|------|
| 3.1.1 Language of page | `lang` attribute on `<html>`. | Check page source. |
| 3.2.1 On focus | No context change on focus alone. | Tab to each element — does anything unexpected happen? |
| 3.2.2 On input | No context change on input without warning. | Changing a dropdown should not navigate away without notice. |
| 3.3.1 Error identification | Errors described in text (not color alone). | Trigger validation — are errors described? |
| 3.3.2 Labels or instructions | Every input has a visible label. | Check that all fields have associated `<label>`. |
| 3.3.3 Error suggestion | Suggestions provided for correctable errors. | Enter wrong format — does the error suggest the right one? |

### Robust

| Criterion | Requirement | Test |
|-----------|-------------|------|
| 4.1.1 Parsing | Valid HTML (no duplicate IDs, proper nesting). | Run HTML validator. |
| 4.1.2 Name, role, value | All UI components expose name, role, and value to assistive tech. | Inspect with screen reader — announced correctly? |

---

## Color Contrast Requirements

### Minimum Ratios

| Element Type | Ratio | WCAG Criterion |
|-------------|-------|---------------|
| Normal text (< 18pt / < 14pt bold) | 4.5:1 | 1.4.3 |
| Large text (>= 18pt / >= 14pt bold) | 3:1 | 1.4.3 |
| UI components (borders, icons, focus rings) | 3:1 | 1.4.11 |
| Decorative/disabled elements | No requirement | N/A |
| Placeholder text | 4.5:1 (treat as informational text) | 1.4.3 |

### Common Pairings That Fail

| Foreground | Background | Ratio | Verdict |
|-----------|------------|-------|---------|
| `#999999` | `#FFFFFF` | 2.85:1 | Fails normal text |
| `#767676` | `#FFFFFF` | 4.54:1 | Passes (barely) |
| `#FFFFFF` | `#3B82F6` (blue-500) | 3.51:1 | Passes large text only |
| `#FFFFFF` | `#10B981` (green-500) | 2.47:1 | Fails all text |
| `#FFFFFF` | `#EF4444` (red-500) | 3.05:1 | Passes large text only |
| `#374151` | `#FFFFFF` | 10.14:1 | Passes all |
| `#6B7280` | `#FFFFFF` | 4.63:1 | Passes (barely) |

**Key insight**: Many popular design system colors fail WCAG when used as text backgrounds with white text. Verify every pairing. The 600-700 range of most palettes is safer for white text.

### Safe Text/Background Combinations

| Use Case | Background | Text | Ratio |
|----------|-----------|------|-------|
| Primary body text | `#FFFFFF` | `#1F2937` (gray-800) | 14.72:1 |
| Secondary body text | `#FFFFFF` | `#4B5563` (gray-600) | 7.45:1 |
| Muted/tertiary text | `#FFFFFF` | `#6B7280` (gray-500) | 4.63:1 |
| Dark surface body text | `#111827` (gray-900) | `#F9FAFB` (gray-50) | 18.06:1 |
| Dark surface secondary | `#111827` | `#D1D5DB` (gray-300) | 10.27:1 |

---

## Keyboard Navigation Patterns

### Focus Management

| Pattern | Keyboard Behavior | Focus Rule |
|---------|-------------------|------------|
| Page load | Focus on skip-to-content link (or first heading) | Do not auto-focus deep into the page |
| Modal open | Focus moves to modal (first focusable element or title) | Trap focus inside modal |
| Modal close | Focus returns to the element that triggered the modal | Preserve context |
| Dropdown open | Focus on first option | Arrow keys navigate options |
| Dropdown close | Focus returns to trigger button | Escape closes |
| Tab panel switch | Focus on selected tab | Arrow keys switch tabs, Tab moves to panel content |
| Toast/notification | Do not steal focus | Announce via live region |
| Delete action | Focus moves to nearest remaining item | Do not leave focus on empty space |

### Standard Key Bindings

| Key | Expected Behavior |
|-----|------------------|
| Tab | Move to next focusable element |
| Shift+Tab | Move to previous focusable element |
| Enter | Activate button, follow link, submit form |
| Space | Toggle checkbox, activate button, scroll page |
| Escape | Close modal, close dropdown, cancel action |
| Arrow keys | Navigate within a component (tabs, menus, radio groups, sliders) |
| Home/End | Move to first/last item in a list |

---

## ARIA Landmark Patterns

### Page Structure

```html
<header role="banner">           → Site header, logo, global nav
<nav role="navigation">          → Primary navigation
<main role="main">               → Primary content (one per page)
<aside role="complementary">     → Sidebar, related content
<footer role="contentinfo">      → Site footer
<section role="region">          → Named content section (requires aria-label)
<form role="form">               → Named form (requires aria-label)
<div role="search">              → Search functionality
```

**Rule**: Every piece of content lives within a landmark. Screen reader users navigate by landmarks the way sighted users scan visually.

### Component ARIA Patterns

| Component | Role | Key Attributes | Announcements |
|-----------|------|---------------|---------------|
| Button | `button` | `aria-pressed` (toggle), `aria-expanded` (menu trigger) | Label + state |
| Link | `link` | `aria-current="page"` (current page in nav) | Label + "link" |
| Dialog/Modal | `dialog` | `aria-modal="true"`, `aria-labelledby` | Title on open |
| Alert | `alert` | (implicit live region) | Content read immediately |
| Status | `status` | (polite live region) | Content read at next pause |
| Tab | `tab` within `tablist` | `aria-selected`, `aria-controls` | Label + "tab" + "selected" |
| Menu | `menu` with `menuitem` | `aria-expanded` on trigger | Item label + position |
| Combobox | `combobox` | `aria-expanded`, `aria-activedescendant`, `aria-autocomplete` | Input + results count |
| Switch | `switch` | `aria-checked` | Label + "switch" + "on/off" |
| Progress | `progressbar` | `aria-valuenow`, `aria-valuemin`, `aria-valuemax`, `aria-label` | Label + percentage |
| Tooltip | `tooltip` | `aria-describedby` on trigger | Content read when trigger focused |
| Accordion | `button` with `aria-expanded` controlling `region` | `aria-expanded="true/false"` | Label + "expanded/collapsed" |

---

## Common WCAG Violations by Component

### Forms

| Violation | Impact | Fix |
|-----------|--------|-----|
| Input without `<label>` | Screen reader cannot identify the field | Associate `<label for="id">` with every input |
| Placeholder as only label | Disappears on input, low contrast | Use visible label above field. Placeholder is supplemental. |
| Error shown by color only | Color-blind users miss errors | Add error icon + text message alongside color change |
| Required field indicator missing | Users guess which fields are required | Use `aria-required="true"` and visible "(required)" text or asterisk with legend |
| Group without fieldset | Related radios/checkboxes lack context | Wrap in `<fieldset>` with `<legend>` |

### Navigation

| Violation | Impact | Fix |
|-----------|--------|-----|
| No skip link | Keyboard users tab through entire nav every page | Add "Skip to main content" as first focusable element |
| Current page not indicated | Screen reader users cannot tell where they are | Add `aria-current="page"` to current nav item |
| Dropdown opens on hover only | Keyboard users cannot access submenu | Open on Enter/Space, navigate with Arrow keys |
| Mobile hamburger menu not labeled | Screen reader says "button" with no context | Add `aria-label="Main menu"` and `aria-expanded` |

### Modals/Dialogs

| Violation | Impact | Fix |
|-----------|--------|-----|
| Focus not trapped | Tab exits modal to background content | Trap focus within modal while open |
| No Escape to close | Keyboard users stuck without clicking X | Add Escape key handler |
| Focus not returned on close | User loses their place in the page | Return focus to the trigger element |
| Background scrollable | Users interact with hidden content | Set `aria-hidden="true"` on background, prevent scroll |
| Missing title | Screen reader announces modal with no context | Use `aria-labelledby` pointing to heading |

### Data Tables

| Violation | Impact | Fix |
|-----------|--------|-----|
| No `<th>` elements | Screen reader cannot associate data with headers | Use `<th scope="col">` for column headers, `<th scope="row">` for row headers |
| Complex table without `headers` | Multi-level headers lose association | Use `id` on `<th>` and `headers` attribute on `<td>` |
| Sortable column not announced | Screen reader users cannot tell sort state | Add `aria-sort="ascending/descending/none"` to `<th>` |
| Missing caption | Table purpose unclear | Add `<caption>` or `aria-label` on `<table>` |

### Media

| Violation | Impact | Fix |
|-----------|--------|-----|
| Auto-playing audio/video | Disorienting, especially for screen reader users | Require user action to play. Provide pause/stop/mute controls. |
| No captions on video | Deaf/hard-of-hearing users excluded | Provide synchronized captions (not auto-generated alone) |
| No alt text on informational images | Screen reader users miss content | Write descriptive alt text: what the image shows and why it matters |
| Decorative image announced | Screen reader noise | Use `alt=""` and `role="presentation"` |

---

## Screen Reader Testing Checklist

| Check | Method |
|-------|--------|
| Page title descriptive | Screen reader announces page title on load |
| Headings create outline | Navigate by heading (H key in NVDA/VoiceOver) — does the outline make sense? |
| Links make sense out of context | List all links — do labels like "Click here" or "Read more" appear? Use descriptive labels instead. |
| Forms announce labels | Focus each field — does the screen reader announce the label? |
| Images described | Navigate images — are informational images described? Are decorative images silent? |
| Dynamic content announced | Trigger a notification/status change — is it announced via live region? |
| Modal focus managed | Open/close modal — does focus behave correctly? |
| Error messages announced | Trigger validation — are errors announced and associated with fields? |

---

## Focus Visible Patterns

| Pattern | CSS Approach | Notes |
|---------|-------------|-------|
| Default browser | `outline: auto` | Varies by browser. Often insufficient contrast. |
| Custom ring | `outline: 2px solid [focus-color]; outline-offset: 2px;` | Use a high-contrast color. 2px offset prevents clipping. |
| Combined | `outline` + `box-shadow` for double ring | Works when single outline might blend with element border |
| Dark mode | Use lighter focus color in dark mode | Ensure 3:1 contrast against the dark surface |

**Rule**: The focus indicator must have at least 3:1 contrast against adjacent colors and be at least 2px in the shortest dimension. This is testable — measure it.
