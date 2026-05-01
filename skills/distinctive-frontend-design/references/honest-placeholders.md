# Honest Placeholders

<!-- Loaded by distinctive-frontend-design when task involves placeholders, missing assets, placeholder images, or no imagery available -->

Use striped placeholders instead of bad imagery. When final assets are not available, a striped background with a monospace label communicates "asset needed" without pretending to be the real thing. Bad stock photos or AI-generated illustrations look intentional and create false design decisions — a stakeholder sees them, assumes that is the direction, and the placeholder becomes permanent by inertia.

## The Striped Placeholder Pattern

```css
.placeholder {
  background: repeating-linear-gradient(
    45deg,
    #e5e5e5,
    #e5e5e5 10px,
    #f0f0f0 10px,
    #f0f0f0 20px
  );
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Courier New', monospace;
  font-size: 14px;
  color: #666;
  min-height: 200px;
  border: 1px dashed #ccc;
}
```

## Usage

Label every placeholder with the asset name and expected dimensions:

```html
<div class="placeholder">product hero (1200x800)</div>
<div class="placeholder">team photo (800x600)</div>
<div class="placeholder">feature screenshot (640x480)</div>
```

The monospace font and dashed border make it visually obvious that this is not a design element. The label tells the asset producer exactly what is needed.

## Dark Mode Variant

```css
[data-theme="dark"] .placeholder,
.dark .placeholder {
  background: repeating-linear-gradient(
    45deg,
    #2a2a2a,
    #2a2a2a 10px,
    #333333 10px,
    #333333 20px
  );
  color: #999;
  border-color: #444;
}
```

## Tailwind Utility Version

When using Tailwind, create a utility class or use arbitrary values:

```html
<!-- Tailwind placeholder with arbitrary gradient -->
<div class="flex items-center justify-center min-h-[200px] font-mono text-sm text-gray-500 border border-dashed border-gray-300 bg-[repeating-linear-gradient(45deg,#e5e5e5,#e5e5e5_10px,#f0f0f0_10px,#f0f0f0_20px)]">
  product hero (1200x800)
</div>
```

Or add a custom utility in `tailwind.config.js`:

```js
// tailwind.config.js
module.exports = {
  theme: {
    extend: {},
  },
  plugins: [
    function({ addUtilities }) {
      addUtilities({
        '.bg-placeholder': {
          background: 'repeating-linear-gradient(45deg, #e5e5e5, #e5e5e5 10px, #f0f0f0 10px, #f0f0f0 20px)',
        },
        '.bg-placeholder-dark': {
          background: 'repeating-linear-gradient(45deg, #2a2a2a, #2a2a2a 10px, #333333 10px, #333333 20px)',
        },
      })
    },
  ],
}
```

```html
<div class="bg-placeholder dark:bg-placeholder-dark flex items-center justify-center min-h-[200px] font-mono text-sm text-gray-500 border border-dashed border-gray-300">
  product hero (1200x800)
</div>
```

## When to Use

- Hero sections before final photography is ready
- Product screenshots before the product is built
- Team photos before the photoshoot
- Blog post featured images before the graphic designer delivers
- Any image slot where using a stock photo would create a false design decision

## When Not to Use

- The asset exists — use the real asset
- A color block or gradient serves the design intent — use the intentional design element
- The design calls for an illustration — commission the illustration or use a licensed set
