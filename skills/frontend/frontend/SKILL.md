---
name: frontend
description: "Frontend: UI design, distinctive visual styles, HTML artifacts, Three.js 3D, TypeScript/React/Next.js apps, e-commerce, portfolios, React Native, web performance."
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Agent
  - Skill
routing:
  force_route: false
  not_for: "game UI and combat rendering (use game-dev), backend work (use workflow), brand or logo design without code, TypeScript race conditions or runtime exceptions (use programming), backend or algorithmic performance in a specific language (use programming)"
  triggers:
    - "design"
    - "UX copy"
    - "design system"
    - "accessibility"
    - "WCAG"
    - "design handoff"
    - "frontend design"
    - "visual identity"
    - "HTML artifact"
    - "make HTML"
    - "self-contained HTML"
    - "threejs"
    - "three.js"
    - "3D web"
    - "3D scene"
    - "WebGL"
    - "WebGPU"
    - "react three fiber"
    - "r3f"
    - "text animation"
    - "card effects"
    - "pptx"
    - "powerpoint"
    - "slide deck"
    - "design critique"
    - "react"
    - "next.js"
    - "frontend"
    - ".tsx"
    - "zod"
    - "UI"
    - "tailwind"
    - "responsive"
    - "animations"
    - "portfolio"
    - "gallery"
    - "react portfolio"
    - "art website"
    - "image gallery"
    - "lightbox"
    - "next.js e-commerce"
    - "nextjs ecommerce"
    - "shopping cart"
    - "stripe"
    - "e-commerce"
    - "online store"
    - "product catalog"
    - "react native"
    - "expo"
    - "reanimated"
    - "flashlist"
    - "hermes"
    - "react-navigation"
    - "gesture handler"
    - "native stack"
    - "core web vitals"
    - "LCP"
    - "bundle size"
    - "render performance"
    - "web performance"
    - "lighthouse"
  category: frontend
  pairs_with:
    - code-quality
    - programming
    - testing
    - game-dev
---

# Frontend Skill

Four modes: **Design** (UX copy, design systems, critique, accessibility, handoff,
research), **Distinctive** (surface check, then brand-led visual direction for
landing and campaign pages), **HTML-Artifact** (self-contained HTML generation with 8 shapes), and
**Three.js** (3D web apps in imperative, R3F, or WebGPU paradigms). App
engineering (TypeScript, React, Next.js, commerce, portfolios, React Native, web
performance) loads one reference from the App Engineering table. When dispatch
pays, use a `general-purpose` worker that loads this skill and that reference.

## Load first for any UI work

Before DESIGN, DISTINCTIVE, HTML-ARTIFACT, or a THREEJS UI overlay (HUD, menu, panel), read `skills/shared-patterns/ui-design-judgment.md`. Take starting values from `ui-design-recipes.md` and before/after fixes from `ui-design-examples.md` in the same folder. The mode references below add depth. Where they conflict with the core doc, the core doc wins. Every default can be overridden; state the reason.

## Mode Selection

Classify the request into one mode before loading references.

| Mode | Signals | What to Load |
|------|---------|-------------|
| **DESIGN** | UX copy, design system, design critique, accessibility, WCAG, design handoff, user research | Design-refs per sub-mode table below |
| **DISTINCTIVE** | Frontend design, typography, visual identity, anti-cliche, text animation, card effects | `references/distinctive-frontend-design-refs/` per step |
| **HTML-ARTIFACT** | HTML artifact, make HTML, as HTML, rich visualization, interactive document, pptx, deck | `references/html-artifact-refs/` per shape |
| **THREEJS** | Three.js, 3D scene, WebGL, WebGPU, react three fiber, R3F, GLTF | `references/threejs-builder-refs/` per paradigm |
| **APP ENGINEERING** | TypeScript, React, Next.js, Tailwind, Zod, e-commerce, Stripe, portfolio, gallery, React Native, Expo, Core Web Vitals, bundle size | One file from the App Engineering table below |

## Mode Workflows

Load `references/mode-workflows.md` for full step-by-step phase checklists for DESIGN, DISTINCTIVE, HTML-ARTIFACT, and THREEJS modes. Quick entry pointers:

- **DESIGN:** Load `references/design-refs/llm-design-failure-modes.md` plus the sub-mode ref (`ux-copy.md`, `design-systems.md`, `design-critique.md`, `accessibility-review.md`, `design-handoff.md`).
- **DISTINCTIVE:** Classify surface first (Tool uses `ui-design-recipes.md`; Brand page runs Brief -> Type -> Color -> Motion -> `validate_design.py` -> core doc section 10 visual check).
- **HTML-ARTIFACT:** Self-contained local `.html` (inline CSS/JS, max 500 KB, embedded `archivo-black.css`, opened locally in Chrome; use Perses for metrics dashboards). Run `fill-template.py --list` -> `detect-shape.py` -> `assemble-template.py` -> `agents/html-builder.md` -> `validate-artifact.py` -> section 10 visual check.
- **THREEJS:** Detect paradigm first (R3F `useFrame`, WebGPU TSL, or Imperative `setAnimationLoop`) using `references/threejs-builder-refs/build-recipes.md` + paradigm ref, keep allocations outside the render loop, and finish with section 10 visual check.

---

## Deep References

Load on demand when the task needs detailed patterns, examples, or specifications:

### App Engineering

Each file holds hard rules, workflow, and its own loading table for `references/<slug>/`.

