# UI Patterns Reference
<!-- Loaded by react-native-engineer when task involves images, modals, Pressable, safe area, ScrollView, styling, galleries, menus, layout measurement -->

## Use expo-image for All Image Rendering
**Impact:** HIGH — memory-efficient caching, blurhash placeholders, progressive loading, correct list recycling

`expo-image` provides disk+memory caching, blurhash placeholder support, progressive loading, and a `recyclingKey` prop for correct behavior in recycled list cells. React Native's built-in `Image` has none of these.

**Instead of:**
```tsx
import { Image } from 'react-native'
function Avatar({ url }: { url: string }) {
  return <Image source={{ uri: url }} style={styles.avatar} />
}
```

**Use:**
```tsx
import { Image } from 'expo-image'

function Avatar({ url }: { url: string }) {
  return (
    <Image
      source={{ uri: url }}
      placeholder={{ blurhash: 'LGF5]+Yk^6#M@-5c,1J5@[or[Q6.' }}
      contentFit="cover"
      transition={200}
      style={styles.avatar}
    />
  )
}
```

Key props: `placeholder` (blurhash while loading), `contentFit` (cover/contain/fill), `transition` (fade-in ms), `priority` (low/normal/high), `cachePolicy` (memory/disk/memory-disk), `recyclingKey` (for lists).

For cross-platform (web + native), `SolitoImage` from `solito/image` uses `expo-image` under the hood.

---

## Use Native Modals Over JS-Based Bottom Sheets
**Impact:** HIGH — native gestures, accessibility, and performance out of the box

Native modals with `presentationStyle="formSheet"` provide swipe-to-dismiss, proper keyboard avoidance, and accessibility automatically. JS-based bottom sheet libraries reimplement all of this in JavaScript.

**Instead of:**
```tsx
// JS bottom sheet library
import BottomSheet from 'some-js-bottom-sheet'
```

**Use:**
```tsx
import { Modal } from 'react-native'

function MyScreen() {
  const [visible, setVisible] = useState(false)
  return (
    <>
      <Button onPress={() => setVisible(true)} title="Open" />
      <Modal
        visible={visible}
        presentationStyle="formSheet"
        animationType="slide"
        onRequestClose={() => setVisible(false)}
      >
        <View style={{ padding: 16 }}>
          <Text>Sheet content</Text>
        </View>
      </Modal>
    </>
  )
}
```

With React Navigation v7:
```tsx
<Stack.Screen
  name="Details"
  component={DetailsScreen}
  options={{
    presentation: 'formSheet',
    sheetAllowedDetents: 'fitToContents',
  }}
/>
```

---

## Use Pressable Instead of Touchable Components
**Impact:** LOW — modern API, more flexible press handling

`TouchableOpacity` and `TouchableHighlight` are legacy. Use `Pressable` from `react-native`. For items inside scrollable lists, use `Pressable` from `react-native-gesture-handler` for better gesture coordination.

**Instead of:**
```tsx
import { TouchableOpacity } from 'react-native'
<TouchableOpacity onPress={onPress} activeOpacity={0.7}>
```

**Use:**
```tsx
import { Pressable } from 'react-native'
// or inside lists: import { Pressable } from 'react-native-gesture-handler'

<Pressable onPress={onPress}>
  <Text>Press me</Text>
</Pressable>
```

For animated press states (scale changes, opacity changes), use `GestureDetector` with Reanimated shared values instead — see `animation-patterns.md`.

---

## Use contentInsetAdjustmentBehavior for Safe Areas
**Impact:** MEDIUM — native safe area handling, no layout shifts, content scrolls behind status bar naturally

`contentInsetAdjustmentBehavior="automatic"` on the root ScrollView lets iOS handle safe area insets natively, including dynamic adjustments for keyboard and toolbars.

**Instead of:**
```tsx
// manual padding — misses dynamic adjustments
<SafeAreaView style={{ flex: 1 }}>
  <ScrollView>{children}</ScrollView>
</SafeAreaView>
```

**Use:**
```tsx
<ScrollView contentInsetAdjustmentBehavior="automatic">
  {children}
</ScrollView>
```

---

## Use contentInset for Dynamic ScrollView Spacing
**Impact:** LOW — no layout recalculation when spacing changes

When adding space that may change dynamically (keyboard height, toolbar visibility), `contentInset` adjusts scroll bounds without re-rendering content. Changing `contentContainerStyle.paddingBottom` triggers a full layout recalculation.

**Instead of:**
```tsx
// re-calculates layout when bottomOffset changes
<ScrollView contentContainerStyle={{ paddingBottom: bottomOffset }}>
```

**Use:**
```tsx
<ScrollView
  contentInset={{ bottom: bottomOffset }}
  scrollIndicatorInsets={{ bottom: bottomOffset }}
>
  {children}
</ScrollView>
```

Use `scrollIndicatorInsets` alongside `contentInset` to keep the scroll indicator aligned. Static spacing that never changes is fine as padding.

---

## Modern Styling Patterns
**Impact:** MEDIUM — consistent design, smoother borders, cleaner layouts

**Use `borderCurve: 'continuous'` with `borderRadius`** for smooth iOS-style corners:
```tsx
{ borderRadius: 12, borderCurve: 'continuous' }
```

**Use `gap` instead of margin for spacing between elements:**
```tsx
// Instead of: marginBottom on children
<View style={{ gap: 8 }}>
  <Text>Title</Text>
  <Text>Subtitle</Text>
</View>
```

