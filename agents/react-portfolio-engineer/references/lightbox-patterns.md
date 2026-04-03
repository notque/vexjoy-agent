# Lightbox Patterns Reference
<!-- Loaded by react-portfolio-engineer when task involves lightbox, image viewer, or modal gallery -->

Lightboxes unlock full-resolution artwork viewing without leaving the page — keeping visitors in the experience rather than navigating away to raw image URLs.

## Keyboard Navigation
**When to use:** Every lightbox. Keyboard nav is both an accessibility requirement and a power-user feature.

Attach a single `keydown` listener on mount, remove it on unmount. Handle `Escape` (close), `ArrowLeft`/`ArrowRight` (navigate), and `Home`/`End` (first/last image).

```tsx
// hooks/useLightboxKeyboard.ts
import { useEffect } from 'react'

interface UseLightboxKeyboardOptions {
  onClose: () => void
  onPrev: () => void
  onNext: () => void
  onFirst?: () => void
  onLast?: () => void
}

export function useLightboxKeyboard({
  onClose,
  onPrev,
  onNext,
  onFirst,
  onLast,
}: UseLightboxKeyboardOptions): void {
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent): void {
      switch (e.key) {
        case 'Escape':     onClose(); break
        case 'ArrowLeft':  onPrev();  break
        case 'ArrowRight': onNext();  break
        case 'Home':       onFirst?.(); break
        case 'End':        onLast?.(); break
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose, onPrev, onNext, onFirst, onLast])
}
```

**Instead of:** Registering keyboard handlers without cleanup — causes duplicate listeners after re-renders.

---

## Focus Trap
**When to use:** Any time a lightbox or modal overlays the page. Focus must not escape to background content while the overlay is open.

```tsx
// hooks/useFocusTrap.ts
import { useEffect, useRef } from 'react'

export function useFocusTrap(active: boolean): React.RefObject<HTMLDivElement> {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!active || !containerRef.current) return

    const focusable = containerRef.current.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )
    const first = focusable[0]
    const last = focusable[focusable.length - 1]

    first?.focus()

    function handleKeyDown(e: KeyboardEvent): void {
      if (e.key !== 'Tab') return
      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault()
          last?.focus()
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault()
          first?.focus()
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [active])

  return containerRef
}
```

Usage in lightbox:

```tsx
export function Lightbox({ images, activeIndex, onClose }: LightboxProps) {
  const containerRef = useFocusTrap(true)

  return (
    <div
      ref={containerRef}
      role="dialog"
      aria-modal="true"
      aria-label={`Image viewer: ${images[activeIndex].alt}`}
      className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center"
    >
      <button onClick={onClose} aria-label="Close image viewer">X</button>
    </div>
  )
}
```

---

## Scroll Lock
**When to use:** When the lightbox is open, prevent the background page from scrolling under the overlay.

```tsx
// hooks/useScrollLock.ts
import { useEffect } from 'react'

export function useScrollLock(locked: boolean): void {
  useEffect(() => {
    if (!locked) return

    const originalOverflow = document.body.style.overflow
    const originalPaddingRight = document.body.style.paddingRight

    // Compensate for scrollbar width to prevent layout shift
    const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth
    document.body.style.overflow = 'hidden'
    document.body.style.paddingRight = `${scrollbarWidth}px`

    return () => {
      document.body.style.overflow = originalOverflow
      document.body.style.paddingRight = originalPaddingRight
    }
  }, [locked])
}
```

---

## Lazy Image Loading in Lightbox
**When to use:** Galleries with more than 10 images. Load the current image eagerly, preload adjacent images, defer the rest.

