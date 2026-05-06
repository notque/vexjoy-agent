# Series Plan Output Format

Standard output template for the series-planner skill.

---

## Complete Series Plan

```
===============================================================
 SERIES PLAN: "[Series Title]"
===============================================================

 Type: [Progressive Depth / Chronological Build / Problem Exploration]
 Parts: [N]
 Total Estimated: [X,XXX-X,XXX] words
 Publishing Cadence: [frequency]

 PART BREAKDOWN:

 Part 1: "[Part Title]" [XXX-XXX words]
   Scope: [What this part covers]
   Standalone value: [What reader gets from this part alone]
   Links forward: "[Teaser for Part 2]"

 Part 2: "[Part Title]" [XXX-XXX words]
   Scope: [What this part covers]
   Standalone value: [What reader gets from this part alone]
   Links back: [What was covered in Part 1]
   Links forward: "[Teaser for Part 3]"

 Part 3: "[Part Title]" [XXX-XXX words]
   Scope: [What this part covers]
   Standalone value: [What reader gets from this part alone]
   Links back: [What was covered in Parts 1-2]
   [Continue pattern...]

 Part N (Final): "[Part Title]" [XXX-XXX words]
   Scope: [What this part covers]
   Standalone value: [What reader gets from this part alone]
   Links back: [What was covered in previous parts]
   Series completion: [How this wraps up the series]

 CROSS-LINKING STRUCTURE:
   - Each part header: "Part X of [N] in the [Series Title] series"
   - Navigation footer: [Previous: Part X] | [Next: Part Y]
   - Series page: /series/[series-slug]/

 PUBLICATION SCHEDULE:
   [Date/Week 1]: Part 1 - [Brief description]
   [Date/Week 2]: Part 2 - [Brief description]
   [Continue...]

 HUGO FRONTMATTER TEMPLATE:
   ---
   title: "[Series Title]: Part X - [Part Title]"
   date: YYYY-MM-DD
   draft: false
   tags: ["[tag1]", "[tag2]", "series:[series-slug]"]
   series: "[Series Title]"
   series_part: X
   summary: "[One sentence for list views]"
   ---

===============================================================
```

---

## Standalone Value Verification Block

Include this block after each part breakdown to show verification was performed:

```
 STANDALONE VERIFICATION:
   Part 1: [PASS/FAIL] - [reason]
   Part 2: [PASS/FAIL] - [reason]
   Part 3: [PASS/FAIL] - [reason]
   [Continue for all parts...]
```

### Pass Criteria

For each part, ALL must be true:
- Reader learns something complete (not half a concept)
- Working code/config/output is possible from this part alone
- No critical information deferred to other parts
- Value proposition is clear without reading series context
- Someone landing on just this part gets something useful

### Fail Indicators

Any of these means the part fails standalone verification:
- "To understand this, read Part 1 first" as mandatory
- Part ends mid-implementation
- Core concepts explained only in earlier parts, not summarized
- "Part 2 will explain why this works"

---

## Minimal Mode Output

When `--minimal` is specified, use this abbreviated format:

```
===============================================================
 SERIES: "[Series Title]" ([Type], [N] parts)
===============================================================

 Part 1: [Title] - [Scope in 1 sentence]
 Part 2: [Title] - [Scope in 1 sentence]
 Part 3: [Title] - [Scope in 1 sentence]
 [...]

 Cadence: [frequency]
===============================================================
```

---

## Landing Page Plan Output

When `--with-landing` is specified, append this section:

```
 LANDING PAGE: /series/[series-slug]/

 Title: "[Series Title]: Complete Series"
 Description: [1-2 sentence overview]

 Structure:
   - What You'll Learn (bullet per part)
   - Prerequisites
   - Parts list (auto-generated from series metadata)

 Hugo frontmatter:
   ---
   title: "[Series Title]: Complete Series"
   date: [first part date]
   draft: false
   type: series
   ---
```
