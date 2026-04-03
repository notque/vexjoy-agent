# List Performance Reference
<!-- Loaded by react-native-engineer when task involves lists, FlatList, FlashList, LegendList, virtualization, renderItem, scroll performance -->

## Use a Virtualizer for Any Scrollable List
**Impact:** CRITICAL — reduces memory usage and mount time; only visible items rendered

Virtualized lists (LegendList, FlashList) render only the ~10-15 items currently visible. ScrollView with mapped children mounts every item up front — 50 items means 50 components in memory even if none are visible.

**Instead of:**
```tsx
function Feed({ items }: { items: Item[] }) {
  return (
    <ScrollView>
      {items.map((item) => (
        <ItemCard key={item.id} item={item} />
      ))}
    </ScrollView>
  )
}
```

**Use:**
```tsx
import { LegendList } from '@legendapp/list'
// or: import { FlashList } from '@shopify/flash-list'

function Feed({ items }: { items: Item[] }) {
  return (
    <LegendList
      data={items}
      renderItem={({ item }) => <ItemCard item={item} />}
      keyExtractor={(item) => item.id}
      estimatedItemSize={80}
    />
  )
}
```

Applies to any scrollable content: profiles, settings, feeds, search results.

---

## Keep Stable Object References — Transform Inside Items
**Impact:** CRITICAL — virtualization skips re-renders only when references are stable

Mapping or filtering data before passing to a list creates new object references on every render. Virtualization compares by reference to know what changed — new references force full re-renders of all visible items on every keystroke or state update.

**Instead of:**
```tsx
function DomainSearch() {
  const { keyword } = useKeywordState()
  const { data: tlds } = useTlds()

  // creates new objects on every render — reparents the entire list
  const domains = tlds.map((tld) => ({
    domain: `${keyword}.${tld.name}`,
    price: tld.price,
  }))

  return <LegendList data={domains} renderItem={({ item }) => <Row item={item} />} />
}
```

**Use:**
```tsx
function DomainSearch() {
  const { data: tlds } = useTlds()

  return (
    <LegendList
      data={tlds}  // stable references
      renderItem={({ item }) => <DomainItem tld={item} />}
    />
  )
}

function DomainItem({ tld }: { tld: Tld }) {
  // transform inside the item; use a selector for dynamic data
  const domain = useKeywordStore((s) => s.keyword + '.' + tld.name)
  return <Text>{domain}</Text>
}
```

Creating a new sorted array is fine as long as inner object references stay the same:
```tsx
const sorted = tlds.toSorted((a, b) => a.name.localeCompare(b.name))
// new array instance, but inner objects are the same references — OK
```

---

## Avoid Inline Objects in renderItem
**Impact:** HIGH — prevents unnecessary re-renders of memoized list items

Inline objects and inline style objects inside `renderItem` create new references on every render, breaking `memo()` comparison.

**Instead of:**
```tsx
renderItem={({ item }) => (
  <UserRow
    user={{ id: item.id, name: item.name }}  // new object every render
    style={{ backgroundColor: item.isActive ? 'green' : 'gray' }}  // new style object
  />
)}
```

**Use:**
```tsx
// Pass primitives directly — memo() compares them by value
renderItem={({ item }) => (
  <UserRow id={item.id} name={item.name} isActive={item.isActive} />
)}

// Or hoist static style references to module scope
const activeStyle = { backgroundColor: 'green' }
const inactiveStyle = { backgroundColor: 'gray' }

renderItem={({ item }) => (
  <UserRow name={item.name} style={item.isActive ? activeStyle : inactiveStyle} />
)}
```

With React Compiler enabled, these manual optimizations are less critical — but stable references still matter for virtualization.

---

## Pass Primitives to List Items for Effective Memoization
**Impact:** HIGH — enables shallow comparison in memo() to skip re-renders

Primitive props (strings, numbers, booleans) allow `memo()` to work correctly. Object props compare by reference — a new object reference triggers a re-render even if the data is identical.

**Instead of:**
```tsx
const UserRow = memo(function UserRow({ user }: { user: User }) {
  // memo compares user by reference — new user object = re-render
  return <Text>{user.name}</Text>
})
renderItem={({ item }) => <UserRow user={item} />}
```

**Use:**
```tsx
const UserRow = memo(function UserRow({ id, name }: { id: string; name: string }) {
  // memo compares id and name by value
  return <Text>{name}</Text>
})
renderItem={({ item }) => <UserRow id={item.id} name={item.name} />}
```

