# Responsive Design Guidelines

Mobile-first approach and breakpoint strategies for responsive UI.

## Breakpoint System

### Common Breakpoints
```css
/* Mobile first approach */
/* Base: 0-639px (mobile) */

/* sm: 640px+ (large phones) */
@media (min-width: 640px) { }

/* md: 768px+ (tablets) */
@media (min-width: 768px) { }

/* lg: 1024px+ (laptops) */
@media (min-width: 1024px) { }

/* xl: 1280px+ (desktops) */
@media (min-width: 1280px) { }

/* 2xl: 1536px+ (large screens) */
@media (min-width: 1536px) { }
```

### Tailwind Breakpoints
```html
<!-- Mobile: 1 column, Tablet: 2 columns, Desktop: 3 columns -->
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
  <div class="p-4 bg-white rounded-lg">Card 1</div>
  <div class="p-4 bg-white rounded-lg">Card 2</div>
  <div class="p-4 bg-white rounded-lg">Card 3</div>
</div>
```

## Layout Patterns

### Responsive Container
```html
<div class="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
  <!-- Content -->
</div>
```

### Responsive Navigation
```html
<!-- Mobile: Hamburger menu, Desktop: Horizontal nav -->
<nav class="relative">
  <!-- Logo always visible -->
  <div class="flex items-center justify-between p-4">
    <a href="/" class="text-xl font-bold">Logo</a>
    
    <!-- Mobile menu button -->
    <button class="md:hidden p-2" aria-label="Menu">
      <svg><!-- Hamburger icon --></svg>
    </button>
    
    <!-- Desktop navigation -->
    <div class="hidden md:flex gap-4">
      <a href="/products">Products</a>
      <a href="/about">About</a>
      <a href="/contact">Contact</a>
    </div>
  </div>
  
  <!-- Mobile menu (hidden by default) -->
  <div class="md:hidden hidden" id="mobile-menu">
    <a href="/products" class="block p-4 border-t">Products</a>
    <a href="/about" class="block p-4 border-t">About</a>
    <a href="/contact" class="block p-4 border-t">Contact</a>
  </div>
</nav>
```

### Responsive Grid
```html
<!-- Sidebar + Main content -->
<div class="flex flex-col lg:flex-row gap-6">
  <!-- Sidebar: Full width on mobile, fixed width on desktop -->
  <aside class="w-full lg:w-64 flex-shrink-0">
    <div class="p-4 bg-gray-100 rounded-lg">
      Sidebar content
    </div>
  </aside>
  
  <!-- Main content -->
  <main class="flex-1">
    <div class="p-4 bg-white rounded-lg border">
      Main content
    </div>
  </main>
</div>
```

## Typography Scaling

### Fluid Typography
```css
/* Scales smoothly between breakpoints */
h1 {
  font-size: clamp(1.875rem, 5vw, 3rem);
}

h2 {
  font-size: clamp(1.5rem, 4vw, 2.25rem);
}

p {
  font-size: clamp(1rem, 2vw, 1.125rem);
}
```

### Tailwind Responsive Text
```html
<h1 class="text-2xl sm:text-3xl lg:text-4xl font-bold">
  Responsive Heading
</h1>
<p class="text-sm sm:text-base lg:text-lg text-gray-600">
  Responsive paragraph text
</p>
```

## Image Handling

### Responsive Images
```html
<!-- Responsive image with srcset -->
<img 
  src="image-800.jpg"
  srcset="image-400.jpg 400w,
          image-800.jpg 800w,
          image-1200.jpg 1200w"
  sizes="(max-width: 640px) 100vw,
         (max-width: 1024px) 50vw,
         33vw"
  alt="Responsive image">
```

### Aspect Ratio
```html
<!-- 16:9 video container -->
<div class="relative w-full aspect-video">
  <iframe 
    class="absolute inset-0 w-full h-full"
    src="https://youtube.com/..."
    allowfullscreen>
  </iframe>
</div>

<!-- 1:1 square -->
<div class="aspect-square bg-gray-200 rounded-lg">
  <img src="product.jpg" alt="Product" class="w-full h-full object-cover">
</div>
```

## Touch Targets

### Minimum Size
```css
/* Minimum 44x44px for touch targets */
button, 
a, 
input[type="checkbox"],
input[type="radio"] {
  min-height: 44px;
  min-width: 44px;
}
```

### Touch-Friendly Buttons
```html
<!-- Mobile: Full width, Desktop: Auto width -->
<button class="w-full sm:w-auto px-6 py-3 bg-blue-500 text-white rounded-lg">
  Button
</button>
```

## Responsive Tables

### Scrollable Table
```html
<div class="overflow-x-auto">
  <table class="w-full min-w-[600px]">
    <thead>
      <tr>
        <th>Name</th>
        <th>Email</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>John Doe</td>
        <td>john@example.com</td>
        <td>Active</td>
      </tr>
    </tbody>
  </table>
</div>
```

### Card Layout on Mobile
```html
<!-- Desktop: Table, Mobile: Cards -->
<div class="hidden md:block overflow-x-auto">
  <table class="w-full">
    <!-- Table content -->
  </table>
</div>

<div class="md:hidden space-y-4">
  <div class="p-4 bg-white rounded-lg border">
    <div class="font-semibold">John Doe</div>
    <div class="text-gray-500">john@example.com</div>
    <span class="inline-block mt-2 px-2 py-1 bg-green-100 text-green-700 rounded text-sm">
      Active
    </span>
  </div>
</div>
```

## Hide/Show Elements

```html
<!-- Hide on mobile -->
<div class="hidden md:block">
  Desktop only content
</div>

<!-- Hide on desktop -->
<div class="md:hidden">
  Mobile only content
</div>

<!-- Show only on specific breakpoint -->
<div class="hidden lg:block xl:hidden">
  Only visible on lg breakpoint
</div>
```

## Testing Checklist

- [ ] Test on 320px width (small mobile)
- [ ] Test on 375px width (iPhone)
- [ ] Test on 768px width (tablet)
- [ ] Test on 1024px width (laptop)
- [ ] Test on 1440px width (desktop)
- [ ] Test landscape orientation on mobile
- [ ] Test touch targets are at least 44x44px
- [ ] Test horizontal scrolling is avoided
- [ ] Test images load appropriately for screen size
- [ ] Test text is readable without zooming
