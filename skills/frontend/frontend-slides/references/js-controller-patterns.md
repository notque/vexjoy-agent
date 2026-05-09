# JS Controller Patterns -- Frontend Slides Reference

> **Load this file during Phase 4 (BUILD) when implementing SlideController.**

## Assembly

Assemble the core controller with optional features:

```bash
python3 skills/frontend/frontend-slides/scripts/assemble-controllers.py --core
python3 scripts/assemble-controllers.py --core --features speaker-notes,countdown-timer
```

Use `--list` to see all components and pattern checks.
Use `--include-css` to bundle CSS components in output.

## Template Files

| File | Purpose |
|------|---------|
| `templates/controllers/slide-controller.js` | Core SlideController class |
| `templates/controllers/indicator.css` | Slide counter CSS |
| `templates/controllers/speaker-notes.js` | Speaker notes toggle (optional) |
| `templates/controllers/speaker-notes.css` | Notes panel CSS (optional) |
| `templates/controllers/countdown-timer.js` | Countdown timer (optional) |

## Core Controller Features

The `SlideController` class provides: keyboard navigation (arrows, Space, Home, End),
touch swipe with Y-axis rejection, wheel with 150ms debounce, IntersectionObserver
for reveal animations, and a position indicator.

## Pattern Checks

| Symptom | Check | Fix |
|---------|-------|-----|
| Skips 2-3 slides on key press | `grep -c 'navigating' output.html` | Add `navigating` guard to `go()` |
| Trackpad jumps to last slide | `rg 'clearTimeout' output.html` | Add 150ms debounce to wheel handler |
| Animations never fire | `grep 'display.*none' output.html` | Use `opacity:0` instead of `display:none` |
| Swipe fires on scroll | `grep 'screenY' output.html` | Add `abs(dy) > abs(dx)` guard |
| Space scrolls page | `grep -A1 'Space' output.html` | Add `e.preventDefault()` before `next()` |
| Indicator invisible | Visual check | Use `rgba(0,0,0,0.45)` + `backdrop-filter` |