Pass only the fields the component actually uses.

---

## Hoist Callbacks to the Root — Items Call with ID
**Impact:** HIGH — single stable callback instance vs new closure per item per render

Creating a callback inside `renderItem` generates a new function on every render. Hoist one callback at the list root; items call it with their identifier.

**Instead of:**
```tsx
renderItem={({ item }) => {
  const onPress = () => handlePress(item.id)  // new function every render
  return <Item item={item} onPress={onPress} />
}}
```

**Use:**
```tsx
const onPress = useCallback((id: string) => handlePress(id), [handlePress])

renderItem={({ item }) => (
  <Item item={item} onPress={onPress} />
)}
```

Or handle the press inside the memoized item using the item's stable ID prop.

---

## Keep List Items Lightweight
**Impact:** HIGH — reduces render time per visible item during scroll

Virtualized lists render many items during scroll. Expensive items (queries, heavy computations, multiple Context reads) cause dropped frames.

**Instead of:**
```tsx
function ProductRow({ id }: { id: string }) {
  const { data: product } = useQuery(['product', id], () => fetchProduct(id))
  const theme = useContext(ThemeContext)
  const cart = useContext(CartContext)
  const recs = useMemo(() => computeRecommendations(product), [product])
  return <View>{/* ... */}</View>
}
```

**Use:**
```tsx
// Fetch all data at parent level once; pass pre-computed values as props
function ProductList() {
  const { data: products } = useQuery(['products'], fetchProducts)
  return (
    <LegendList
      data={products}
      renderItem={({ item }) => (
        <ProductRow name={item.name} price={item.price} imageUrl={item.image} />
      )}
    />
  )
}

function ProductRow({ name, price, imageUrl }: Props) {
  // Good: minimal hooks, receives only what it needs
  const inCart = useCartStore((s) => s.items.has(id))  // Zustand selector preferred over Context
  return <View>{/* ... */}</View>
}
```

Guidelines: no queries in items, no expensive computations, prefer Zustand selectors over Context, minimize useState/useEffect.

---

## Use Item Types for Heterogeneous Lists
**Impact:** HIGH — efficient recycling, prevents layout thrashing between different layouts

When a list has different item layouts (headers, messages, images), use `getItemType`. Items with the same type share a recycling pool — a header never gets recycled into an image cell.

**Instead of:**
```tsx
renderItem={({ item }) => {
  if (item.isHeader) return <HeaderItem />
  if (item.imageUrl) return <ImageItem />
  return <MessageItem />
}}
```

**Use:**
```tsx
type FeedItem = HeaderItem | MessageItem | ImageItem  // discriminated union

<LegendList
  data={items}
  keyExtractor={(item) => item.id}
  getItemType={(item) => item.type}
  getEstimatedItemSize={(index, item, itemType) => {
    switch (itemType) {
      case 'header': return 48
      case 'message': return 72
      case 'image': return 300
      default: return 72
    }
  }}
  renderItem={({ item }) => {
    switch (item.type) {
      case 'header': return <SectionHeader title={item.title} />
      case 'message': return <MessageRow text={item.text} />
      case 'image': return <ImageRow url={item.url} />
    }
  }}
  recycleItems
/>
```

TypeScript can narrow the item type in each switch branch automatically.

---

## Use Compressed, Appropriately-Sized Images in Lists
**Impact:** HIGH — reduces memory and prevents scroll jank from oversized images

Loading full-resolution images for small thumbnails consumes excessive memory. Request images sized to their display dimensions (2x for retina).

**Instead of:**
```tsx
// 4000x3000 source loaded for a 100x100 thumbnail
<Image source={{ uri: product.imageUrl }} style={{ width: 100, height: 100 }} />
```

**Use:**
```tsx
import { Image } from 'expo-image'

function ProductItem({ product }: { product: Product }) {
  const thumbnailUrl = `${product.imageUrl}?w=200&h=200&fit=cover`  // 2x retina

  return (
    <Image
      source={{ uri: thumbnailUrl }}
      style={{ width: 100, height: 100 }}
      contentFit="cover"
      recyclingKey={product.id}
    />
  )
}
```

Use `expo-image` for list images — it provides memory-efficient caching and a `recyclingKey` prop for correct behavior in recycled list cells.
