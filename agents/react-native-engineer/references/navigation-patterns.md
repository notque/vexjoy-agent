# Navigation Patterns Reference
<!-- Loaded by react-native-engineer when task involves navigation, stacks, tabs, expo-router, react-navigation, screen transitions -->

## Use Native Navigators for Stacks and Tabs
**Impact:** HIGH — native transitions, platform-appropriate UI, system integration

Native navigators use platform APIs (UINavigationController on iOS, Fragment on Android) for transitions, gestures, and behavior. JS-based navigators reimplement these in JavaScript — they are slower and miss platform nuances like iOS large titles, Android back stack, and scroll-to-top on tab tap.

### Stack Navigation

**Instead of:**
```tsx
// JS stack navigator — slower transitions, no platform integration
import { createStackNavigator } from '@react-navigation/stack'
const Stack = createStackNavigator()
```

**Use:**
```tsx
// Native stack — uses UINavigationController / Fragment
import { createNativeStackNavigator } from '@react-navigation/native-stack'
const Stack = createNativeStackNavigator()

function App() {
  return (
    <Stack.Navigator>
      <Stack.Screen name="Home" component={HomeScreen} />
      <Stack.Screen name="Details" component={DetailsScreen} />
    </Stack.Navigator>
  )
}
```

With expo-router, the default `<Stack />` already uses native-stack:
```tsx
// app/_layout.tsx
import { Stack } from 'expo-router'
export default function Layout() {
  return <Stack />
}
```

### Tab Navigation

**Instead of:**
```tsx
// JS bottom tabs
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs'
```

**Use:**
```tsx
// Native bottom tabs — platform tab bar component
import { createNativeBottomTabNavigator } from '@bottom-tabs/react-navigation'
const Tab = createNativeBottomTabNavigator()

function App() {
  return (
    <Tab.Navigator>
      <Tab.Screen
        name="Home"
        component={HomeScreen}
        options={{ tabBarIcon: () => ({ sfSymbol: 'house' }) }}
      />
      <Tab.Screen
        name="Settings"
        component={SettingsScreen}
        options={{ tabBarIcon: () => ({ sfSymbol: 'gear' }) }}
      />
    </Tab.Navigator>
  )
}
```

With expo-router native tabs:
```tsx
// app/(tabs)/_layout.tsx
import { NativeTabs } from 'expo-router/unstable-native-tabs'

export default function TabLayout() {
  return (
    <NativeTabs>
      <NativeTabs.Trigger name="index">
        <NativeTabs.Trigger.Label>Home</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="house.fill" md="home" />
      </NativeTabs.Trigger>
    </NativeTabs>
  )
}
```

---

## Prefer Native Header Options Over Custom Header Components
**Impact:** MEDIUM — automatic large titles, search bars, blur effects, proper safe areas

**Instead of:**
```tsx
<Stack.Screen
  name="Profile"
  options={{ header: () => <CustomHeader title="Profile" /> }}
/>
```

**Use:**
```tsx
<Stack.Screen
  name="Profile"
  options={{
    title: 'Profile',
    headerLargeTitleEnabled: true,       // iOS large title
    headerSearchBarOptions: {            // native search bar
      placeholder: 'Search',
    },
  }}
/>
```

Native headers automatically handle safe areas, blur effects, and scroll behavior. iOS native tabs also automatically enable `contentInsetAdjustmentBehavior` on the first `ScrollView` in each tab screen.

---

## Benefits of Native Navigators

- **Performance**: Transitions and gestures run on the UI thread
- **Platform behavior**: iOS large titles, Android material design, system back gesture
- **System integration**: Scroll-to-top on tab tap, picture-in-picture avoidance, correct safe areas
- **Accessibility**: Platform accessibility features work automatically without custom implementation
