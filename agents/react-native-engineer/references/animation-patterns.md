# Animation Patterns Reference
<!-- Loaded by react-native-engineer when task involves animations, Reanimated, shared values, gestures, press states, interpolation -->

## Animate Transform and Opacity for 60fps
**Impact:** HIGH — GPU-accelerated, no layout recalculation

Transform and opacity run on the GPU. Animating `width`, `height`, `top`, `left`, `margin`, or `padding` recalculates layout every frame.

**Instead of:**
```tsx
const animatedStyle = useAnimatedStyle(() => ({
  height: withTiming(expanded ? 200 : 0),
}))
```

**Use:**
```tsx
import Animated, { useAnimatedStyle, withTiming } from 'react-native-reanimated'

const animatedStyle = useAnimatedStyle(() => ({
  transform: [{ scaleY: withTiming(expanded ? 1 : 0) }],
  opacity: withTiming(expanded ? 1 : 0),
}))

return (
  <Animated.View style={[{ height: 200, transformOrigin: 'top' }, animatedStyle]}>
    {children}
  </Animated.View>
)
```

For slides: `transform: [{ translateY: withTiming(visible ? 0 : 100) }]`

GPU-accelerated: `transform` (translate, scale, rotate), `opacity`. Everything else triggers layout.

---

## Store State in Shared Values, Derive Visual Output
**Impact:** HIGH — single source of truth, easy to extend

Shared values represent real state (`pressed`, `progress`, `isOpen`), not visual outputs (`scale`, `opacity`). Derive visuals using `interpolate`.

**Instead of:**
```tsx
const scale = useSharedValue(1)
const tap = Gesture.Tap()
  .onBegin(() => scale.set(withTiming(0.95)))
  .onFinalize(() => scale.set(withTiming(1)))
```

**Use:**
```tsx
import { interpolate } from 'react-native-reanimated'

const pressed = useSharedValue(0)
const tap = Gesture.Tap()
  .onBegin(() => pressed.set(withTiming(1)))
  .onFinalize(() => pressed.set(withTiming(0)))

const animatedStyle = useAnimatedStyle(() => ({
  transform: [{ scale: interpolate(pressed.get(), [0, 1], [1, 0.95]) }],
  opacity: interpolate(pressed.get(), [0, 1], [1, 0.7]),
}))
```

---

## Use useDerivedValue Over useAnimatedReaction for Derivations
**Impact:** MEDIUM — declarative with automatic dependency tracking

`useDerivedValue` computes new shared values declaratively. `useAnimatedReaction` is for side effects (haptics, `runOnJS`), not producing values.

**Instead of:**
```tsx
useAnimatedReaction(
  () => progress.value,
  (current) => { opacity.value = 1 - current }
)
```

**Use:**
```tsx
const opacity = useDerivedValue(() => 1 - progress.get())
```

---

## Use GestureDetector for Animated Press States
**Impact:** MEDIUM — UI thread animations without JS thread round-trip

`GestureDetector` with `Gesture.Tap()` runs callbacks as worklets on UI thread. Pressable's `onPressIn`/`onPressOut` go through JS thread, adding latency.

**Instead of:**
```tsx
<Pressable
  onPressIn={() => scale.set(withTiming(0.95))}
  onPressOut={() => scale.set(withTiming(1))}
  onPress={onPress}
>
```

**Use:**
```tsx
import { Gesture, GestureDetector } from 'react-native-gesture-handler'
import { runOnJS } from 'react-native-reanimated'

const pressed = useSharedValue(0)

const tap = Gesture.Tap()
  .onBegin(() => pressed.set(withTiming(1)))
  .onFinalize(() => pressed.set(withTiming(0)))
  .onEnd(() => runOnJS(onPress)())

const animatedStyle = useAnimatedStyle(() => ({
  transform: [{ scale: interpolate(pressed.get(), [0, 1], [1, 0.95]) }],
}))

return (
  <GestureDetector gesture={tap}>
    <Animated.View style={animatedStyle}>
      <Text>Press me</Text>
    </Animated.View>
  </GestureDetector>
)
```

---

## Use .get() and .set() with React Compiler
**Impact:** LOW — required for React Compiler compatibility

With React Compiler, use `.get()` and `.set()` instead of `.value`. The compiler cannot track `.value` access.

**Instead of:**
```tsx
count.value = count.value + 1
```

**Use:**
```tsx
count.set(count.get() + 1)
```

Inside worklets (`useAnimatedStyle`, `useAnimatedReaction`), `.value` still works — the compiler does not process worklets.
