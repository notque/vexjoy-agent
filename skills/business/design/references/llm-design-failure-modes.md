# LLM Design Failure Modes

Specific ways LLMs fail at design tasks. Each failure mode includes detection signals and concrete defenses. Load this reference for every design mode.

---

## 1. Generic Copy Without Product Context

**What happens**: LLM generates professionally-written copy that could belong to any product. "Get started today!" "Something went wrong." "Welcome aboard!"

**Detection signals**:
- Copy works equally well for a banking app and a gaming platform
- No product-specific terminology
- Tone does not match the product's existing voice
- Generic verbs: "Submit", "Continue", "OK"

**Defense**:
- Ask for the product's existing terminology and voice before writing
- Match button labels to the specific outcome: "Create invoice" not "Submit"
- Reference the user's actual task: "No invoices yet" not "Nothing here yet"
- Check: would a competitor's product use this exact same copy? If yes, it's too generic. Make it specific.

---

## 2. Inaccessible Color Suggestions

**What happens**: LLM recommends color combinations that look appealing but fail WCAG contrast requirements. Common with white text on medium-brightness backgrounds.

**Detection signals**:
- White text on any color lighter than the 600 shade (e.g., blue-500, green-500)
- Gray text lighter than #767676 on white
- Colored text on colored backgrounds without ratio check
- Status colors (green for success, red for error) used as text color on white

**Defense**:
- Calculate contrast ratio for every text/background pairing recommended
- Minimum 4.5:1 for normal text, 3:1 for large text (18pt+), 3:1 for UI components
- Common safe pairings: gray-800 on white (14.72:1), gray-600 on white (7.45:1)
- When suggesting a color palette, include the contrast ratio for each pairing
- Always pair color-based status indicators with icons and text labels

---

## 3. Platform-Blind Critique

**What happens**: LLM applies desktop web conventions to mobile designs, or iOS patterns to Android, or web patterns to native apps.

**Detection signals**:
- Suggesting hover states for mobile interfaces
- Recommending hamburger menu for an iOS app (use tab bar instead)
- Applying web-style dropdowns to native mobile (use bottom sheets)
- Suggesting right-click context menus for touch interfaces
- Recommending text sizes below 16px for mobile body text

**Defense**:
- Identify the target platform before critiquing
- Apply platform-specific conventions:

| Platform | Key Conventions |
|----------|----------------|
| iOS | Tab bar (bottom), navigation bar (top), system sheets, swipe gestures, SF Symbols, 44pt touch targets |
| Android | Bottom navigation, FAB, Material Design components, back button, 48dp touch targets |
| Web Desktop | Sidebar nav, hover states, right-click menus, keyboard shortcuts, cursor states |
| Web Mobile | Bottom navigation, thumb-zone awareness, touch targets 44px+, no hover dependency |

- When platform is ambiguous, ask. "Is this for web or native mobile?"

---

## 4. Missing Edge Cases in Specs

**What happens**: LLM generates clean specs for the happy path — a well-formed form, a list with 5-10 items, a short username. Real products encounter extremes.

**Detection signals**:
- No empty state documented
- No loading state specified
- No error state designed
- No mention of content overflow
- No slow/offline connection handling
- "The user enters their name" but no spec for a 200-character name

**Defense**:
Use this checklist for every spec:

| Category | Edge Cases to Cover |
|----------|-------------------|
| Content length | Empty (0), one, minimum, typical, maximum, overflow |
| Data states | Loading (initial), loading (more), loading (action), success, error (inline), error (page), offline, stale |
| User input | Valid, invalid format, empty required, max length, special characters, paste, autofill |
| List/collection | 0 items, 1 item, typical count, maximum count, filtered to 0 |
| Permissions | Admin, editor, viewer, no access, expired access |
| Timing | Instant response, slow response (2-5s), timeout (30s+), rate-limited |
| i18n | Text 40% longer, RTL layout, locale-specific formatting |

---

## 5. Surface-Level Critique

**What happens**: LLM provides vague feedback that sounds positive but gives no actionable guidance. "The layout is clean." "Good use of whitespace." "The hierarchy is clear."

**Detection signals**:
- Feedback uses subjective adjectives without specifics: "clean", "modern", "intuitive"
- No specific elements named
- No before/after comparison
- No design principle cited as basis for feedback
- Critique could apply to any design

**Defense**:
- Every finding names: the specific element, the specific issue, the specific impact, and a specific recommendation
- Use the format: "[Element] has [issue] which causes [impact]. Improve by [recommendation]."
- "Clean" is not feedback. "The 32px section spacing creates consistent vertical rhythm between content blocks" is feedback.
- Always include what works well and explain WHY it works (which principle it applies correctly)

