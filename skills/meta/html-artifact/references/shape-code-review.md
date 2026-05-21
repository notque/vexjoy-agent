# Shape: Code Review

> **Shape**: code-review | **Signal words**: review PR, diff, annotate, code review, explain code
> CSS layout classes: `templates/shapes/code-review.css` (injected by assemble-template.py)

---

## Layout Description

Two-column layout: sticky file navigation sidebar (220px) + scrollable main content area. On mobile, sidebar becomes a horizontal scrollable bar above content.

Main content flows: PR summary header, risk map (severity distribution bars), then file diff blocks in severity order (blocking first, safe last).

---

## Severity System

| Level | Color Var | Badge Class | Use For |
|---|---|---|---|
| Blocking | `--color-danger` | `.severity-badge.blocking` | Must fix before merge |
| Needs Attention | `--color-warning` | `.severity-badge.attention` | Important, non-blocking |
| Worth a Look | `--color-look` (define as `#C4A742`) | `.severity-badge.look` | Minor improvement |
| Safe | `--color-success` | `.severity-badge.safe` | No concerns |

---

## Key CSS Classes (from templates/shapes/code-review.css)

| Class | Purpose |
|---|---|
| `.review-layout` | 2-column grid (sidebar + main) |
| `.file-nav` | Sticky sidebar with file links |
| `.diff-file` | Container per changed file |
| `.diff-header` | File name + severity badge + stats |
| `.diff-line` | Single diff line (`.addition`, `.deletion`, `.context`) |
| `.line-num`, `.line-code` | Line number gutter + code content |
| `.annotation` | Inline review comment between diff lines |
| `.severity-badge` | Colored label (blocking/attention/safe) |
| `.stat-add`, `.stat-del` | Green/red +N/-N stats |

---

## Composition Guide

| Request | Sections |
|---|---|
| "Review this PR" | PR Summary + Risk Map + File Nav + Diff Blocks + Annotations + Keyboard Nav |
| "Annotate this diff" | Diff Blocks + Annotations (no side nav) |
| "Module architecture" | Module Map SVG + Brief annotations per module |
| "What changed in this commit" | Diff Blocks with context-heavy, fewer annotations |

### Section Ordering
1. PR summary (title, author, branch, stats)
2. Risk map (severity distribution)
3. Module map (if architecture visualization needed)
4. File diffs in severity order
5. Keyboard shortcut reference at bottom

---

## Interaction Patterns

- **Expand/collapse diffs:** Button with `aria-expanded` + animated `max-height`
- **Filter by severity:** Buttons filter both sidebar links and diff blocks
- **Keyboard nav:** `j`/`k` between files, `x` to toggle expand (don't fire in text inputs)
- **Jump-to-file:** Sidebar links scroll to and auto-expand the target diff
- **Module map clicks:** SVG module nodes link to their file diff section

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| Line numbers selectable during copy | Use `user-select: none` on `.line-num` |
| Missing +/- prefix on diff lines | Use `::before` pseudo-elements |
| Annotations not connected to lines | Place annotations inline between diff lines, not in a separate section |
| Sidebar not scrollable independently | Use `overflow-y: auto` with `height: 100vh` |
| Keyboard shortcuts fire in text inputs | Check `e.target.tagName !== 'INPUT'` |

---

## Accessibility Checklist

- [ ] Expand/collapse buttons have `aria-expanded` and `aria-controls`
- [ ] Filter buttons use `aria-pressed` state
- [ ] File nav has `aria-label="File navigation"`
- [ ] Annotations have `role="note"` and descriptive `aria-label`
- [ ] Color is never the sole indicator (severity uses text labels + color)
- [ ] Keyboard shortcuts don't fire inside text inputs
- [ ] `prefers-reduced-motion` disables transitions and smooth scrolling
- [ ] Diff line numbers use `user-select: none`
