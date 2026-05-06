# Design Critique Reference

Structured methodology for evaluating designs. Concrete frameworks that change model behavior — not "give constructive feedback" generics.

---

## Four-Step Critique Method

Apply in order. Each step builds on the previous.

### Step 1: Describe (What Is Present)

Observe and name without judgment. This forces careful looking before evaluating.

| Observe | Questions |
|---------|-----------|
| Elements | What components, images, text blocks, and controls are present? |
| Layout | How is content organized? Grid, hierarchy, grouping? |
| Visual relationships | What's near what? What aligns? What stands alone? |
| Color usage | What palette? How many colors? Where are they used? |
| Typography | How many type sizes? Weights? What creates the reading order? |
| Spacing | Tight or loose? Consistent or varied? Where does white space live? |

**Output**: Neutral inventory. "The page has a two-column layout with a sidebar navigation on the left and a content area on the right. Three heading levels are visible."

### Step 2: Analyze (How Principles Apply)

Evaluate the design against fundamental principles:

| Principle | What to Check | Strong Signal | Weak Signal |
|-----------|--------------|---------------|-------------|
| **Contrast** | Do important elements stand out? | CTA visually distinct from surrounding elements | Primary and secondary actions look the same |
| **Hierarchy** | Is there a clear reading order? | Eye follows: heading -> key content -> CTA | Multiple elements compete for attention |
| **Alignment** | Are elements on a consistent grid? | Clean vertical and horizontal alignment | Elements placed "close enough" without snapping |
| **Proximity** | Are related items grouped? | Labels near their fields, actions near their context | Related elements scattered across the screen |
| **Repetition** | Are patterns consistent? | Same card style used for all similar content | Each card has slightly different padding/layout |
| **Balance** | Does the layout feel stable? | Visual weight distributed intentionally | One side heavy with content, other empty |

### Step 3: Interpret (What the Design Communicates)

| Dimension | Questions |
|-----------|-----------|
| Emotional tone | Does it feel professional, playful, urgent, calm? Is that appropriate? |
| Brand alignment | Does it look like it belongs to this product/brand? |
| User expectations | Would users recognize this as [type of screen]? Does it match their mental model? |
| Information priority | What does the design say is most important? Is the design right? |
| Trust signals | Does it feel trustworthy? Reliable? Appropriate for the data sensitivity? |

### Step 4: Evaluate (What Works, What to Improve)

Structure every finding as: **Element + Issue + Impact + Recommendation**.

| Element | Weak Feedback | Strong Feedback |
|---------|--------------|----------------|
| CTA button | "The button doesn't stand out" | "The primary CTA ('Start trial') uses the same visual weight as navigation links. Users may miss it. Increase contrast: use a filled button with `color-brand-primary` background." |
| Form layout | "The form is confusing" | "Card number, expiry, and CVV appear in a single column at full width. Group them in a row to match the physical card layout and reduce vertical scrolling." |
| Error state | "Error handling is bad" | "Form validation shows all errors at the top of the form. Users must scroll up to see them, then scroll back down to fix them. Show each error inline below its field." |

---

## Nielsen's 10 Heuristics — Applied

Each heuristic with concrete application to real design patterns. Apply to the specific design; skip heuristics that do not apply.

### 1. Visibility of System Status

The system keeps users informed about what is happening.

| Pattern | Strong | Weak |
|---------|--------|------|
| File upload | Progress bar with percentage and estimated time | Spinner with no indication of progress or duration |
| Form submission | Button shows loading state, then success confirmation | Page refreshes with no feedback |
| Background process | Status indicator: "Syncing 3 of 12 files..." | Nothing visible until complete |
| Search | Results count and load time shown | Results appear with no context |

### 2. Match Between System and Real World

Use language and concepts familiar to users.

| Pattern | Strong | Weak |
|---------|--------|------|
| Terminology | "Shopping cart" (matches mental model) | "Procurement queue" (internal jargon) |
| Organization | Calendar view for scheduling | Timestamp list for scheduling |
| Icons | Trash can for delete | Abstract geometric shape for delete |

### 3. User Control and Freedom

Users make mistakes. Provide exits, undo, and recovery.

| Pattern | Strong | Weak |
|---------|--------|------|
| Destructive action | "Undo" toast for 10 seconds after deletion | Immediate permanent deletion |
| Navigation | Clear back button, breadcrumbs | Deep modal with no escape route |
| Multi-step flow | "Save draft" available at every step | Losing all progress on back navigation |

### 4. Consistency and Standards

Follow platform conventions and internal patterns.

| Check | Questions |
|-------|-----------|
| Platform | Does it follow iOS/Android/Web conventions for this control type? |
| Internal | Does it match other screens in the same product? |
| Industry | Does it match user expectations from similar products? |
| Visual | Same spacing, colors, typography for same element types? |

