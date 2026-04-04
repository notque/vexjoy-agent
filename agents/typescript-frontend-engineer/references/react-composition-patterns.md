# React Composition Patterns Reference
<!-- Loaded by typescript-frontend-engineer when task involves component architecture, compound components, context, providers, or prop design -->

## Compound Components with Shared Context
**Impact:** HIGH — enables flexible composition without prop drilling or boolean proliferation

Compound components let consumers arrange subcomponents freely, sharing state through context rather than props. The parent component never needs to anticipate every layout variation — consumers compose exactly what they need.

**Instead of:**
```tsx
// Each new variation requires adding boolean props
function Composer({
  onSubmit,
  isThread,
  channelId,
  isDMThread,
  dmId,
  isEditing,
  isForwarding,
}: Props) {
  return (
    <form>
      <Header />
      <Input />
      {isDMThread ? (
        <AlsoSendToDMField id={dmId} />
      ) : isThread ? (
        <AlsoSendToChannelField id={channelId} />
      ) : null}
      {isEditing ? <EditActions /> : isForwarding ? <ForwardActions /> : <DefaultActions />}
      <Footer onSubmit={onSubmit} />
    </form>
  )
}
```

**Use:**
```tsx
const ComposerContext = createContext<ComposerContextValue | null>(null)

function ComposerProvider({ children, state, actions, meta }: ProviderProps) {
  return (
    <ComposerContext value={{ state, actions, meta }}>
      {children}
    </ComposerContext>
  )
}

function ComposerFrame({ children }: { children: React.ReactNode }) {
  return <form>{children}</form>
}

function ComposerInput() {
  const { state, actions: { update }, meta: { inputRef } } = use(ComposerContext)
  return (
    <input
      ref={inputRef}
      value={state.input}
      onChange={e => update(s => ({ ...s, input: e.target.value }))}
    />
  )
}

function ComposerSubmit() {
  const { actions: { submit } } = use(ComposerContext)
  return <button onClick={submit}>Send</button>
}

// Exported as a compound component namespace
export const Composer = {
  Provider: ComposerProvider,
  Frame: ComposerFrame,
  Input: ComposerInput,
  Submit: ComposerSubmit,
  Header: ComposerHeader,
  Footer: ComposerFooter,
}
```

**Usage — each variant composes exactly what it needs:**
```tsx
// Thread composer adds one extra field
function ThreadComposer({ channelId }: { channelId: string }) {
  return (
    <Composer.Provider state={state} actions={actions} meta={meta}>
      <Composer.Frame>
        <Composer.Header />
        <Composer.Input />
        <AlsoSendToChannelField id={channelId} />
        <Composer.Footer>
          <Composer.Submit />
        </Composer.Footer>
      </Composer.Frame>
    </Composer.Provider>
  )
}

// Edit composer swaps the footer actions entirely
function EditComposer() {
  return (
    <Composer.Provider state={state} actions={actions} meta={meta}>
      <Composer.Frame>
        <Composer.Input />
        <Composer.Footer>
          <CancelEdit />
          <SaveEdit />
        </Composer.Footer>
      </Composer.Frame>
    </Composer.Provider>
  )
}
```

---

## Lift State into Provider Components
**Impact:** HIGH — enables state sharing outside visual component boundaries

State trapped inside a component can only be passed down through props. Lifting state into a provider lets sibling components outside the main UI tree access and mutate the same state without prop drilling or effect-based synchronization.

**Instead of:**
```tsx
// State trapped inside — sibling components can't reach submit or read input
function ForwardMessageDialog() {
  return (
    <Dialog>
      <ForwardMessageComposer />
      <MessagePreview />     {/* needs composer state — can't get it */}
      <DialogActions>
        <ForwardButton />    {/* needs submit — can't get it */}
      </DialogActions>
    </Dialog>
  )
}
```

**Instead of (anti-patterns for accessing trapped state):**
```tsx
// Effect sync — fires on every change, risks tearing
function ForwardMessageComposer({ onInputChange }: { onInputChange: (v: string) => void }) {
  const [state, setState] = useState(initialState)
  useEffect(() => { onInputChange(state.input) }, [state.input])
}

// Ref reading — stale if read before setState commits
function ForwardMessageDialog() {
  const stateRef = useRef(null)
  return <ForwardButton onPress={() => submit(stateRef.current)} />
}
```

