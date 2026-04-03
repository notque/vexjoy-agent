# Component Library: Display Components Reference
<!-- Loaded by ui-design-engineer when task involves cards, tables, data display, badges, avatars, progress indicators, or alerts -->

Accessible display components surface information clearly with proper semantic markup, ARIA roles, and visible structure. Every component here conveys meaning through structure and text, not color alone.

## Card
**When to use:** Grouping related content visually. Cards surface scannable summaries and can link to detail views.

```tsx
// components/Card.tsx
interface CardProps {
  title: string
  description?: string
  footer?: React.ReactNode
  children?: React.ReactNode
  href?: string
}

export function Card({ title, description, footer, children, href }: CardProps) {
  const content = (
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <h3 className="text-base font-semibold text-gray-900">{title}</h3>
      {description && (
        <p className="mt-1 text-sm text-gray-600">{description}</p>
      )}
      {children && <div className="mt-4">{children}</div>}
      {footer && (
        <div className="mt-4 border-t border-gray-100 pt-4">{footer}</div>
      )}
    </div>
  )

  if (href) {
    return (
      <a
        href={href}
        className="block rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 hover:shadow-md transition-shadow"
      >
        {content}
      </a>
    )
  }

  return content
}
```

---

## Data Table
**When to use:** Structured tabular data with headers, sorting, and optional pagination. Use `<table>` for data with rows and columns — never divs.

```tsx
// components/DataTable.tsx
interface Column<T> {
  key: keyof T
  label: string
  sortable?: boolean
  render?: (value: T[keyof T], row: T) => React.ReactNode
}

interface DataTableProps<T extends { id: string }> {
  columns: Column<T>[]
  rows: T[]
  caption?: string
}

export function DataTable<T extends { id: string }>({ columns, rows, caption }: DataTableProps<T>) {
  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="min-w-full divide-y divide-gray-200">
        {caption && (
          <caption className="sr-only">{caption}</caption>
        )}
        <thead className="bg-gray-50">
          <tr>
            {columns.map(col => (
              <th
                key={String(col.key)}
                scope="col"
                className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-gray-500"
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white">
          {rows.map(row => (
            <tr key={row.id} className="hover:bg-gray-50">
              {columns.map(col => (
                <td
                  key={String(col.key)}
                  className="whitespace-nowrap px-4 py-3 text-sm text-gray-700"
                >
                  {col.render
                    ? col.render(row[col.key], row)
                    : String(row[col.key] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

---

## Badge
**When to use:** Status labels, category tags, count indicators. Use color and a label — never color alone.

```tsx
// components/Badge.tsx
type BadgeVariant = 'default' | 'success' | 'warning' | 'error' | 'info'

interface BadgeProps {
  label: string
  variant?: BadgeVariant
}

const variantClasses: Record<BadgeVariant, string> = {
  default: 'bg-gray-100 text-gray-700',
  success: 'bg-green-100 text-green-800',
  warning: 'bg-yellow-100 text-yellow-800',
  error:   'bg-red-100 text-red-800',
  info:    'bg-blue-100 text-blue-800',
}

export function Badge({ label, variant = 'default' }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${variantClasses[variant]}`}
    >
      {label}
    </span>
  )
}
```

---

## Avatar
**When to use:** User or entity representation. Always provide alt text or aria-label for screen readers. Show initials fallback when image fails.

```tsx
// components/Avatar.tsx
interface AvatarProps {
  src?: string
  name: string
  size?: 'sm' | 'md' | 'lg'
}

const sizeClasses = {
  sm: 'h-8 w-8 text-xs',
  md: 'h-10 w-10 text-sm',
  lg: 'h-12 w-12 text-base',
}

function getInitials(name: string): string {
  return name
    .split(' ')
    .slice(0, 2)
    .map(part => part[0] ?? '')
    .join('')
    .toUpperCase()
}

export function Avatar({ src, name, size = 'md' }: AvatarProps) {
  if (src) {
    return (
      <img
        src={src}
        alt={name}
        className={`${sizeClasses[size]} rounded-full object-cover`}
      />
    )
  }

  return (
    <span
      aria-label={name}
      className={`${sizeClasses[size]} inline-flex items-center justify-center rounded-full bg-gray-200 font-medium text-gray-700`}
    >
      {getInitials(name)}
    </span>
  )
}
```

---

## Progress Indicator
**When to use:** File uploads, multi-step forms, loading sequences where progress can be quantified. Use `role="progressbar"` with `aria-valuenow`, `aria-valuemin`, `aria-valuemax`.

```tsx
// components/ProgressBar.tsx
interface ProgressBarProps {
  value: number        // 0–100
  label: string        // describes what is progressing
  showLabel?: boolean
}

export function ProgressBar({ value, label, showLabel = true }: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, value))

  return (
    <div>
      {showLabel && (
        <div className="mb-1 flex justify-between text-sm text-gray-700">
          <span>{label}</span>
          <span aria-hidden="true">{clamped}%</span>
        </div>
      )}
      <div
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
        className="h-2 w-full overflow-hidden rounded-full bg-gray-200"
      >
        <div
          className="h-full rounded-full bg-blue-600 transition-all duration-300"
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  )
}
```

---

## Alert
**When to use:** Inline feedback — validation errors, warnings, or success confirmations that are part of page content (not transient toasts). Use `role="alert"` for errors (interrupts screen readers) and `role="status"` for non-urgent status updates.

```tsx
// components/Alert.tsx
type AlertVariant = 'info' | 'success' | 'warning' | 'error'

interface AlertProps {
  variant: AlertVariant
  title?: string
  message: string
}

const variantConfig: Record<AlertVariant, { classes: string; role: 'alert' | 'status' }> = {
  info:    { classes: 'bg-blue-50 border-blue-200 text-blue-800',   role: 'status' },
  success: { classes: 'bg-green-50 border-green-200 text-green-800', role: 'status' },
  warning: { classes: 'bg-yellow-50 border-yellow-200 text-yellow-800', role: 'status' },
  error:   { classes: 'bg-red-50 border-red-200 text-red-800',      role: 'alert' },
}

export function Alert({ variant, title, message }: AlertProps) {
  const { classes, role } = variantConfig[variant]

  return (
    <div
      role={role}
      className={`rounded-lg border p-4 ${classes}`}
    >
      {title && (
        <p className="mb-1 font-medium">{title}</p>
      )}
      <p className="text-sm">{message}</p>
    </div>
  )
}
```
