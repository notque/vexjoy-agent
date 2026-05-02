# Lightbox Patterns Reference
<!-- Loaded by react-portfolio-engineer when task involves lightbox, image viewer, or modal gallery -->

## Keyboard Navigation

Every lightbox needs keyboard nav (accessibility + power-user feature). Handle Escape, ArrowLeft/Right, Home/End.

```tsx
// hooks/useLightboxKeyboard.ts
import { useEffect } from 'react'

export function useLightboxKeyboard({ onClose, onPrev, onNext, onFirst, onLast }) {
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
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

---

## Focus Trap

Focus must not escape to background content while overlay is open.

```tsx
// hooks/useFocusTrap.ts
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

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key !== 'Tab') return
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus() }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus() }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [active])

  return containerRef
}
```

---

## Scroll Lock

Prevent background scrolling. Compensate for scrollbar width to avoid layout shift.

```tsx
// hooks/useScrollLock.ts
export function useScrollLock(locked: boolean) {
  useEffect(() => {
    if (!locked) return
    const originalOverflow = document.body.style.overflow
    const originalPadding = document.body.style.paddingRight
    const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth
    document.body.style.overflow = 'hidden'
    document.body.style.paddingRight = `${scrollbarWidth}px`
    return () => {
      document.body.style.overflow = originalOverflow
      document.body.style.paddingRight = originalPadding
    }
  }, [locked])
}
```

---

## Lightbox Component (Lazy Loading Adjacent Images)

```tsx
'use client'
import Image from 'next/image'

export function Lightbox({ images, activeIndex, onClose, onNext, onPrev }: LightboxProps) {
  const containerRef = useFocusTrap(true)
  useScrollLock(true)
  useLightboxKeyboard({ onClose, onPrev, onNext })

  const current = images[activeIndex]
  const prev = images[activeIndex - 1]
  const next = images[activeIndex + 1]

  return (
    <div ref={containerRef} role="dialog" aria-modal="true"
      aria-label={`Viewing: ${current.alt}`}
      className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center"
      onClick={onClose}>
      <div className="relative max-w-5xl w-full mx-4" onClick={e => e.stopPropagation()}>
        <Image src={current.src} alt={current.alt} width={current.width} height={current.height}
          priority className="w-full h-auto object-contain max-h-[85vh]" />
      </div>

      {prev && <Image src={prev.src} alt="" width={1} height={1} className="sr-only" loading="eager" />}
      {next && <Image src={next.src} alt="" width={1} height={1} className="sr-only" loading="eager" />}

      <button onClick={onPrev} disabled={activeIndex === 0} aria-label="Previous image"
        className="absolute left-4 top-1/2 -translate-y-1/2 text-white text-4xl disabled:opacity-30">Prev</button>
      <button onClick={onNext} disabled={activeIndex === images.length - 1} aria-label="Next image"
        className="absolute right-4 top-1/2 -translate-y-1/2 text-white text-4xl disabled:opacity-30">Next</button>
      <button onClick={onClose} aria-label="Close image viewer"
        className="absolute top-4 right-4 text-white text-2xl">Close</button>

      <p className="absolute bottom-4 left-1/2 -translate-x-1/2 text-white text-sm">
        {activeIndex + 1} / {images.length}
      </p>
    </div>
  )
}
```

---

## Swipe Gestures (Mobile)

```tsx
// hooks/useSwipeGesture.ts
export function useSwipeGesture(onSwipeLeft: () => void, onSwipeRight: () => void, threshold = 50) {
  const startX = useRef<number>(0)
  return {
    onTouchStart(e: React.TouchEvent) { startX.current = e.touches[0].clientX },
    onTouchEnd(e: React.TouchEvent) {
      const delta = e.changedTouches[0].clientX - startX.current
      if (Math.abs(delta) < threshold) return
      if (delta < 0) onSwipeLeft(); else onSwipeRight()
    },
  }
}
```

Attach: `<div {...useSwipeGesture(onNext, onPrev)} className="fixed inset-0 ...">`

---

## Gallery Grid Layout

```tsx
export function GalleryGrid({ images, onImageClick }: GalleryGridProps) {
  return (
    <ul role="list" className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2" aria-label="Image gallery">
      {images.map((image, index) => (
        <li key={image.id}>
          <button onClick={() => onImageClick(index)} aria-label={`View full size: ${image.alt}`}
            className="relative block w-full aspect-square overflow-hidden rounded focus:ring-2">
            <Image src={image.src} alt={image.alt} fill className="object-cover"
              sizes="(max-width: 768px) 50vw, (max-width: 1200px) 33vw, 25vw"
              loading={index < 4 ? 'eager' : 'lazy'} />
          </button>
        </li>
      ))}
    </ul>
  )
}
```

Use `<button>` not `<div onClick>` — keyboard nav and screen reader access.

---

## Returning Focus on Close

```tsx
const triggerRefs = useRef<(HTMLButtonElement | null)[]>([])

function closeLightbox() {
  const trigger = triggerRefs.current[activeIndex!]
  setActiveIndex(null)
  requestAnimationFrame(() => trigger?.focus())
}
```
