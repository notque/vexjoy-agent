# Visual review

Check the rendered screen, not the code. This checklist applies [UI design judgment](../../../shared-patterns/ui-design-judgment.md) section 10 to shadcn screens; run that section's page check script at each width too. Every item is pass or fail with a location. Default viewport widths are 375, 768, and 1280 px, each in light and dark mode.

## Tools

| Harness has | Do |
|---|---|
| Playwright MCP | `browser_navigate`, `browser_resize`, `browser_take_screenshot`, `browser_snapshot` (accessibility tree), `browser_press_key` (Tab order) |
| chrome-devtools MCP | `navigate_page`, `resize_page`, `take_screenshot`, `take_snapshot`, `emulate` (dark mode, reduced motion), `lighthouse_audit` (accessibility score) |
| neither | Say so. Give the user this checklist and the dev-server URL (bound to `127.0.0.1`). Do not claim visual quality. |

Toggle dark mode by adding the `dark` class to `<html>`, or by emulating `prefers-color-scheme: dark` when the app follows the system.

## Checklist

**Hierarchy**
- [ ] The screen has one `h1`, and it names the task or product.
- [ ] Within 5 seconds of looking at the screenshot, you can name the primary action. It is the only `default`-variant button in its region.
- [ ] Headings, labels, and numbers alone tell the story when the operator only scans.

**Spacing and alignment**
- [ ] Controls in the same row share one height (`layout_tokens.control`).
- [ ] Left edges align on a shared grid. No element is off by a few pixels.
- [ ] Gaps come from the plan's `gap` and `section` tokens, with no one-off values.

**Contrast and color**
- [ ] The plan's `contrast` rows all read `ok: true`. Custom colors you added reach 4.5:1 for text and 3:1 for icons, borders, and focus rings.
- [ ] One accent color. Red appears only for destructive or error states.

**Accessibility**
- [ ] Tab reaches every control in visual order, and focus is always visible.
- [ ] Every icon-only button has an accessible name (check the accessibility tree).
- [ ] Dialogs and sheets trap focus and return it to their trigger on close.
- [ ] Touch targets are at least 44 × 44 px at 375 px width.
- [ ] With reduced motion on, nothing slides or bounces.

**Responsive**
- [ ] No horizontal scroll at 375 px.
- [ ] Tables either scroll inside their own region or switch to a list at 375 px.
- [ ] The primary action is visible without scrolling at 375 px, or sticks to the bottom.

**Dark mode**
- [ ] No white panels or black text left behind. Charts and images stay legible.
- [ ] Borders are still visible on `input` fields.

**States**
- [ ] Loading shows `skeleton` or `spinner`. Empty shows `empty` with a next step. Errors show `alert` or field errors with a recovery action.

## Reporting a finding

Write each finding as: location, fact, width and mode, fix. For example: "Members list, row actions, 375 px light: the kebab button is 32 px tall; raise it to 44 px (`size-11`)."

Feed findings back as follows:
- Wrong component for a job: change that requirement's role or capabilities in `brief.json`, and rerun the planner.
- Wrong tone: change `style_traits`, and rerun.
- Anything else: fix the code.

Stop after three rounds, and list any open findings.