**Use `experimental_backgroundImage` for linear gradients:**
```tsx
<View style={{ experimental_backgroundImage: 'linear-gradient(to bottom, #000, #fff)' }} />
```

**Use CSS `boxShadow` string syntax:**
```tsx
// Instead of: shadowColor, shadowOffset, shadowOpacity, elevation
{ boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)' }
```

**Limit font sizes — use weight and color for hierarchy:**
```tsx
// Instead of: fontSize 18/14/12 for title/subtitle/caption
<Text style={{ fontWeight: '600' }}>Title</Text>
<Text style={{ color: '#666' }}>Subtitle</Text>
<Text style={{ color: '#999' }}>Caption</Text>
```

---

## Use Galeria for Image Galleries with Lightbox
**Impact:** MEDIUM — native shared element transitions, pinch-to-zoom, pan-to-close

For tap-to-fullscreen image galleries, `@nandorojo/galeria` provides native shared element transitions, pinch-to-zoom, double-tap zoom, and pan-to-close with any image component.

**Use:**
```tsx
import { Galeria } from '@nandorojo/galeria'
import { Image } from 'expo-image'

function ImageGallery({ urls }: { urls: string[] }) {
  return (
    <Galeria urls={urls}>
      {urls.map((url, index) => (
        <Galeria.Image index={index} key={url}>
          <Image source={{ uri: url }} style={styles.thumbnail} />
        </Galeria.Image>
      ))}
    </Galeria>
  )
}
```

With a virtualizer:
```tsx
<Galeria urls={urls}>
  <FlashList
    data={urls}
    renderItem={({ item, index }) => (
      <Galeria.Image index={index}>
        <Image source={{ uri: item }} style={styles.thumbnail} />
      </Galeria.Image>
    )}
    estimatedItemSize={100}
  />
</Galeria>
```

---

## Use Native Menus for Dropdowns and Context Menus
**Impact:** HIGH — native accessibility, platform-consistent UX, no custom JS overlay needed

Use `zeego` for cross-platform native menus. Native menus automatically get platform accessibility, keyboard support, and system-consistent visual behavior.

**Instead of:**
```tsx
// custom JS dropdown with absolute-positioned View
{open && (
  <View style={{ position: 'absolute', top: 40 }}>
    <Pressable onPress={() => handleEdit()}><Text>Edit</Text></Pressable>
  </View>
)}
```

**Use:**
```tsx
import * as DropdownMenu from 'zeego/dropdown-menu'

<DropdownMenu.Root>
  <DropdownMenu.Trigger>
    <Pressable><Text>Options</Text></Pressable>
  </DropdownMenu.Trigger>
  <DropdownMenu.Content>
    <DropdownMenu.Item key="edit" onSelect={() => handleEdit()}>
      <DropdownMenu.ItemTitle>Edit</DropdownMenu.ItemTitle>
    </DropdownMenu.Item>
    <DropdownMenu.Item key="delete" destructive onSelect={() => handleDelete()}>
      <DropdownMenu.ItemTitle>Delete</DropdownMenu.ItemTitle>
    </DropdownMenu.Item>
  </DropdownMenu.Content>
</DropdownMenu.Root>
```

For long-press context menus, use `zeego/context-menu` with the same API structure.

---

## Measuring View Dimensions
**Impact:** MEDIUM — synchronous initial measurement, avoids unnecessary re-renders

Use `useLayoutEffect` for synchronous initial measurement and `onLayout` for updates when the view changes. For non-primitive states, use a dispatch updater to compare values and avoid unnecessary re-renders.

```tsx
import { useLayoutEffect, useRef, useState } from 'react'
import { View, LayoutChangeEvent } from 'react-native'

type Size = { width: number; height: number }

function MeasuredBox({ children }: { children: React.ReactNode }) {
  const ref = useRef<View>(null)
  const [size, setSize] = useState<Size | undefined>(undefined)

  useLayoutEffect(() => {
    // Synchronous measurement on mount (RN 0.82+)
    const rect = ref.current?.getBoundingClientRect()
    if (rect) setSize({ width: rect.width, height: rect.height })
  }, [])

  const onLayout = (e: LayoutChangeEvent) => {
    const { width, height } = e.nativeEvent.layout
    setSize((prev) => {
      // compare before firing re-render for non-primitive states
      if (prev?.width === width && prev?.height === height) return prev
      return { width, height }
    })
  }

  return (
    <View ref={ref} onLayout={onLayout}>
      {children}
    </View>
  )
}
```

---

## Use Compound Components for Flexible Button Composition
**Impact:** MEDIUM — explicit, composable API without polymorphic type gymnastics

Compound components give each part a clear role and a typed API — consumers compose exactly what they need.

**Instead of:**
```tsx
// ambiguous — accepts string or ReactNode
<Button icon={<Icon />}>Save</Button>
```

**Use:**
```tsx
function Button({ children }: { children: React.ReactNode }) {
  return <Pressable>{children}</Pressable>
}
function ButtonText({ children }: { children: React.ReactNode }) {
  return <Text>{children}</Text>
}
function ButtonIcon({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}

// explicit and composable
<Button>
  <ButtonIcon><SaveIcon /></ButtonIcon>
  <ButtonText>Save</ButtonText>
</Button>
```
