# List Performance Reference
<!-- Loaded by react-native-engineer when task involves lists, FlatList, FlashList, LegendList, virtualization, renderItem, scroll performance -->

## Use a Virtualizer for Any Scrollable List
**Impact:** CRITICAL — only visible items rendered, reduces memory and mount time

**Instead of:**
```tsx
<ScrollView>
  {items.map((item) => <ItemCard key={item.id} item={item} />)}
</ScrollView>
```

**Use:**
```tsx
import { LegendList } from '@legendapp/list'

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

---

## Keep Stable Object References — Transform Inside Items
**Impact:** CRITICAL — virtualization skips re-renders only when references are stable

Mapping/filtering before passing to list creates new references every render, forcing full re-renders on every state update.

**Instead of:**
```tsx
const domains = tlds.map((tld) => ({
  domain: `${keyword}.${tld.name}`,
  price: tld.price,
}))
return <LegendList data={domains} ... />
```

**Use:**
```tsx
<LegendList
  data={tlds}  // stable references
  renderItem={({ item }) => <DomainItem tld={item} />}
/>

function DomainItem({ tld }: { tld: Tld }) {
  const domain = useKeywordStore((s) => s.keyword + '.' + tld.name)
  return <Text>{domain}</Text>
}
```

New sorted arrays are fine if inner object references stay the same: `tlds.toSorted(...)`.

---

## Pass Primitives and Stable References to List Items
**Impact:** HIGH — prevents re-renders of memoized items

Inline objects/styles in `renderItem` create new references every render, breaking `memo()`.

**Instead of:**
```tsx
renderItem={({ item }) => (
  <UserRow
    user={{ id: item.id, name: item.name }}
    style={{ backgroundColor: item.isActive ? 'green' : 'gray' }}
  />
)}
```

**Use:**
```tsx
renderItem={({ item }) => (
  <UserRow id={item.id} name={item.name} isActive={item.isActive} />
)}

// Or hoist static styles to module scope
const activeStyle = { backgroundColor: 'green' }
const inactiveStyle = { backgroundColor: 'gray' }
```

---

## Pass Primitives for Effective Memoization
**Impact:** HIGH — enables shallow comparison in memo()

**Instead of:**
```tsx
const UserRow = memo(function UserRow({ user }: { user: User }) {
  return <Text>{user.name}</Text>
})
renderItem={({ item }) => <UserRow user={item} />}
```

**Use:**
```tsx
const UserRow = memo(function UserRow({ id, name }: { id: string; name: string }) {
  return <Text>{name}</Text>
})
renderItem={({ item }) => <UserRow id={item.id} name={item.name} />}
```

---

## Hoist Callbacks to the Root — Items Call with ID
**Impact:** HIGH — single stable callback vs new closure per item

**Instead of:**
```tsx
renderItem={({ item }) => {
  const onPress = () => handlePress(item.id)
  return <Item item={item} onPress={onPress} />
}}
```

**Use:**
```tsx
const onPress = useCallback((id: string) => handlePress(id), [handlePress])
renderItem={({ item }) => <Item item={item} onPress={onPress} />}
```

---

## Keep List Items Lightweight
**Impact:** HIGH — reduces per-item render time during scroll

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
  const inCart = useCartStore((s) => s.items.has(id))
  return <View>{/* ... */}</View>
}
```

No queries in items, no expensive computations, prefer Zustand selectors over Context.

---

## Use Item Types for Heterogeneous Lists
**Impact:** HIGH — efficient recycling, prevents layout thrashing

```tsx
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

---

## Use Compressed, Appropriately-Sized Images in Lists
**Impact:** HIGH — reduces memory; thumbnails load at display dimensions

**Instead of:**
```tsx
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

Use `expo-image` for list images — memory-efficient caching and `recyclingKey` for recycled cells.
