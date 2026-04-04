# Interactive Components Reference
<!-- Loaded by ui-design-engineer for buttons, inputs, modals, dropdowns, tooltips, toasts, tabs, accordions -->
Keyboard navigation, ARIA, and visible focus states are built into every component below.

## Button
**When to use:** Any clickable action. Use semantic `<button>` elements — they are keyboard-focusable and screen-reader-announced by default.

```tsx
// components/Button.tsx
import { forwardRef } from 'react'

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
type ButtonSize = 'sm' | 'md' | 'lg'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:   'bg-blue-600 text-white hover:bg-blue-700 focus-visible:ring-blue-500',
  secondary: 'bg-gray-100 text-gray-900 hover:bg-gray-200 focus-visible:ring-gray-400',
  ghost:     'bg-transparent text-gray-700 hover:bg-gray-100 focus-visible:ring-gray-400',
  danger:    'bg-red-700 text-white hover:bg-red-800 focus-visible:ring-red-500',
}

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-sm min-h-[36px]',
  md: 'px-4 py-2 text-sm min-h-[44px]',    // 44px meets WCAG touch target
  lg: 'px-6 py-3 text-base min-h-[52px]',
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', loading, disabled, children, className, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        aria-busy={loading}
        className={[
          'inline-flex items-center justify-center gap-2 rounded font-medium',
          'transition-colors duration-150',
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          variantClasses[variant],
          sizeClasses[size],
          className,
        ].filter(Boolean).join(' ')}
        {...props}
      >
        {loading && <span className="sr-only">Loading</span>}
        {children}
      </button>
    )
  }
)
Button.displayName = 'Button'
```

---

## Modal / Dialog
**When to use:** Confirmations, forms, or detail views that require user interaction before continuing. Not for notifications or toasts.

```tsx
// components/Modal.tsx
'use client'
import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  description?: string
  children: React.ReactNode
}

export function Modal({ open, onClose, title, description, children }: ModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null)

  // Lock scroll while open
  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = prev }
  }, [open])

  // Close on Escape
  useEffect(() => {
    if (!open) return
    function handler(e: KeyboardEvent): void {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, onClose])

  // Focus first focusable element when opened
  useEffect(() => {
    if (!open || !dialogRef.current) return
    const focusable = dialogRef.current.querySelector<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )
    focusable?.focus()
  }, [open])

  if (!open) return null

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      aria-hidden={!open}
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Dialog */}
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        aria-describedby={description ? 'modal-description' : undefined}
        className="relative z-10 w-full max-w-md rounded-xl bg-white p-6 shadow-xl"
      >
        <h2 id="modal-title" className="text-lg font-semibold text-gray-900">
          {title}
        </h2>
        {description && (
          <p id="modal-description" className="mt-1 text-sm text-gray-600">
            {description}
          </p>
        )}
        <div className="mt-4">{children}</div>
        <button
          onClick={onClose}
          aria-label="Close dialog"
          className="absolute right-4 top-4 rounded p-1 text-gray-400 hover:text-gray-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        >
          <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
          </svg>
        </button>
      </div>
    </div>,
    document.body
  )
}
```

---

## Dropdown Menu
**When to use:** Action menus, context menus, select-like pickers with complex items. Not for simple option selection — use a `<select>` for that.

```tsx
// components/DropdownMenu.tsx
'use client'
import { useState, useRef, useEffect } from 'react'

interface DropdownItem {
  id: string
  label: string
  action: () => void
  disabled?: boolean
}

interface DropdownMenuProps {
  trigger: React.ReactNode
  items: DropdownItem[]
  align?: 'left' | 'right'
}

export function DropdownMenu({ trigger, items, align = 'left' }: DropdownMenuProps) {
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLUListElement>(null)
  const [focusedIndex, setFocusedIndex] = useState(0)

  // Close on outside click
  useEffect(() => {
    if (!open) return
    function handler(e: MouseEvent): void {
      if (!menuRef.current?.contains(e.target as Node) &&
          !triggerRef.current?.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  function handleTriggerKeyDown(e: React.KeyboardEvent): void {
    if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      setOpen(true)
      setFocusedIndex(0)
    }
  }

  function handleMenuKeyDown(e: React.KeyboardEvent): void {
    const enabledItems = items.filter(i => !i.disabled)
    switch (e.key) {
      case 'ArrowDown': {
        e.preventDefault()
        setFocusedIndex(i => (i + 1) % enabledItems.length)
        break
      }
      case 'ArrowUp': {
        e.preventDefault()
        setFocusedIndex(i => (i - 1 + enabledItems.length) % enabledItems.length)
        break
      }
      case 'Escape': {
        setOpen(false)
        triggerRef.current?.focus()
        break
      }
    }
  }

  return (
    <div className="relative inline-block">
      <button
        ref={triggerRef}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen(o => !o)}
        onKeyDown={handleTriggerKeyDown}
        className="focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
      >
        {trigger}
      </button>

      {open && (
        <ul
          ref={menuRef}
          role="menu"
          onKeyDown={handleMenuKeyDown}
          className={`absolute z-20 mt-1 min-w-[10rem] rounded-lg border border-gray-200 bg-white py-1 shadow-lg ${
            align === 'right' ? 'right-0' : 'left-0'
          }`}
        >
          {items.map((item, index) => (
            <li key={item.id} role="none">
              <button
                role="menuitem"
                disabled={item.disabled}
                tabIndex={index === focusedIndex ? 0 : -1}
                onClick={() => { item.action(); setOpen(false) }}
                className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 focus:bg-gray-50 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {item.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
```

---

## Tabs
**When to use:** Switching between related content panels. Do not use tabs for navigation between pages — use links.

