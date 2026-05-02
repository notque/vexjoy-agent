# Monorepo Config Reference
<!-- Loaded by react-native-engineer when task involves monorepo, fonts, imports, design system, dependency versions, autolinking -->

## Install Native Dependencies in the App Directory
**Impact:** CRITICAL — required for autolinking

Autolinking only scans the native app's `node_modules`. Native deps in shared packages but missing from the app directory won't link.

**Instead of:**
```
packages/
  ui/
    package.json  ← has react-native-reanimated
  app/
    package.json  ← missing react-native-reanimated ← autolinking fails
```

**Use:**
```json
// packages/app/package.json
{
  "dependencies": {
    "react-native-reanimated": "3.16.1"
  }
}
```

Even if only the shared package uses the native dep, the app must declare it.

---

## Use Single Dependency Versions Across the Monorepo
**Impact:** MEDIUM — avoids duplicate bundles and version conflicts

**Instead of:**
```json
// packages/app: "react-native-reanimated": "^3.0.0"
// packages/ui:  "react-native-reanimated": "^3.5.0"
```

**Use:**
```json
// package.json (root)
{
  "pnpm": {
    "overrides": { "react-native-reanimated": "3.16.1" }
  }
}
// npm: "overrides", yarn: "resolutions"
```

Use exact versions (no `^` or `~`). Use `syncpack` to audit consistency.

---

## Load Fonts at Build Time with Expo Config Plugin
**Impact:** LOW — fonts available at launch, no loading state

**Instead of:**
```tsx
const [fontsLoaded] = useFonts({ 'Geist-Bold': require('./assets/fonts/Geist-Bold.otf') })
if (!fontsLoaded) return null
```

**Use:**
```json
// app.json
{
  "expo": {
    "plugins": [
      ["expo-font", { "fonts": ["./assets/fonts/Geist-Bold.otf"] }]
    ]
  }
}
```

Run `npx expo prebuild` after adding fonts. Requires Expo (managed or bare with config plugins).

---

## Re-export Dependencies Through a Design System Folder
**Impact:** LOW — single point of change for component swaps

**Instead of:**
```tsx
import { View, Text } from 'react-native'
import { Button } from '@ui/button'
```

**Use:**
```tsx
// components/view.tsx
export function View(props: Pick<React.ComponentProps<typeof RNView>, 'style' | 'children'>) {
  return <RNView {...props} />
}

// App code
import { View } from '@/components/view'
```

Start with re-exports. Customize prop shapes later without changing app code.