| Signal | Load |
|--------|------|
| TypeScript, React, Next.js, `.tsx`, Zod, tsconfig, React 19 migration, type-safe state or API clients, build config | `references/typescript-frontend.md` |
| UI implementation: Tailwind, design tokens, responsive layout, accessibility, animations, interaction states, AI-slop cleanup | `references/ui-design.md` |
| Portfolio, gallery, art website, image gallery, lightbox, artist site | `references/react-portfolio.md` |
| Next.js e-commerce, shopping cart, Stripe, checkout, product catalog, online store, admin dashboard | `references/nextjs-ecommerce.md` |
| React Native, Expo, Reanimated, FlashList, Hermes, react-navigation, gesture handler, native stack | `references/react-native.md` |
| Core Web Vitals, LCP, INP, CLS, bundle size, render performance, Lighthouse, RUM, performance budgets | `references/performance-optimization.md` |

### Design Refs

| File | Content |
|------|---------|
| `references/design-refs/ux-copy.md` | Component-specific UX copy patterns |
| `references/design-refs/design-systems.md` | Design token architecture, component specs |
| `references/design-refs/design-critique.md` | Structured critique method, heuristics |
| `references/design-refs/accessibility-review.md` | WCAG criteria, component a11y patterns |
| `references/design-refs/design-handoff.md` | Spec categories, artifact templates |
| `references/design-refs/llm-design-failure-modes.md` | LLM design failure modes with defenses |

### Distinctive Frontend Design Refs

| File | Content |
|------|---------|
| `references/distinctive-frontend-design-refs/font-catalog.json` | Curated fonts by aesthetic category |
| `references/distinctive-frontend-design-refs/color-inspirations.json` | Cultural/contextual palette sources |
| `references/distinctive-frontend-design-refs/animation-patterns.md` | Animation choreography with CSS/React |
| `references/distinctive-frontend-design-refs/background-techniques.md` | Atmospheric background methods |
| `references/distinctive-frontend-design-refs/implementation-examples.md` | CSS tokens, framework templates |
| `references/distinctive-frontend-design-refs/macrostructure-catalog.md` | Named macro:* page structures |
| `references/distinctive-frontend-design-refs/phase-details.md` | Direction examples, motion timing, hero, backgrounds, design stamp |
| `references/distinctive-frontend-design-refs/css-audit-patterns.md` | Grep commands to audit existing CSS |
| `references/distinctive-frontend-design-refs/performance-budgets.md` | Render costs, layout thrashing |
| `references/distinctive-frontend-design-refs/game-ui-polish.md` | Game-native UI polish rules |
| `references/distinctive-frontend-design-refs/card-shader-patterns.md` | Fragment shader GLSL |
| `references/distinctive-frontend-design-refs/shader-integration-react.md` | React 19 WebGL hook + context pool |
| `references/distinctive-frontend-design-refs/balatro-shader-breakdown.md` | Holographic foil shader |
| `references/distinctive-frontend-design-refs/roll-text.md` | Roll/slot text patterns |
| `references/distinctive-frontend-design-refs/text-animation-patterns.md` | Reveal, typewriter, crossfade |
| `references/distinctive-frontend-design-refs/oklch-color-harmony.md` | OKLCH color harmony |
| `references/distinctive-frontend-design-refs/honest-placeholders.md` | Placeholder content rules |

### HTML Artifact Refs

| File | Content |
|------|---------|
| `references/html-artifact-refs/design-system.md` | Theme tokens, a11y checklist, SVG rules |
| `references/html-artifact-refs/diagram-layering.md` | SVG layer order, dark-theme colors |
| `references/html-artifact-refs/infographic-layouts.md` | 21 layout types, 22 visual styles |
| `references/html-artifact-refs/pdf-export.md` | Page-size table, troubleshooting |
| `references/html-artifact-refs/pptx-export.md` | Layout types, THEME dict, CLI ref |
| `references/html-artifact-refs/shape-diagram-illustration.md` | SVG construction, diagram types |

### Three.js Refs

| File | Content |
|------|---------|
| `references/threejs-builder-refs/build-recipes.md` | Boilerplate, scene setup, error handling |
| `references/threejs-builder-refs/react-three-fiber.md` | R3F patterns, Drei, Zustand |
| `references/threejs-builder-refs/webgpu.md` | WebGPURenderer, TSL, compute shaders |
| `references/threejs-builder-refs/advanced-topics.md` | GLTF, post-processing, shaders, physics |
| `references/threejs-builder-refs/visual-polish.md` | Materials, lighting, HDR, shadows |
| `references/threejs-builder-refs/gltf-loading.md` | Coordinate contract, caching, auto-center |
| `references/threejs-builder-refs/game-patterns.md` | Animation FSM, camera movement, input |
| `references/threejs-builder-refs/game-architecture.md` | EventBus, GameState, pre-ship checklist |
| `references/threejs-builder-refs/shader-patterns.md` | ShaderMaterial, vertex displacement, effects |
| `references/threejs-builder-refs/performance-patterns.md` | InstancedMesh, batching, LOD, dispose |
| `references/threejs-builder-refs/advanced-animation.md` | AnimationMixer, IK, spring physics, GSAP |

## Scripts

- Distinctive design: `scripts-distinctive-frontend-design/validate_design.py`, `scripts-distinctive-frontend-design/css_slop_rules.py`
- HTML artifact: `scripts-html-artifact/detect-shape.py`, `scripts-html-artifact/assemble-template.py`, `scripts-html-artifact/validate-artifact.py`, `scripts-html-artifact/fill-template.py`, `scripts-html-artifact/to-pdf.py`, `scripts-html-artifact/pptx-bridge/`
- HTML artifact templates: `templates/`, agents: `agents/html-builder.md`