### 5. Error Prevention

Design to prevent errors before they happen.

| Pattern | Strong | Weak |
|---------|--------|------|
| Input formatting | Auto-format phone number as user types | Reject input after submission for wrong format |
| Destructive action | Require typing project name to confirm deletion | Single "Delete" button with no confirmation |
| Data loss | Auto-save with version history | No save reminder before navigating away |

### 6. Recognition Over Recall

Make options visible. Reduce memory load.

| Pattern | Strong | Weak |
|---------|--------|------|
| Navigation | Visible sidebar with all sections | Remembering keyboard shortcuts for navigation |
| Search | Recent searches and suggestions shown | Empty search box with no hints |
| Forms | Dropdown with options visible | Free-text field requiring exact format |

### 7. Flexibility and Efficiency of Use

Serve both novices and experts.

| Pattern | Strong | Weak |
|---------|--------|------|
| Power users | Keyboard shortcuts + visual UI both available | Keyboard only or mouse only |
| Customization | Configurable dashboard with sensible defaults | Fixed layout for all users |
| Shortcuts | Recent/favorite items accessible | Start from scratch every time |

### 8. Aesthetic and Minimalist Design

Every element earns its space. Visual noise competes with content.

| Check | Questions |
|-------|-----------|
| Content priority | Is the most important content most prominent? |
| Visual noise | Are there decorative elements that add no information? |
| Density | Is there enough white space for comfortable scanning? |
| Distraction | Do secondary elements pull attention from primary tasks? |

### 9. Help Users Recognize, Diagnose, and Recover from Errors

Error messages are plain language, indicate the problem, and suggest a solution.

| Pattern | Strong | Weak |
|---------|--------|------|
| Form error | "Password must be at least 8 characters" shown at the field | "Error" shown at top of page |
| System error | "We couldn't save your changes. Your work is safe — try again in a moment." | "500 Internal Server Error" |
| Auth error | "Wrong password. Reset your password?" with link | "Authentication failed" |

### 10. Help and Documentation

Provide contextual help where users need it.

| Pattern | Strong | Weak |
|---------|--------|------|
| Complex feature | Inline tooltip explaining the option | Separate help page requiring navigation away |
| First use | Contextual walkthrough of key features | 20-step feature tour on first login |
| Edge case | "Learn more" link next to advanced option | No explanation of advanced options |

---

## Cognitive Walkthrough Methodology

Simulate a new user attempting a specific task. For each step:

| Question | What It Reveals |
|----------|----------------|
| Will the user try to achieve the right effect? | Is the goal clear? |
| Will the user see the correct action is available? | Is the affordance visible? |
| Will the user associate the action with the desired effect? | Is the label/icon clear? |
| Will the user see progress after taking the action? | Is feedback provided? |

**Walkthrough output**: Step-by-step table with each action, success/failure prediction, and specific issues found.

---

## Critique Framing by Audience

| Audience | Frame | Focus | Language |
|----------|-------|-------|----------|
| Designer (peer) | Collaborative exploration | Design decisions, alternatives, rationale | "Have you considered..." / "What if..." |
| Designer (junior) | Educational, encouraging | Principles applied, growth areas, what works | "This works because..." / "Try this approach..." |
| Stakeholder | Impact-focused | User impact, business goals, competitive context | "Users will..." / "This supports [goal] by..." |
| Developer | Actionable, specific | Implementation implications, edge cases, specs | "This needs [specific state]" / "Token: [name]" |
| Cross-functional review | Balanced, structured | Findings organized by severity and category | Numbered findings, severity levels, priority order |

---

## Critique Anti-Patterns to Avoid

| Anti-pattern | Do instead |
|-------------|-----------|
| Vague praise: "Looks good" | Specific observation: "The card grid creates a consistent scanning pattern and the hover states clearly indicate interactivity" |
| Vague criticism: "This is confusing" | Specific finding: "The filter controls and sort controls use the same visual style, making it unclear which is which. Differentiate with distinct grouping or labels." |
| Unsolicited redesign: "You should redo the whole layout" | Targeted recommendation: "The sidebar navigation competes with the main content. Consider reducing sidebar width or collapsing it by default." |
| Subjective preference: "I don't like the color" | Principled feedback: "The blue links on the blue-tinted background have a contrast ratio of 2.8:1, below the 4.5:1 WCAG AA requirement." |
| Missing context: Critiquing a prototype for pixel-perfection | Stage-appropriate feedback: "Since this is an early prototype, focusing on the flow: the 3-step checkout reduces friction compared to the current 5-step flow." |