```tsx
// components/Lightbox.tsx
'use client'
import Image from 'next/image'
import { useLightboxKeyboard } from '@/hooks/useLightboxKeyboard'
import { useFocusTrap } from '@/hooks/useFocusTrap'
import { useScrollLock } from '@/hooks/useScrollLock'

interface LightboxImage {
  src: string
  alt: string
  width: number
  height: number
}

interface LightboxProps {
  images: LightboxImage[]
  activeIndex: number
  onClose: () => void
  onNext: () => void
  onPrev: () => void
}

export function Lightbox({ images, activeIndex, onClose, onNext, onPrev }: LightboxProps) {
  const containerRef = useFocusTrap(true)
  useScrollLock(true)
  useLightboxKeyboard({ onClose, onPrev, onNext })

  const current = images[activeIndex]
  const prev = images[activeIndex - 1]
  const next = images[activeIndex + 1]

  return (
    <div
      ref={containerRef}
      role="dialog"
      aria-modal="true"
      aria-label={`Viewing: ${current.alt}`}
      className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center"
      onClick={onClose}
    >
      <div
        className="relative max-w-5xl w-full mx-4"
        onClick={e => e.stopPropagation()}
      >
        <Image
          src={current.src}
          alt={current.alt}
          width={current.width}
          height={current.height}
          priority
          className="w-full h-auto object-contain max-h-[85vh]"
        />
      </div>

      {/* Preload adjacent images */}
      {prev && (
        <Image src={prev.src} alt="" width={1} height={1} className="sr-only" loading="eager" />
      )}
      {next && (
        <Image src={next.src} alt="" width={1} height={1} className="sr-only" loading="eager" />
      )}

      <button
        onClick={onPrev}
        disabled={activeIndex === 0}
        aria-label="Previous image"
        className="absolute left-4 top-1/2 -translate-y-1/2 text-white text-4xl disabled:opacity-30"
      >
        Prev
      </button>
      <button
        onClick={onNext}
        disabled={activeIndex === images.length - 1}
        aria-label="Next image"
        className="absolute right-4 top-1/2 -translate-y-1/2 text-white text-4xl disabled:opacity-30"
      >
        Next
      </button>
      <button
        onClick={onClose}
        aria-label="Close image viewer"
        className="absolute top-4 right-4 text-white text-2xl"
      >
        Close
      </button>

      <p className="absolute bottom-4 left-1/2 -translate-x-1/2 text-white text-sm">
        {activeIndex + 1} / {images.length}
      </p>
    </div>
  )
}
```

---

## Swipe Gestures (Mobile)
**When to use:** Lightboxes on touch devices. Horizontal swipe navigates between images.

```tsx
// hooks/useSwipeGesture.ts
import { useRef } from 'react'

interface SwipeHandlers {
  onTouchStart: (e: React.TouchEvent) => void
  onTouchEnd: (e: React.TouchEvent) => void
}

export function useSwipeGesture(
  onSwipeLeft: () => void,
  onSwipeRight: () => void,
  threshold = 50
): SwipeHandlers {
  const startX = useRef<number>(0)

  return {
    onTouchStart(e: React.TouchEvent): void {
      startX.current = e.touches[0].clientX
    },
    onTouchEnd(e: React.TouchEvent): void {
      const delta = e.changedTouches[0].clientX - startX.current
      if (Math.abs(delta) < threshold) return
      if (delta < 0) onSwipeLeft()
      else onSwipeRight()
    },
  }
}
```

Attach to the lightbox container:

```tsx
const swipeHandlers = useSwipeGesture(onNext, onPrev)

<div {...swipeHandlers} className="fixed inset-0 ...">
```

---

## Gallery Grid Layout
**When to use:** Portfolio index page — uniform grid with consistent aspect ratios for clean visual rhythm.

```tsx
// components/GalleryGrid.tsx
import Image from 'next/image'

interface GalleryImage {
  id: string
  src: string
  alt: string
  width: number
  height: number
}

interface GalleryGridProps {
  images: GalleryImage[]
  onImageClick: (index: number) => void
}

export function GalleryGrid({ images, onImageClick }: GalleryGridProps) {
  return (
    <ul
      role="list"
      className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2"
      aria-label="Image gallery"
    >
      {images.map((image, index) => (
        <li key={image.id}>
          <button
            onClick={() => onImageClick(index)}
            className="relative block w-full aspect-square overflow-hidden rounded focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            aria-label={`View full size: ${image.alt}`}
          >
            <Image
              src={image.src}
              alt={image.alt}
              fill
              className="object-cover transition-transform hover:scale-105"
              sizes="(max-width: 768px) 50vw, (max-width: 1200px) 33vw, 25vw"
              loading={index < 4 ? 'eager' : 'lazy'}
            />
          </button>
        </li>
      ))}
    </ul>
  )
}
```

**Instead of:** Using `<div onClick>` for gallery items — breaks keyboard navigation and screen reader access.

---

## Returning Focus on Close
**When to use:** Always. When the lightbox closes, return focus to the element that opened it.

```tsx
const [activeIndex, setActiveIndex] = useState<number | null>(null)
const triggerRefs = useRef<(HTMLButtonElement | null)[]>([])

function openLightbox(index: number): void {
  setActiveIndex(index)
}

function closeLightbox(): void {
  const trigger = triggerRefs.current[activeIndex!]
  setActiveIndex(null)
  requestAnimationFrame(() => trigger?.focus())
}
```