---

## 6. Fabricated Research Findings

**What happens**: LLM invents plausible user quotes, statistics, persona details, or research findings that sound authoritative but have no source.

**Detection signals**:
- Specific statistics without source: "73% of users prefer..."
- User quotes that sound polished rather than natural
- Persona details too detailed to derive from the input data
- Confident claims about user behavior with no evidence trail
- "Research shows..." without citing which research

**Defense**:
- Every finding traces to specific user-provided data. If no data was provided, state the limitation.
- Use participant type attribution: "3 of 5 enterprise admins mentioned..." — not invented names
- Flag confidence levels: HIGH (multiple sources, behavioral data), MEDIUM (single source, self-reported), LOW (inferred, limited data)
- Mark assumptions explicitly: "Assumption: users complete this flow in a single session. Validate with session data."
- When asked about user behavior with no data, say so. "I don't have behavioral data on this. Here's what the design implies about expected behavior."

---

## 7. Token-Value Confusion

**What happens**: LLM specs use raw values (`#3B82F6`, `16px`, `0.5rem`) instead of design token references (`color-primary`, `spacing-4`, `space-2`).

**Detection signals**:
- Hex codes in the spec where token names should be
- Pixel values without corresponding token names
- Font specifications using raw values instead of type scale tokens
- Inconsistent values that should reference the same token

**Defense**:
- Ask for the design system's token naming convention before writing specs
- Every value in a spec should be a token reference: `color-primary` not `#3B82F6`
- When the token system is unknown, use conventional names and flag them: "Assuming token naming convention. Verify against your design system."
- Flag any raw value with: "Needs token mapping — verify [value] maps to [suggested token name]"
- If a value does not fit any existing token, call it out: "No existing token matches this value. Consider creating `spacing-section-header: 28px` or adjusting to nearest token `spacing-8: 32px`."

---

## 8. Framework Dumping

**What happens**: LLM lists all 10 Nielsen heuristics, all WCAG criteria, or all design principles as a checklist without applying them to the specific design.

**Detection signals**:
- All 10 heuristics listed regardless of relevance
- WCAG criteria listed without checking specific elements
- Design principles stated abstractly: "Contrast is important for hierarchy"
- No specific design elements referenced in the analysis
- Equal depth on all points instead of focusing on actual issues

**Defense**:
- Apply each criterion to the actual design. Skip criteria that do not apply.
- Focus depth on actual findings. A design with great keyboard support and poor contrast deserves a paragraph on contrast and a sentence on keyboard.
- Cite the specific element that passes or fails each criterion
- "WCAG 1.4.3 Contrast: The body text (#6B7280 on #FFFFFF) passes at 4.63:1." — not "Contrast should be at least 4.5:1 for normal text."

---

## 9. Ignoring Design System Constraints

**What happens**: LLM suggests components or patterns that conflict with the product's existing design system, introducing visual inconsistency.

**Detection signals**:
- Recommending a component variant that does not exist in the system
- Suggesting custom styling instead of using existing component props
- Proposing a new pattern when an existing one would work
- Mixing conventions from different design systems (Material + Apple HIG)

**Defense**:
- Ask what design system the product uses before making recommendations
- Recommend existing components and variants first. Propose new ones only when existing components cannot solve the problem.
- When suggesting a new pattern, show its relationship to existing patterns: "This extends the existing Card component with a new `featured` variant"
- Flag when a recommendation might conflict with existing patterns: "Check if your design system already has a notification component before building this custom one"

---

## 10. Treating Mobile as Smaller Desktop

**What happens**: LLM applies desktop interaction patterns to mobile, resulting in designs that ignore how mobile users actually hold and interact with their devices.

**Detection signals**:
- Small touch targets (below 44px)
- Hover-dependent interactions
- Dense information layouts without mobile-specific reorganization
- No consideration of thumb zone (reachability)
- Desktop-style dropdowns instead of mobile-native bottom sheets

**Defense**:
- Thumb zone awareness: primary actions in the bottom half of the screen (easy reach), secondary in the top half
- Touch targets: minimum 44x44 CSS pixels, with 8px spacing between targets
- Interaction patterns: bottom sheets over dropdowns, swipe gestures for common actions, pull-to-refresh
- Content density: reduce visible items, use progressive disclosure, larger type sizes (minimum 16px body)
- Text input: minimize typing, use pickers/selectors where possible, auto-capitalize, appropriate keyboard type (`type="email"`, `type="tel"`)
