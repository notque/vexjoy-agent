# UI Implementation Patterns Reference

> Loaded by ui-design-engineer when implementing Tailwind themes, accessible components, responsive layouts, or animations.

## Output Format

This agent uses the **Implementation Schema**.

**Phase 1: ANALYZE**
- Classify surface type: landing page or app/dashboard
- Write the narrative brief: visual thesis, content plan, interaction thesis
- Confirm real content is available (hero headline, product name, single promise)
- Identify design requirements (design system, components, responsiveness)
- Determine accessibility needs (WCAG level, ARIA patterns)
- Plan responsive breakpoints and mobile-first strategy

**Phase 2: DESIGN**
- Design Tailwind theme (colors, typography, spacing)
- Design component architecture (variants, composition)
- Plan animation strategy (what animates, when, how)

**Phase 3: IMPLEMENT**
- Implement Tailwind configuration and design tokens
- Build accessible components with ARIA patterns
- Add responsive design and animations
- Ensure WCAG 2.1 AA compliance

**Phase 4: VALIDATE**
- Test keyboard navigation (Tab, Enter, Escape, Arrows)
- Validate color contrast (WCAG contrast checker)
- Check responsive design (mobile/tablet/desktop)
- Verify screen reader compatibility (NVDA/JAWS)

**Final Output**:
```
═══════════════════════════════════════════════════════════════
 UI IMPLEMENTATION COMPLETE
═══════════════════════════════════════════════════════════════

 Design System:
   - Tailwind custom theme
   - Design tokens (colors, typography, spacing)
   - Component library

 Accessibility:
   - WCAG 2.1 AA compliant: ✓
   - Color contrast: ≥4.5:1
   - Keyboard navigation: ✓
   - Screen reader support: ✓

 Responsive Design:
   - Mobile-first: ✓
   - Breakpoints: sm (640px), md (768px), lg (1024px), xl (1280px)
   - Touch targets: ≥44×44px

 Animations:
   - Framer Motion: ✓
   - prefers-reduced-motion: ✓
═══════════════════════════════════════════════════════════════
```

## Design Patterns

### Tailwind Theme Configuration

**Custom Colors and Typography**:
```javascript
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f0f9ff',
          500: '#3b82f6',
          900: '#1e3a8a',
        },
        // Color contrast validated for WCAG AA
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        'xs': ['0.75rem', { lineHeight: '1rem' }],
        'base': ['1rem', { lineHeight: '1.5rem' }],
      },
    },
  },
}
```

### Accessible Button Component

**WCAG Compliant Button**:
```tsx
// components/Button.tsx
interface ButtonProps {
  variant?: 'primary' | 'secondary'
  children: React.ReactNode
  disabled?: boolean
  onClick?: () => void
}

export function Button({ variant = 'primary', children, disabled, onClick }: ButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        // Base styles
        'px-4 py-2 rounded-lg font-medium transition-colors',
        'focus:outline-none focus:ring-2 focus:ring-offset-2',
        // Accessible focus indicator
        'disabled:opacity-50 disabled:cursor-not-allowed',
        // WCAG AA contrast ratios
        variant === 'primary' && 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500',
        variant === 'secondary' && 'bg-gray-200 text-gray-900 hover:bg-gray-300 focus:ring-gray-500',
      )}
    >
      {children}
    </button>
  )
}
```

### Responsive Layout

**Mobile-First Grid**:
```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
  {/* Mobile: 1 column, Tablet: 2 columns, Desktop: 3 columns */}
</div>
```

### Animation with Reduced Motion

**Accessible Animations**:
```tsx
import { motion } from 'framer-motion'

export function Card({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: 0.3,
        // Respect user preferences
        ...(window.matchMedia('(prefers-reduced-motion: reduce)').matches
          ? { duration: 0 }
          : {})
      }}
    >
      {children}
    </motion.div>
  )
}
```
