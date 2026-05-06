# UX Copy Reference

Domain knowledge for writing interface copy by component type. Every pattern here changes model behavior — generic writing advice lives elsewhere.

---

## Core Principles

1. **Clear** — Say exactly what you mean. Eliminate ambiguity before brevity.
2. **Concise** — Use the fewest words that convey full meaning. Cut, then check if meaning survived.
3. **Consistent** — Same terms for the same things everywhere. Build a terminology table per product.
4. **Useful** — Every word helps the user accomplish their goal. Decorative text earns its pixels or gets cut.
5. **Human** — Write like a helpful person. Match emotional register to user state.

---

## Copy Patterns by Component Type

### Buttons and CTAs

| Pattern | Example | Why It Works |
|---------|---------|-------------|
| Start with a verb | "Save changes", "Download report" | Action-oriented, sets expectation |
| Match label to outcome | "Create account" over "Submit" | User knows what happens next |
| Specific over generic | "Add to cart" over "Continue" | Removes ambiguity |
| Primary = one clear CTA per screen | "Start free trial" (primary), "Learn more" (secondary) | Hierarchy guides attention |

**Character guidance**: Button text 1-4 words. Mobile: 1-3 words. If a button needs explanation, add helper text below.

**Pairs that work**:

| Action | Confirmation | Cancel |
|--------|-------------|--------|
| Delete | "Delete project" | "Keep project" |
| Discard | "Discard changes" | "Keep editing" |
| Send | "Send message" | "Back to draft" |
| Remove | "Remove member" | "Cancel" |
| Publish | "Publish now" | "Save as draft" |

Use the specific action for both confirm and cancel. "OK / Cancel" forces the user to re-read the dialog.

### Error Messages

**Structure**: What happened + Why it happened + How to fix it.

| Context | Example | Anti-pattern |
|---------|---------|-------------|
| Form validation | "Email address needs an @ symbol" | "Invalid email" |
| Payment failure | "Payment declined. Your bank declined this charge. Try a different card or contact your bank." | "Transaction failed" |
| Permission | "You need editor access to change this. Ask the project owner to update your role." | "Permission denied" |
| Rate limit | "Too many requests. Wait 30 seconds, then try again." | "Error 429" |
| Network | "Can't reach the server. Check your connection and try again." | "Network error" |
| File upload | "This file is 25MB. Upload files under 10MB, or compress this one first." | "File too large" |

**Tone calibration**: Error messages meet users at their most frustrated. Be helpful and direct. Skip apologies ("Oops!") unless the error is genuinely the product's fault. When it is, acknowledge briefly: "Something went wrong on our end. We're looking into it."

**Technical errors**: Translate codes for users. Show the technical detail in a collapsible section for power users or support context. "Something went wrong (Error 500)" with expandable details.

### Empty States

**Structure**: What this area is + Why it's empty + Clear next action.

| Context | Example |
|---------|---------|
| First use | "No projects yet. Create your first project to start collaborating with your team." [Create project] |
| Search no results | "No results for 'widget'. Try different keywords or check your filters." |
| Filtered empty | "No items match these filters. Clear filters to see all items." [Clear filters] |
| Deleted content | "This project was deleted. You can restore it from the trash within 30 days." [Go to trash] |
| Permissions | "You don't have access to any projects yet. Ask your team admin to add you." |

**Key rule**: Empty states are onboarding opportunities. Show the user what's possible, not just what's missing. Use illustration or example content when appropriate.

### Confirmation Dialogs

| Element | Pattern | Example |
|---------|---------|---------|
| Title | State the action clearly | "Delete 3 files?" |
| Body | Describe consequences | "These files will be permanently removed. This action can't be undone." |
| Confirm button | Label with the action | "Delete files" |
| Cancel button | Label with the alternative | "Keep files" |

**Destructive actions**: Use the destructive action as the verb ("Delete", "Remove", "Revoke"). Add a consequence statement. Require explicit confirmation for irreversible actions (type the name, check a box).

**Non-destructive confirmations**: For reversible actions, keep it lightweight. "Move to archive? You can restore anytime." [Archive] [Cancel]

### Tooltips

| Guideline | Example |
|-----------|---------|
| Concise, specific help | "Keyboard shortcut: Cmd+K" |
| Explain hidden functionality | "Drag to reorder items" |
| Provide context for icons | "Share with team" |
| Add detail to truncated content | Full text on hover |

**Character limit**: 150 characters max. If you need more, use an inline help section or link to docs. Tooltips that require reading are tooltips that fail.

