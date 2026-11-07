# Navigation Patterns Reference
<!-- Loaded by react-native-engineer when task involves navigation, stacks, tabs, expo-router, react-navigation, screen transitions -->

## Use Native Navigators for Stacks and Tabs
**Impact:** HIGH — native transitions, platform UI, system integration

Native navigators use platform APIs (UINavigationController / Fragment). JS-based navigators reimplement in JavaScript — slower, missing platform nuances.

### Stack

**Instead of:**
```tsx
import { createStackNavigator } from '@react-navigation/stack'
```

**Use:**
```tsx
import { createNativeStackNavigator } from '@react-navigation/native-stack'
const Stack = createNativeStackNavigator()
```

With expo-router, `<Stack />` already uses native-stack.

### Tabs

**Instead of:**
```tsx
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs'
```

**Use:**
```tsx
import { createNativeBottomTabNavigator } from '@bottom-tabs/react-navigation'
const Tab = createNativeBottomTabNavigator()
```

With expo-router:
```tsx
import { NativeTabs } from 'expo-router/unstable-native-tabs'
```

---

## Prefer Native Header Options Over Custom Components
**Impact:** MEDIUM — automatic large titles, search bars, blur effects, safe areas

**Instead of:**
```tsx
<Stack.Screen name="Profile" options={{ header: () => <CustomHeader title="Profile" /> }} />
```

**Use:**
```tsx
<Stack.Screen
  name="Profile"
  options={{
    title: 'Profile',
    headerLargeTitleEnabled: true,
    headerSearchBarOptions: { placeholder: 'Search' },
  }}
/>
```

Native headers handle safe areas, blur effects, and scroll behavior automatically. iOS native tabs also enable `contentInsetAdjustmentBehavior` on the first ScrollView.

---

## Benefits of Native Navigators

- **Performance**: Transitions and gestures on UI thread
- **Platform behavior**: iOS large titles, Android material design, system back gesture
- **System integration**: Scroll-to-top on tab tap, correct safe areas
- **Accessibility**: Platform features work automatically
