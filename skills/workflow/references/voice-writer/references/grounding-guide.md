# Grounding Guide

Full reference for Phase 2 (GROUND) of the voice-writer pipeline.

---

## Emotional Anchoring Questions

Answer these three questions before generating:

| Question | Why It Matters |
|----------|----------------|
| What emotion drives this content? | Sets underlying tone (celebration, frustration, curiosity) |
| What does the writer care about? | Guides emphasis and detail level |
| Who are they writing for? | Calibrates assumed knowledge and language |

---

## Relational Positioning Table

| Dimension | Options |
|-----------|---------|
| Writer-Audience relationship | Peer, expert, fan, community member |
| Assumed knowledge level | Newcomer, familiar, expert |
| Intimacy level | Public formal, community casual, personal |

---

## Mode Selection Details

Select content mode from the voice's `config.json` modes list. Each voice defines modes that shape structure and tone:

- **"awards" mode**: produces celebratory recognition pieces
- **"technical" mode**: produces systems explanations
- Other modes are voice-specific and defined in each voice's `config.json`

If user does not specify a mode, infer the best match from the subject matter and available modes.

---

## Blog Post Assessment Template

When the content is a blog post, article, or similar structured piece:

```markdown
## Assessment
- Topic: [user-provided topic]
- Scope: [narrow / medium / broad]
- Audience: [beginner / intermediate / expert]
- Estimated length: [short 500-800 / medium 1000-1500 / long 2000+]
```

---

## Structure Planning Template

Plan the post structure using voice patterns and structure templates:

```markdown
## Plan
- Opening pattern: [Provocative Question / News Lead / Bold Claim / Direct Answer]
- Draft opening: [first sentence or question]
- Core metaphor: [conceptual lens, if voice uses extended metaphors]
- Sections:
  1. [Section name]: [purpose]
  2. [Section name]: [purpose]
  ...
- Closing pattern: [Callback / Implication / Crescendo]
- Callback element: [what from opening returns]
```

Draft frontmatter if writing to a Hugo site:

```yaml
---
title: "Post Title Here"
slug: "post-slug-here"
date: YYYY-MM-DD
draft: false
tags: ["tag1", "tag2"]
summary: "One sentence description for list views"
---
```

---

## Content Type Selection

Select content type from `references/structure-templates.md` if available:

- **Problem-Solution**: Bug fix, debugging session, resolution
- **Technical Explainer**: Concept, technology, how it works
- **Walkthrough**: Step-by-step instructions for a task
