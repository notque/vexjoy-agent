# React Native and Expo

Performant, native-feeling mobile apps with React Native and Expo. Patterns apply to both the Expo managed workflow and bare React Native unless noted.

Not for: React web apps (`typescript-frontend.md`); portfolio and gallery sites (`react-portfolio.md`).

Domains:
- **List performance:** virtualized lists (LegendList, FlashList), memoization, stable references, item recycling.
- **Animations:** Reanimated GPU-accelerated animations, gesture handling, shared values.
- **Navigation:** native navigators (native-stack, react-native-bottom-tabs, expo-router).
- **Native UI:** expo-image, native modals, Pressable, safe areas, native menus.
- **State:** minimal state, derived values, Zustand selectors, dispatch updaters.
- **Rendering:** conditional rendering safety, Text component rules, React Compiler compatibility.
- **Monorepo config:** native dependency autolinking, single dependency versions, design system imports.

## Phases

### UNDERSTAND

- Read and follow the repository CLAUDE.md first; project conventions override these defaults.
- Check injected retro-knowledge for react-native-patterns, mobile-performance, and animation learnings.
- Confirm Expo managed vs bare React Native.
- Confirm whether React Compiler is enabled (it changes memoization advice).
- Identify the domain the task touches (list, animation, navigation, UI).

### IMPLEMENT

Load only the reference for the task's domain (table below), then implement.

- Prefer native platform APIs over JavaScript reimplementations; native modules are faster and more reliable than JS polyfills.
- Change only what is requested or clearly necessary; over-engineering mobile code grows bundle size and bridge traffic.
- Profile before optimizing: measure with Flipper or React DevTools before guessing at bottlenecks.

### VERIFY

- Run TypeScript compilation if applicable.
- Test on iOS and Android when behavior may differ.
- List changes: no jank on fast scroll.
- Animation changes: 60fps on the UI thread.

## Reference loading table

| Signal | Load |
|---|---|
| Screen layout, visual hierarchy, spacing, type, color, empty/error states (load first; iOS and Android conventions win over web defaults) | `skills/shared-patterns/ui-design-judgment.md`, then `ui-design-recipes.md` and `ui-design-examples.md` in the same folder |
| Lists, FlatList, FlashList, LegendList, scroll performance, virtualization, renderItem | `react-native/list-performance.md` |
| Animations, Reanimated, shared values, gestures, press states, interpolation | `react-native/animation-patterns.md` |
| Navigation, stacks, tabs, expo-router, react-navigation, screen transitions | `react-native/navigation-patterns.md` |
| Images, modals, Pressable, safe area, ScrollView, styling, galleries, menus, layout measurement | `react-native/ui-patterns.md` |
| useState, derived state, Zustand, state structure, dispatchers, ground truth | `react-native/state-management.md` |
| Conditional rendering, &&, Text components, React Compiler, memoization | `react-native/rendering-patterns.md` |
| Monorepo, fonts, imports, design system, dependency versions, autolinking | `react-native/monorepo-config.md` |
| Tests, RNTL, jest, Maestro, Detox, native module mocking, waitFor, snapshot | `react-native/testing.md` |
| Error boundaries, Sentry, crash recovery, unhandled rejection, try/catch, fetch errors | `react-native/error-handling.md` |

Companion skill: `code-quality` for cleanup, linting, formatting, and quality gates.

## Symptom to reference

| Symptom | Load | Likely cause |
|---|---|---|
| Scroll jank | `react-native/list-performance.md` | Inline objects, missing memoization, expensive `renderItem` |
| Animation not smooth | `react-native/animation-patterns.md` | Animating layout properties instead of transform/opacity |
| Native module not found | `react-native/monorepo-config.md` | Autolinking: native dep not installed in the app directory |
| Text rendering crash | `react-native/rendering-patterns.md` | String outside `Text`, or falsy `&&` rendering |
| State sync issues | `react-native/state-management.md` | Stale closure or redundant derived state |
| Production crashes, Error Boundaries, Sentry, unhandled rejections | `react-native/error-handling.md` | Boundary setup, crash reporting, fetch error handling |
| Test setup, RNTL queries, native module mocks, async assertions | `react-native/testing.md` | RNTL patterns, jest config, native mocks, failure modes |
