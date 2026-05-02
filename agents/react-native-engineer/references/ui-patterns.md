# UI Patterns Reference
<!-- Loaded by react-native-engineer when task involves images, modals, Pressable, safe area, ScrollView, styling, galleries, menus, layout measurement -->

## Use expo-image for All Image Rendering
**Impact:** HIGH — memory-efficient caching, blurhash placeholders, progressive loading, list recycling

**Instead of:**
```tsx
import { Image } from 'react-native'
<Image source={{ uri: url }} style={styles.avatar} />
```

**Use:**
```tsx
import { Image } from 'expo-image'

<Image
  source={{ uri: url }}
  placeholder={{ blurhash: 'LGF5]+Yk^6#M@-5c,1J5@[or[Q6.' }}
  contentFit="cover"
  transition={200}
  style={styles.avatar}
/>
```

Key props: `placeholder` (blurhash), `contentFit`, `transition`, `priority`, `cachePolicy`, `recyclingKey` (for lists). Cross-platform: `SolitoImage` from `solito/image`.

---

## Use Native Modals Over JS-Based Bottom Sheets
**Impact:** HIGH — native gestures, accessibility, performance

**Instead of:** JS bottom sheet libraries.

**Use:**
```tsx
<Modal
  visible={visible}
  presentationStyle="formSheet"
  animationType="slide"
  onRequestClose={() => setVisible(false)}
>
  <View style={{ padding: 16 }}><Text>Sheet content</Text></View>
</Modal>
```

With React Navigation v7:
```tsx
<Stack.Screen
  name="Details"
  component={DetailsScreen}
  options={{ presentation: 'formSheet', sheetAllowedDetents: 'fitToContents' }}
/>
```

---

## Use Pressable Instead of Touchable Components
**Impact:** LOW — modern API, more flexible

`TouchableOpacity`/`TouchableHighlight` are legacy. Use `Pressable` from `react-native`. In scrollable lists: `Pressable` from `react-native-gesture-handler`.

For animated press states, use `GestureDetector` with Reanimated — see `animation-patterns.md`.

---

## Use contentInsetAdjustmentBehavior for Safe Areas
**Impact:** MEDIUM — native safe area handling, no layout shifts

**Instead of:**
```tsx
<SafeAreaView style={{ flex: 1 }}><ScrollView>{children}</ScrollView></SafeAreaView>
```

**Use:**
```tsx
<ScrollView contentInsetAdjustmentBehavior="automatic">{children}</ScrollView>
```

---

## Use contentInset for Dynamic ScrollView Spacing
**Impact:** LOW — no layout recalculation on spacing changes

**Instead of:** `contentContainerStyle={{ paddingBottom: bottomOffset }}` (triggers layout recalc).

**Use:**
```tsx
<ScrollView
  contentInset={{ bottom: bottomOffset }}
  scrollIndicatorInsets={{ bottom: bottomOffset }}
>
  {children}
</ScrollView>
```

Static spacing that never changes is fine as padding.

---

## Modern Styling Patterns
**Impact:** MEDIUM

**Smooth corners**: `{ borderRadius: 12, borderCurve: 'continuous' }`

**Gap instead of margin**: `<View style={{ gap: 8 }}>`

**Linear gradients**: `{ experimental_backgroundImage: 'linear-gradient(to bottom, #000, #fff)' }`

**Box shadows**: `{ boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)' }`

**Font hierarchy via weight/color, not size**: Use `fontWeight: '600'` for titles, `color: '#666'` for subtitles, `color: '#999'` for captions.

---

## Use Galeria for Image Galleries with Lightbox
**Impact:** MEDIUM — native shared element transitions, pinch-to-zoom, pan-to-close

```tsx
import { Galeria } from '@nandorojo/galeria'
import { Image } from 'expo-image'

<Galeria urls={urls}>
  {urls.map((url, index) => (
    <Galeria.Image index={index} key={url}>
      <Image source={{ uri: url }} style={styles.thumbnail} />
    </Galeria.Image>
  ))}
</Galeria>
```

---

## Use Native Menus for Dropdowns and Context Menus
**Impact:** HIGH — native accessibility, platform-consistent UX

**Instead of:** Custom JS dropdown with absolute-positioned View.

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

For long-press: `zeego/context-menu` with same API.

---

## Measuring View Dimensions
**Impact:** MEDIUM — synchronous initial measurement, avoids unnecessary re-renders

```tsx
const ref = useRef<View>(null)
const [size, setSize] = useState<Size | undefined>(undefined)

useLayoutEffect(() => {
  const rect = ref.current?.getBoundingClientRect()
  if (rect) setSize({ width: rect.width, height: rect.height })
}, [])

const onLayout = (e: LayoutChangeEvent) => {
  const { width, height } = e.nativeEvent.layout
  setSize((prev) => {
    if (prev?.width === width && prev?.height === height) return prev
    return { width, height }
  })
}
```

---

## Use Compound Components for Flexible Button Composition
**Impact:** MEDIUM — explicit, composable API

**Instead of:** `<Button icon={<Icon />}>Save</Button>` (ambiguous).

**Use:**
```tsx
<Button>
  <ButtonIcon><SaveIcon /></ButtonIcon>
  <ButtonText>Save</ButtonText>
</Button>
```
