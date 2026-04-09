# UI Design Patterns

Common UI patterns for reference when designing interfaces.

## Navigation Patterns

### Top Navigation Bar
```html
<nav class="flex items-center justify-between px-6 py-4 bg-white border-b">
  <div class="flex items-center gap-8">
    <a href="/" class="text-xl font-bold">Logo</a>
    <div class="flex gap-4">
      <a href="/products" class="hover:text-blue-500">Products</a>
      <a href="/about" class="hover:text-blue-500">About</a>
      <a href="/contact" class="hover:text-blue-500">Contact</a>
    </div>
  </div>
  <div class="flex items-center gap-4">
    <button class="p-2 hover:bg-gray-100 rounded-full">
      <svg><!-- Search icon --></svg>
    </button>
    <button class="px-4 py-2 bg-blue-500 text-white rounded-lg">
      Sign In
    </button>
  </div>
</nav>
```

### Sidebar Navigation
```html
<aside class="w-64 h-screen bg-gray-900 text-white p-4">
  <div class="mb-8">
    <h1 class="text-xl font-bold">Dashboard</h1>
  </div>
  <nav class="space-y-2">
    <a href="#" class="flex items-center gap-3 px-4 py-2 rounded-lg bg-gray-800">
      <svg><!-- Icon --></svg>
      <span>Overview</span>
    </a>
    <a href="#" class="flex items-center gap-3 px-4 py-2 rounded-lg hover:bg-gray-800">
      <svg><!-- Icon --></svg>
      <span>Analytics</span>
    </a>
  </nav>
</aside>
```

## Card Patterns

### Basic Card
```html
<div class="bg-white rounded-xl shadow-sm border p-6">
  <h3 class="text-lg font-semibold mb-2">Card Title</h3>
  <p class="text-gray-600 mb-4">Card description goes here.</p>
  <button class="text-blue-500 hover:text-blue-600">Learn more →</button>
</div>
```

### Product Card
```html
<div class="bg-white rounded-xl overflow-hidden shadow-sm border">
  <img src="product.jpg" alt="Product" class="w-full h-48 object-cover">
  <div class="p-4">
    <h3 class="font-semibold">Product Name</h3>
    <p class="text-gray-500 text-sm mb-2">Category</p>
    <div class="flex items-center justify-between">
      <span class="text-lg font-bold">$99</span>
      <button class="px-4 py-2 bg-blue-500 text-white rounded-lg text-sm">
        Add to Cart
      </button>
    </div>
  </div>
</div>
```

## Form Patterns

### Login Form
```html
<form class="max-w-md mx-auto p-6 bg-white rounded-xl shadow-sm">
  <h2 class="text-2xl font-bold mb-6 text-center">Sign In</h2>
  
  <div class="mb-4">
    <label class="block text-sm font-medium mb-1">Email</label>
    <input type="email" 
           class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
           placeholder="you@example.com">
  </div>
  
  <div class="mb-4">
    <label class="block text-sm font-medium mb-1">Password</label>
    <input type="password" 
           class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
           placeholder="••••••••">
  </div>
  
  <button type="submit" 
          class="w-full py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors">
    Sign In
  </button>
</form>
```

### Search Input
```html
<div class="relative">
  <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400">
    <!-- Search icon -->
  </svg>
  <input type="search" 
         class="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
         placeholder="Search...">
</div>
```

## Modal Patterns

### Centered Modal
```html
<div class="fixed inset-0 bg-black/50 flex items-center justify-center p-4">
  <div class="bg-white rounded-xl max-w-md w-full p-6">
    <div class="flex justify-between items-center mb-4">
      <h2 class="text-xl font-bold">Modal Title</h2>
      <button class="p-1 hover:bg-gray-100 rounded">
        <svg><!-- Close icon --></svg>
      </button>
    </div>
    <p class="text-gray-600 mb-6">Modal content goes here.</p>
    <div class="flex gap-3 justify-end">
      <button class="px-4 py-2 border rounded-lg hover:bg-gray-50">Cancel</button>
      <button class="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600">Confirm</button>
    </div>
  </div>
</div>
```

## Button Variants

```html
<!-- Primary -->
<button class="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600">
  Primary
</button>

<!-- Secondary -->
<button class="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200">
  Secondary
</button>

<!-- Outline -->
<button class="px-4 py-2 border border-blue-500 text-blue-500 rounded-lg hover:bg-blue-50">
  Outline
</button>

<!-- Ghost -->
<button class="px-4 py-2 text-gray-700 rounded-lg hover:bg-gray-100">
  Ghost
</button>

<!-- Danger -->
<button class="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600">
  Danger
</button>

<!-- Disabled -->
<button class="px-4 py-2 bg-gray-300 text-gray-500 rounded-lg cursor-not-allowed" disabled>
  Disabled
</button>
```

## Alert Patterns

```html
<!-- Info -->
<div class="flex gap-3 p-4 bg-blue-50 border border-blue-200 rounded-lg">
  <svg class="w-5 h-5 text-blue-500 flex-shrink-0"><!-- Icon --></svg>
  <div>
    <h4 class="font-medium text-blue-800">Information</h4>
    <p class="text-blue-700 text-sm">This is an info message.</p>
  </div>
</div>

<!-- Success -->
<div class="flex gap-3 p-4 bg-green-50 border border-green-200 rounded-lg">
  <svg class="w-5 h-5 text-green-500 flex-shrink-0"><!-- Icon --></svg>
  <div>
    <h4 class="font-medium text-green-800">Success</h4>
    <p class="text-green-700 text-sm">Operation completed successfully.</p>
  </div>
</div>

<!-- Warning -->
<div class="flex gap-3 p-4 bg-amber-50 border border-amber-200 rounded-lg">
  <svg class="w-5 h-5 text-amber-500 flex-shrink-0"><!-- Icon --></svg>
  <div>
    <h4 class="font-medium text-amber-800">Warning</h4>
    <p class="text-amber-700 text-sm">Please review before proceeding.</p>
  </div>
</div>

<!-- Error -->
<div class="flex gap-3 p-4 bg-red-50 border border-red-200 rounded-lg">
  <svg class="w-5 h-5 text-red-500 flex-shrink-0"><!-- Icon --></svg>
  <div>
    <h4 class="font-medium text-red-800">Error</h4>
    <p class="text-red-700 text-sm">Something went wrong.</p>
  </div>
</div>
```