```tsx
// components/Tabs.tsx
'use client'
import { useState } from 'react'

interface Tab {
  id: string
  label: string
  content: React.ReactNode
}

export function Tabs({ tabs }: { tabs: Tab[] }) {
  const [activeId, setActiveId] = useState(tabs[0].id)

  return (
    <div>
      {/* Tab list */}
      <div role="tablist" className="flex border-b border-gray-200">
        {tabs.map(tab => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={tab.id === activeId}
            aria-controls={`panel-${tab.id}`}
            id={`tab-${tab.id}`}
            onClick={() => setActiveId(tab.id)}
            className={[
              'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
              'focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-inset',
              tab.id === activeId
                ? 'border-blue-600 text-blue-700'
                : 'border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300',
            ].join(' ')}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab panels */}
      {tabs.map(tab => (
        <div
          key={tab.id}
          role="tabpanel"
          id={`panel-${tab.id}`}
          aria-labelledby={`tab-${tab.id}`}
          hidden={tab.id !== activeId}
          tabIndex={0}
          className="py-4 focus:outline-none"
        >
          {tab.content}
        </div>
      ))}
    </div>
  )
}
```

---

## Accordion
**When to use:** FAQ sections, expandable content blocks, settings panels. Use when you want to show one or more sections at a time.

```tsx
// components/Accordion.tsx
'use client'
import { useState } from 'react'

interface AccordionItem {
  id: string
  question: string
  answer: React.ReactNode
}

export function Accordion({ items }: { items: AccordionItem[] }) {
  const [openIds, setOpenIds] = useState<Set<string>>(new Set())

  function toggle(id: string): void {
    setOpenIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <dl className="divide-y divide-gray-200 border-t border-b border-gray-200">
      {items.map(item => {
        const isOpen = openIds.has(item.id)
        return (
          <div key={item.id}>
            <dt>
              <button
                aria-expanded={isOpen}
                aria-controls={`answer-${item.id}`}
                onClick={() => toggle(item.id)}
                className="flex w-full items-center justify-between px-0 py-4 text-left font-medium text-gray-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-inset"
              >
                {item.question}
                <svg
                  className={`h-5 w-5 flex-shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`}
                  viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"
                >
                  <path fillRule="evenodd" d="M5.22 8.22a.75.75 0 011.06 0L10 11.94l3.72-3.72a.75.75 0 111.06 1.06l-4.25 4.25a.75.75 0 01-1.06 0L5.22 9.28a.75.75 0 010-1.06z" />
                </svg>
              </button>
            </dt>
            <dd
              id={`answer-${item.id}`}
              className={isOpen ? 'pb-4' : 'hidden'}
            >
              <div className="text-gray-600">{item.answer}</div>
            </dd>
          </div>
        )
      })}
    </dl>
  )
}
```

---

## Toast Notifications
**When to use:** Brief, non-blocking feedback for completed actions (saved, deleted, error). Auto-dismiss after 4–5 seconds.

```tsx
// components/Toast.tsx
'use client'
import { useEffect } from 'react'

type ToastType = 'success' | 'error' | 'info'

interface ToastProps {
  message: string
  type?: ToastType
  onDismiss: () => void
  duration?: number
}

const typeClasses: Record<ToastType, string> = {
  success: 'bg-green-700 text-white',
  error:   'bg-red-700 text-white',
  info:    'bg-gray-800 text-white',
}

export function Toast({ message, type = 'info', onDismiss, duration = 4000 }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, duration)
    return () => clearTimeout(timer)
  }, [onDismiss, duration])

  return (
    // role="status" announces to screen readers without interrupting
    <div
      role="status"
      aria-live="polite"
      aria-atomic="true"
      className={`flex items-center gap-3 rounded-lg px-4 py-3 shadow-lg ${typeClasses[type]}`}
    >
      <span className="text-sm font-medium">{message}</span>
      <button
        onClick={onDismiss}
        aria-label="Dismiss notification"
        className="ml-auto rounded p-0.5 opacity-70 hover:opacity-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-white"
      >
        <svg className="h-4 w-4" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
          <path d="M3.72 3.72a.75.75 0 011.06 0L8 6.94l3.22-3.22a.75.75 0 111.06 1.06L9.06 8l3.22 3.22a.75.75 0 11-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 01-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 010-1.06z" />
        </svg>
      </button>
    </div>
  )
}
```

---

## Form Input with Validation States
**When to use:** Every form field. Validation state must be conveyed through more than just color (for colorblind users).

```tsx
type FieldState = 'default' | 'error' | 'success'

interface FormFieldProps {
  id: string
  label: string
  state?: FieldState
  message?: string  // error or success message
  required?: boolean
  children: React.ReactElement<{ id: string; 'aria-describedby'?: string; 'aria-invalid'?: boolean }>
}

export function FormField({ id, label, state = 'default', message, required, children }: FormFieldProps) {
  const messageId = `${id}-message`

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium text-gray-700">
        {label}
        {required && <span aria-hidden="true" className="ml-1 text-red-600">*</span>}
        {required && <span className="sr-only">(required)</span>}
      </label>

      {/* Inject aria attributes into the child input */}
      {React.cloneElement(children, {
        id,
        'aria-describedby': message ? messageId : undefined,
        'aria-invalid': state === 'error' ? true : undefined,
      })}

      {message && (
        <p
          id={messageId}
          className={`text-sm ${state === 'error' ? 'text-red-700' : 'text-green-700'}`}
          role={state === 'error' ? 'alert' : 'status'}
        >
          {state === 'error' ? '! ' : '✓ '}
          {message}
        </p>
      )}
    </div>
  )
}
```