Tooltips explain what isn't obvious. If the UI element is self-explanatory, skip the tooltip.

### Notifications

| Type | Tone | Duration | Example |
|------|------|----------|---------|
| Success | Confirmatory, brief | 3-5 seconds, auto-dismiss | "Changes saved" |
| Info | Neutral, helpful | 5-8 seconds or persistent | "New version available. Refresh to update." |
| Warning | Clear, actionable | Persistent until addressed | "Your trial ends in 3 days. Upgrade to keep your data." |
| Error | Empathetic, directive | Persistent until resolved | "Upload failed. Check your connection and try again." |

**Notification copy rules**:
- Lead with the outcome, not the process. "File uploaded" over "Upload complete."
- Include an action when relevant. "Comment added. [View comment]"
- Respect attention. Only notify for things the user needs to know.

### Onboarding

| Step | Pattern | Example |
|------|---------|---------|
| Welcome | Set expectations, not features | "Set up your workspace in 3 steps" |
| Progress | Show where they are | "Step 2 of 3: Invite your team" |
| Value moment | Connect setup to benefit | "Add your first project to start tracking progress" |
| Completion | Celebrate, direct to core flow | "You're all set. Here's your dashboard." |

**Progressive disclosure**: Introduce one concept at a time. Let the user succeed at something simple before introducing complexity. Setup wizards with 3-5 steps outperform feature tours.

---

## Voice and Tone Framework

Voice is constant (who you are). Tone adapts to context (how you say it).

### Tone by User State

| User State | Emotional Register | Tone Approach | Example |
|-----------|-------------------|---------------|---------|
| Accomplishing a goal | Focused, confident | Concise, get out of the way | "Saved" |
| Learning | Curious, uncertain | Supportive, educational | "Drag items to reorder. Changes save automatically." |
| Encountering an error | Frustrated, anxious | Empathetic, direct, solution-first | "Payment failed. Try a different card." |
| Making a decision | Thoughtful, weighing options | Informative, neutral | "Free plan: 3 projects. Pro plan: unlimited projects." |
| Waiting | Impatient, uncertain | Reassuring, set expectations | "Processing your export. This usually takes 1-2 minutes." |
| Succeeding | Satisfied, relieved | Celebratory but proportional | "Project published!" (not "Woohoo! Amazing job!") |

### Content Hierarchy

1. **Title/heading**: What is this? (noun or verb phrase)
2. **Primary copy**: What should the user do? (action-oriented)
3. **Supporting copy**: Why? Additional context. (explanatory)
4. **Helper text**: How? Technical details. (instructional)

Scan the hierarchy: users read headings and bold text first, body text second, helper text only when stuck.

---

## Character Limits by Context

| Element | Recommended Max | Hard Max | Notes |
|---------|----------------|----------|-------|
| Button text | 20 chars | 30 chars | 1-4 words, verb-first |
| Page title | 40 chars | 60 chars | Front-load key words |
| Tooltip | 80 chars | 150 chars | One concept only |
| Error message | 120 chars | 200 chars | What + why + fix |
| Notification | 80 chars | 120 chars | Outcome + optional action |
| Empty state heading | 40 chars | 60 chars | What's missing |
| Empty state body | 100 chars | 150 chars | Why empty + next step |
| Modal title | 40 chars | 50 chars | Action or question |
| Input label | 25 chars | 40 chars | Noun phrase |
| Placeholder text | 30 chars | 50 chars | Example or format hint |

---

## Localization Considerations

| Factor | Guidance |
|--------|----------|
| Text expansion | Translated text runs 30-40% longer than English. Design for expansion. |
| String concatenation | Use complete sentences with placeholders, not concatenated fragments. "You have {count} items" not "You have " + count + " items" |
| Pluralization | Different languages have different plural rules (not just singular/plural). Use ICU MessageFormat or equivalent. |
| Date/time | Use locale-aware formatting. "May 5, 2026" vs "5 May 2026" vs "2026/5/5" |
| Cultural idioms | "Heads up" and "FYI" translate poorly. Use direct language: "Note:" or "Important:" |
| Right-to-left | UI layout mirrors for RTL languages. Icon placement, text alignment, and progress direction all reverse. |
| Color meaning | Red = danger in Western cultures, prosperity in Chinese culture. Rely on icons and text alongside color. |
| Gendered language | Some languages require gendered forms. Design copy to minimize gender-specific constructions where possible. |

**Localization-safe pattern**: Write copy that is literal, complete, and free of idioms. "Save your work before closing" translates cleanly. "Don't lose your stuff!" does not.
