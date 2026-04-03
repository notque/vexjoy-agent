# Animation Patterns Reference
<!-- Loaded by react-native-engineer when task involves animations, Reanimated, shared values, gestures, press states, interpolation -->

## Animate Transform and Opacity for 60fps Animations
**Impact:** HIGH — GPU-accelerated animations with no layout recalculation

Transform (`scale`, `translate`, `rotate`) and `opacity` run on the GPU without triggering layout recalculation. Animating `width`, `height`, `top`, `left`, `margin`, or `padding` recalculates layout on every frame — the main cause of animation jank.

**Instead of:**
```tsx
// triggers layout on every frame
const animatedStyle = useAnimatedStyle(() => ({
  height: withTiming(expanded ? 200 : 0),
}))
```

**Use:**
```tsx
import Animated, { useAnimatedStyle, withTiming } from 'react-native-reanimated'

// GPU-accelerated, no layout recalculation
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

For slide animations:
```tsx
const animatedStyle = useAnimatedStyle(() => ({
  transform: [{ translateY: withTiming(visible ? 0 : 100) }],
  opacity: withTiming(visible ? 1 : 0),
}))
```

GPU-accelerated properties: `transform` (translate, scale, rotate), `opacity`. Everything else triggers layout.

---

## Store State in Shared Values, Derive Visual Output
**Impact:** HIGH — single source of truth, easy to extend, clearer debugging

Shared values should represent real state (`pressed`, `progress`, `isOpen`), not visual outputs (`scale`, `opacity`). Derive visual values from state using `interpolate`. This keeps state as ground truth and makes it easy to add more visual effects without new state.

**Instead of:**
```tsx
// stores the visual output — scale is not a meaningful state
const scale = useSharedValue(1)
const tap = Gesture.Tap()
  .onBegin(() => scale.set(withTiming(0.95)))
  .onFinalize(() => scale.set(withTiming(1)))

const animatedStyle = useAnimatedStyle(() => ({
  transform: [{ scale: scale.get() }],
}))
```

**Use:**
```tsx
import { interpolate } from 'react-native-reanimated'

// stores meaningful state — 0 = not pressed, 1 = pressed
const pressed = useSharedValue(0)
const tap = Gesture.Tap()
  .onBegin(() => pressed.set(withTiming(1)))
  .onFinalize(() => pressed.set(withTiming(0)))

// derive visual values from state
const animatedStyle = useAnimatedStyle(() => ({
  transform: [{ scale: interpolate(pressed.get(), [0, 1], [1, 0.95]) }],
  opacity: interpolate(pressed.get(), [0, 1], [1, 0.7]),  // easy to add more effects
}))
```

---

## Use useDerivedValue Over useAnimatedReaction for Derivations
**Impact:** MEDIUM — declarative derivations with automatic dependency tracking

`useDerivedValue` is for computing a new shared value from existing ones — it's declarative and tracks dependencies automatically. `useAnimatedReaction` is for side effects (triggering haptics, calling `runOnJS`), not for producing values.

**Instead of:**
```tsx
const progress = useSharedValue(0)
const opacity = useSharedValue(1)

// useAnimatedReaction for derivation — imperative and requires manual deps
useAnimatedReaction(
  () => progress.value,
  (current) => { opacity.value = 1 - current }
)
```

**Use:**
```tsx
const progress = useSharedValue(0)

// useDerivedValue — declarative, automatic dependency tracking
const opacity = useDerivedValue(() => 1 - progress.get())
```

Use `useAnimatedReaction` only for side effects that don't produce a value.

---

## Use GestureDetector for Animated Press States
**Impact:** MEDIUM — UI thread animations without JS thread round-trip

For animated press states (scale on press, opacity on press), `GestureDetector` with `Gesture.Tap()` runs callbacks on the UI thread as worklets. Pressable's `onPressIn`/`onPressOut` go through the JS thread, adding latency.

**Instead of:**
```tsx
// Pressable callbacks run on JS thread — adds latency to press animation
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
  .onBegin(() => pressed.set(withTiming(1)))    // runs on UI thread
  .onFinalize(() => pressed.set(withTiming(0))) // runs on UI thread
  .onEnd(() => runOnJS(onPress)())              // bridges back to JS for the callback

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
**Impact:** LOW — required for React Compiler compatibility with Reanimated

With React Compiler enabled, use `.get()` and `.set()` instead of reading or writing `.value` directly. The compiler cannot track `.value` property access on shared values.

**Instead of:**
```tsx
// opts out of React Compiler optimization
count.value = count.value + 1
```

**Use:**
```tsx
count.set(count.get() + 1)
```

For worklet-only code (inside `useAnimatedStyle`, `useAnimatedReaction`), `.value` still works — the compiler does not process worklets. Use `.get()/.set()` in regular component code.
