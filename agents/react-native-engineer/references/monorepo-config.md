# Monorepo Config Reference
<!-- Loaded by react-native-engineer when task involves monorepo, fonts, imports, design system, dependency versions, autolinking -->

## Install Native Dependencies in the App Directory
**Impact:** CRITICAL — required for autolinking to work

In a monorepo, autolinking only scans the native app's `node_modules`. A native dependency installed in a shared package but missing from the app directory will not be linked — the native module will appear missing at runtime.

**Instead of:**
```
packages/
  ui/
    package.json  ← has react-native-reanimated
  app/
    package.json  ← missing react-native-reanimated  ← autolinking fails
```

**Use:**
```
packages/
  ui/
    package.json  ← has react-native-reanimated
  app/
    package.json  ← also has react-native-reanimated  ← autolinking works
```

```json
// packages/app/package.json
{
  "dependencies": {
    "react-native-reanimated": "3.16.1"
  }
}
```

Even if only the shared `ui` package uses the native dependency, the app must also declare it for autolinking to detect and link the native code.

---

## Use Single Dependency Versions Across the Monorepo
**Impact:** MEDIUM — avoids duplicate bundles, prevents version conflicts

Multiple versions of the same package cause duplicate code in the bundle, runtime conflicts, and inconsistent behavior. Use exact versions (no `^` or `~`) and enforce a single version via package manager overrides.

**Instead of:**
```json
// packages/app/package.json
{ "dependencies": { "react-native-reanimated": "^3.0.0" } }

// packages/ui/package.json
{ "dependencies": { "react-native-reanimated": "^3.5.0" } }
// Two different resolved versions — duplicated native code
```

**Use:**
```json
// package.json (root) — enforce via package manager
{
  "pnpm": {
    "overrides": { "react-native-reanimated": "3.16.1" }
  }
}
// For npm: use "overrides" field
// For yarn: use "resolutions" field

// packages/app/package.json
{ "dependencies": { "react-native-reanimated": "3.16.1" } }

// packages/ui/package.json
{ "dependencies": { "react-native-reanimated": "3.16.1" } }
```

Use `syncpack` to audit and fix version consistency across all packages. Specify exact versions when adding new dependencies.

---

## Load Fonts at Build Time with Expo Config Plugin
**Impact:** LOW — fonts available at app launch, no async loading or loading state

The `expo-font` config plugin embeds fonts into the native binary at build time. The `useFonts` / `Font.loadAsync` approach loads fonts asynchronously at runtime, requiring loading state management and potentially showing a flash of unstyled text.

**Instead of:**
```tsx
import { useFonts } from 'expo-font'

function App() {
  const [fontsLoaded] = useFonts({
    'Geist-Bold': require('./assets/fonts/Geist-Bold.otf'),
  })
  if (!fontsLoaded) return null  // loading state required
  return <View><Text style={{ fontFamily: 'Geist-Bold' }}>Hello</Text></View>
}
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

```tsx
function App() {
  // no loading state — font is available at launch
  return <View><Text style={{ fontFamily: 'Geist-Bold' }}>Hello</Text></View>
}
```

After adding fonts to the config plugin, run `npx expo prebuild` and rebuild the native app. This pattern requires Expo (managed or bare with config plugins). For bare React Native without Expo, use the React Native font linking workflow.

---

## Re-export Dependencies Through a Design System Folder
**Impact:** LOW — enables global refactoring, single point of change for component swaps

App code importing directly from packages creates many import sites to update when switching libraries. Re-exporting through a design system folder means switching `Image` from `react-native` to `expo-image` requires one file change, not hundreds.

**Instead of:**
```tsx
import { View, Text } from 'react-native'
import { Button } from '@ui/button'
```

**Use:**
```tsx
// components/view.tsx — re-export with controlled props
import { View as RNView } from 'react-native'
export function View(props: Pick<React.ComponentProps<typeof RNView>, 'style' | 'children'>) {
  return <RNView {...props} />
}

// components/text.tsx
export { Text } from 'react-native'

// components/button.tsx
export { Button } from '@ui/button'
```

```tsx
// App code imports from design system, not packages
import { View } from '@/components/view'
import { Text } from '@/components/text'
import { Button } from '@/components/button'
```

Start by simply re-exporting. Customize prop shapes and add defaults later without changing app code.