**Use:**
```tsx
function ForwardMessageProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState(initialState)
  const forwardMessage = useForwardMessage()
  const inputRef = useRef(null)

  return (
    <Composer.Provider
      state={state}
      actions={{ update: setState, submit: forwardMessage }}
      meta={{ inputRef }}
    >
      {children}
    </Composer.Provider>
  )
}

function ForwardMessageDialog() {
  return (
    <ForwardMessageProvider>
      <Dialog>
        <Composer.Frame>
          <Composer.Input />
        </Composer.Frame>
        <MessagePreview />
        <DialogActions>
          <ForwardButton />
        </DialogActions>
      </Dialog>
    </ForwardMessageProvider>
  )
}

// Lives outside Composer.Frame — still has full access
function ForwardButton() {
  const { actions: { submit } } = use(Composer.Context)
  return <button onClick={submit}>Forward</button>
}

function MessagePreview() {
  const { state } = use(Composer.Context)
  return <Preview message={state.input} />
}
```

Components access shared state based on provider ancestry, not visual nesting. The provider boundary is what matters.

---

## Children over Render Props
**Impact:** MEDIUM — cleaner composition, more readable call sites

`children` composes naturally in JSX. Render props require callers to understand callback signatures and produce harder-to-read nesting. Use render props only when the parent needs to pass data back to the caller.

**Instead of:**
```tsx
function Composer({
  renderHeader,
  renderFooter,
  renderActions,
}: {
  renderHeader?: () => React.ReactNode
  renderFooter?: () => React.ReactNode
  renderActions?: () => React.ReactNode
}) {
  return (
    <form>
      {renderHeader?.()}
      <Input />
      {renderFooter ? renderFooter() : <DefaultFooter />}
      {renderActions?.()}
    </form>
  )
}

// Call site is awkward
<Composer
  renderHeader={() => <CustomHeader />}
  renderFooter={() => <><Formatting /><Emojis /></>}
  renderActions={() => <SubmitButton />}
/>
```

**Use:**
```tsx
function ComposerFrame({ children }: { children: React.ReactNode }) {
  return <form>{children}</form>
}

function ComposerFooter({ children }: { children: React.ReactNode }) {
  return <footer className="flex">{children}</footer>
}

// Call site reads like the resulting DOM
<Composer.Frame>
  <CustomHeader />
  <Composer.Input />
  <Composer.Footer>
    <Composer.Formatting />
    <Composer.Emojis />
    <SubmitButton />
  </Composer.Footer>
</Composer.Frame>
```

**When render props are appropriate:** when the parent needs to pass data or state back to the caller — e.g., `<List renderItem={({ item, index }) => <Item item={item} />} />`.

---

## Explicit Variants over Boolean Props
**Impact:** CRITICAL — prevents unmaintainable exponential state combinations

Each boolean prop doubles the number of possible component states. Two booleans = 4 states; five booleans = 32. Create explicit named variants instead — each is self-documenting and contains only the pieces it needs.

**Instead of:**
```tsx
// What does this render? Requires reading the entire component implementation
<Composer
  isThread
  isEditing={false}
  channelId="abc"
  showAttachments
  showFormatting={false}
/>
```

**Use:**
```tsx
// Immediately clear — no implementation knowledge required
<ThreadComposer channelId="abc" />
<EditMessageComposer messageId="xyz" />
<ForwardMessageComposer messageId="123" />
```

**Implementation — each variant is explicit and self-contained:**
```tsx
function ThreadComposer({ channelId }: { channelId: string }) {
  return (
    <ThreadProvider channelId={channelId}>
      <Composer.Frame>
        <Composer.Input />
        <AlsoSendToChannelField channelId={channelId} />
        <Composer.Footer>
          <Composer.Formatting />
          <Composer.Submit />
        </Composer.Footer>
      </Composer.Frame>
    </ThreadProvider>
  )
}

function EditMessageComposer({ messageId }: { messageId: string }) {
  return (
    <EditMessageProvider messageId={messageId}>
      <Composer.Frame>
        <Composer.Input />
        <Composer.Footer>
          <Composer.Formatting />
          <CancelEdit />
          <SaveEdit />
        </Composer.Footer>
      </Composer.Frame>
    </EditMessageProvider>
  )
}
```

Each variant documents exactly what it renders, what provider it uses, and what actions are available — no boolean combinations to reason about.

---

## Context Interface Pattern (state / actions / meta)
**Impact:** HIGH — enables dependency-injectable state across completely different implementations

