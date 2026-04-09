# Accessibility Guidelines

WCAG compliance and accessibility best practices for UI design.

## Core Principles (POUR)

1. **Perceivable** - Users must be able to perceive the content
2. **Operable** - Users must be able to operate the interface
3. **Understandable** - Users must understand the content and interface
4. **Robust** - Content must be robust enough for various assistive technologies

## Color Contrast

### Minimum Ratios
| Level | Normal Text | Large Text | UI Components |
|-------|-------------|------------|---------------|
| AA | 4.5:1 | 3:1 | 3:1 |
| AAA | 7:1 | 4.5:1 | 3:1 |

### Checking Contrast
```css
/* Good example - passes AA */
.button {
  background: #2563EB; /* blue-600 */
  color: #FFFFFF;
  /* Contrast ratio: 7.5:1 ✓ */
}

/* Bad example - fails AA */
.button {
  background: #60A5FA; /* blue-400 */
  color: #FFFFFF;
  /* Contrast ratio: 2.9:1 ✗ */
}
```

## Keyboard Navigation

### Focus Indicators
```css
/* Always visible focus indicator */
:focus-visible {
  outline: 2px solid #3B82F6;
  outline-offset: 2px;
}

/* Remove default outline only when using :focus-visible */
:focus:not(:focus-visible) {
  outline: none;
}
```

### Tab Order
- Use `tabindex="0"` for interactive elements
- Use `tabindex="-1"` for programmatically focusable elements
- Never use `tabindex` > 0

### Skip Links
```html
<a href="#main-content" class="sr-only focus:not-sr-only">
  Skip to main content
</a>
<main id="main-content">
  <!-- Content -->
</main>
```

## Screen Reader Support

### Semantic HTML
```html
<!-- Good: Semantic structure -->
<header>
  <nav aria-label="Main navigation">
    <ul>
      <li><a href="/">Home</a></li>
    </ul>
  </nav>
</header>
<main>
  <article>
    <h1>Article Title</h1>
    <p>Content...</p>
  </article>
</main>
<footer>
  <p>© 2024 Company</p>
</footer>

<!-- Bad: Non-semantic -->
<div class="header">
  <div class="nav">
    <div class="link">Home</div>
  </div>
</div>
```

### ARIA Labels
```html
<!-- Icon button -->
<button aria-label="Close dialog">
  <svg aria-hidden="true"><!-- X icon --></svg>
</button>

<!-- Form field -->
<input 
  type="text" 
  id="search" 
  aria-label="Search products"
  placeholder="Search...">

<!-- Required field -->
<label for="email">
  Email <span aria-hidden="true">*</span>
</label>
<input 
  type="email" 
  id="email" 
  required
  aria-required="true">
```

### Live Regions
```html
<!-- Announces changes -->
<div aria-live="polite" aria-atomic="true">
  Item added to cart
</div>

<!-- Urgent announcements -->
<div aria-live="assertive">
  Session will expire in 1 minute
</div>
```

## Form Accessibility

### Labels and Errors
```html
<div class="form-group">
  <label for="email">
    Email Address
    <span class="required" aria-hidden="true">*</span>
  </label>
  <input 
    type="email" 
    id="email"
    aria-required="true"
    aria-invalid="true"
    aria-describedby="email-error">
  <span id="email-error" class="error" role="alert">
    Please enter a valid email address
  </span>
</div>
```

### Fieldsets
```html
<fieldset>
  <legend>Shipping Method</legend>
  <label>
    <input type="radio" name="shipping" value="standard">
    Standard (5-7 days)
  </label>
  <label>
    <input type="radio" name="shipping" value="express">
    Express (2-3 days)
  </label>
</fieldset>
```

## Images and Media

### Alt Text
```html
<!-- Informative image -->
<img src="chart.png" alt="Sales increased 25% from Q1 to Q2">

<!-- Decorative image -->
<img src="decoration.png" alt="" role="presentation">

<!-- Complex image -->
<img src="diagram.png" alt="System architecture diagram" 
     aria-describedby="diagram-desc">
<aside id="diagram-desc">
  Detailed description of the diagram...
</aside>
```

### Video/Audio
```html
<video controls>
  <source src="video.mp4" type="video/mp4">
  <track kind="captions" src="captions.vtt" label="English" srclang="en">
</video>

<audio controls>
  <source src="audio.mp3" type="audio/mpeg">
</audio>
```

## Interactive Components

### Buttons vs Links
```html
<!-- Button: Action (no URL change) -->
<button onclick="openModal()">Open Dialog</button>

<!-- Link: Navigation (URL change) -->
<a href="/products">View Products</a>
```

### Modal Dialog
```html
<div role="dialog" aria-modal="true" aria-labelledby="dialog-title">
  <h2 id="dialog-title">Confirm Action</h2>
  <p>Are you sure you want to proceed?</p>
  <button>Cancel</button>
  <button>Confirm</button>
</div>
```

### Tabs
```html
<div role="tablist">
  <button role="tab" aria-selected="true" aria-controls="panel-1">
    Tab 1
  </button>
  <button role="tab" aria-selected="false" aria-controls="panel-2">
    Tab 2
  </button>
</div>
<div role="tabpanel" id="panel-1">Content 1</div>
<div role="tabpanel" id="panel-2" hidden>Content 2</div>
```

## Checklist

- [ ] Color contrast meets WCAG AA (4.5:1 for text)
- [ ] All interactive elements are keyboard accessible
- [ ] Focus indicators are visible
- [ ] Images have appropriate alt text
- [ ] Forms have labels and error messages
- [ ] Headings follow logical hierarchy (h1 → h2 → h3)
- [ ] Links have descriptive text (not "click here")
- [ ] Skip navigation link provided
- [ ] ARIA used only when necessary
- [ ] Works with screen reader (test with VoiceOver/NVDA)