Define a generic interface for context with three parts: `state` (the data), `actions` (the mutations), and `meta` (refs and non-serializable values). This interface is a contract — any provider can implement it, so the same UI components work with local state, global state, or server-synced state interchangeably.

**Use:**
```tsx
interface ComposerState {
  input: string
  attachments: Attachment[]
  isSubmitting: boolean
}

interface ComposerActions {
  update: (updater: (state: ComposerState) => ComposerState) => void
  submit: () => void
}

interface ComposerMeta {
  inputRef: React.RefObject<HTMLInputElement>
}

interface ComposerContextValue {
  state: ComposerState
  actions: ComposerActions
  meta: ComposerMeta
}

const ComposerContext = createContext<ComposerContextValue | null>(null)
```

**UI components depend on the interface, not the implementation:**
```tsx
function ComposerInput() {
  const { state, actions: { update }, meta } = use(ComposerContext)
  // Works with ANY provider that implements ComposerContextValue
  return (
    <input
      ref={meta.inputRef}
      value={state.input}
      onChange={e => update(s => ({ ...s, input: e.target.value }))}
    />
  )
}
```

**Multiple providers implement the same interface:**
```tsx
// Local state for ephemeral forms
function ForwardMessageProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState(initialState)
  const submit = useForwardMessage()
  const inputRef = useRef<HTMLInputElement>(null)

  return (
    <ComposerContext value={{ state, actions: { update: setState, submit }, meta: { inputRef } }}>
      {children}
    </ComposerContext>
  )
}

// Global synced state for persistent channels
function ChannelProvider({ channelId, children }: { channelId: string; children: React.ReactNode }) {
  const { state, update, submit } = useGlobalChannel(channelId)
  const inputRef = useRef<HTMLInputElement>(null)

  return (
    <ComposerContext value={{ state, actions: { update, submit }, meta: { inputRef } }}>
      {children}
    </ComposerContext>
  )
}
```

Swap the provider; the UI components are unchanged.

---

## Decouple State Management from UI
**Impact:** MEDIUM — enables swapping state implementations without touching UI components

The provider component is the only place that knows how state is managed. UI components consume the context interface — they don't know or care whether state comes from `useState`, Zustand, or a server sync.

**Instead of:**
```tsx
// UI component coupled to a specific state hook
function ChannelComposer({ channelId }: { channelId: string }) {
  const state = useGlobalChannelState(channelId)
  const { submit, updateInput } = useChannelSync(channelId)

  return (
    <Composer.Frame>
      <Composer.Input value={state.input} onChange={updateInput} />
      <Composer.Submit onPress={submit} />
    </Composer.Frame>
  )
}
```

**Use:**
```tsx
// Provider isolates all state management details
function ChannelProvider({ channelId, children }: { channelId: string; children: React.ReactNode }) {
  const { state, update, submit } = useGlobalChannel(channelId)
  const inputRef = useRef<HTMLInputElement>(null)

  return (
    <Composer.Provider state={state} actions={{ update, submit }} meta={{ inputRef }}>
      {children}
    </Composer.Provider>
  )
}

// UI component depends only on the context interface
function ChannelComposer() {
  return (
    <Composer.Frame>
      <Composer.Header />
      <Composer.Input />
      <Composer.Footer>
        <Composer.Submit />
      </Composer.Footer>
    </Composer.Frame>
  )
}

// Usage: provider wraps UI
function Channel({ channelId }: { channelId: string }) {
  return (
    <ChannelProvider channelId={channelId}>
      <ChannelComposer />
    </ChannelProvider>
  )
}
```

---

## React 19: ref as Prop (No forwardRef)
**Impact:** MEDIUM — cleaner component definitions, removes deprecated API

In React 19, `ref` is a regular prop. `forwardRef` is deprecated and will be removed in a future version. Accept `ref` directly in the function signature.

**Instead of:**
```tsx
const ComposerInput = forwardRef<HTMLInputElement, Props>((props, ref) => {
  return <input ref={ref} {...props} />
})
```

**Use:**
```tsx
function ComposerInput({ ref, ...props }: Props & { ref?: React.Ref<HTMLInputElement> }) {
  return <input ref={ref} {...props} />
}
```

Also applies to `useContext` — replace with `use()` in React 19, which can be called conditionally:

```tsx
// React 18
const value = useContext(ComposerContext)

// React 19
const value = use(ComposerContext)
```
