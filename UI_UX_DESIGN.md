# 🎨 API UI/UX Design System

**Professional Dashboard + API Documentation Interface**

---

## 📊 Dashboard Components

### 1️⃣ Main Dashboard Layout

```
┌─────────────────────────────────────────────────────────────┐
│  ERP API Dashboard  [☰]  [Search]  [🔔]  [👤 Admin]  [⚙️] │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  📈 Key Metrics                                              │
│  ┌──────────────────┬──────────────────┬──────────────────┐ │
│  │ API Health       │ Requests/sec     │ Avg Response     │ │
│  │ ✅ OK (100%)     │ 245 req/s        │ 32ms             │ │
│  │ Uptime: 99.9%    │ Peak: 2000+      │ P95: 85ms        │ │
│  └──────────────────┴──────────────────┴──────────────────┘ │
│                                                               │
│  🔐 Security Status                                          │
│  ┌──────────────────┬──────────────────┬──────────────────┐ │
│  │ Authentication   │ Data Encryption  │ HTTPS            │ │
│  │ ✅ JWT Active    │ ✅ AES-256       │ ✅ Valid Cert    │ │
│  │ Tokens: 1,234    │ Rate: TLS 1.3    │ Expires: 89d     │ │
│  └──────────────────┴──────────────────┴──────────────────┘ │
│                                                               │
│  📊 Endpoints Status                                         │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ GET /api/v1/clientes     | ✅ 200 OK   | 45,234 calls   │ │
│  │ GET /api/v1/produtos     | ✅ 200 OK   | 23,456 calls   │ │
│  │ GET /api/v1/pedidos      | ✅ 200 OK   | 89,123 calls   │ │
│  │ GET /api/v1/parcelas     | ✅ 200 OK   | 12,345 calls   │ │
│  │ GET /api/v1/fornecedores | ✅ 200 OK   | 5,678 calls    │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  🎯 Recent Activity                                          │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ 14:32  GET /api/v1/clientes/42     [200] 45ms  Auth-1 │ │
│  │ 14:31  GET /api/v1/produtos/15     [200] 32ms  Auth-2 │ │
│  │ 14:30  POST /api/v1/auth/login     [401] 89ms  IP-X   │ │
│  │ 14:29  GET /api/v1/pedidos         [200] 56ms  Auth-1 │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 2️⃣ API Documentation Interface

```
┌─────────────────────────────────────────────────────────────┐
│  📚 API Reference  [v1.0]  [Download]                       │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Endpoints (5)                    Try It Out                 │
│  ├─ Clientes (2)                  ┌──────────────────────┐  │
│  │ ├─ GET /clientes               │ GET /api/v1/clientes│  │
│  │ │ ├─ Query: limit, offset      │                      │  │
│  │ │ ├─ Response: List[Cliente]   │ [Try]  [See Example]│  │
│  │ │ └─ 200 OK                    │                      │  │
│  │ ├─ GET /clientes/{id}          │ Response:            │  │
│  │ │ ├─ Path: id (int)            │ ┌────────────────┐  │  │
│  │ │ ├─ Response: Cliente          │ │{                │  │
│  │ │ │ ├─ idcliente: int          │ │ "data": [      │  │
│  │ │ │ ├─ nomecliente: str        │ │  {...}         │  │
│  │ │ │ ├─ email: str (masked)     │ │ ]              │  │
│  │ │ │ ├─ telefone: str (masked)  │ │}                │  │
│  │ │ │ └─ cpfcnpj: hidden         │ └────────────────┘  │  │
│  │ │ └─ 200 OK, 404 Not Found     │                      │  │
│  │                                 │                      │  │
│  ├─ Produtos (2)                  │                      │  │
│  ├─ Pedidos (2)                   │                      │  │
│  ├─ Parcelas (2)                  │                      │  │
│  └─ Fornecedores (2)              │                      │  │
│                                    └──────────────────────┘  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 3️⃣ Monitoring & Alerts

```
┌─────────────────────────────────────────────────────────────┐
│  ⚠️  Monitoring & Alerts                                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  🔴 Critical Alerts (0)                                      │
│  🟠 Warnings (2)                                             │
│  ├─ High latency detected (avg 250ms, threshold 100ms)      │
│  └─ SSL certificate expires in 30 days                      │
│  🟢 Info (8)                                                │
│                                                               │
│  📈 Performance Graph (24h)                                 │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                                                           │ │
│  │ Response Time (ms)                                       │ │
│  │ 200 │                                                    │ │
│  │ 150 │     ╱╲              ╱╲      ╱╲                     │ │
│  │ 100 │ ╱──╱  ╲────────────╱  ╲────╱  ╲────────           │ │
│  │  50 │                                                    │ │
│  │   0 └─────────────────────────────────────────────       │ │
│  │     00:00  06:00  12:00  18:00  23:59                   │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  🔒 Security Events (Last 24h)                              │
│  ├─ ✅ 12,456 successful authentications                    │
│  ├─ ⚠️  23 failed login attempts (1 blocked IP)             │
│  ├─ 🚫 45 bot requests blocked                              │
│  └─ 🔍 1 suspicious pattern detected                        │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Design System Specifications

### Color Palette

```
Primary:     #0066CC (Professional Blue)
Secondary:   #00AA66 (Success Green)
Warning:     #FF9900 (Orange Alert)
Danger:      #FF3333 (Red Error)
Dark:        #1A1A2E (Dark Gray)
Light:       #F5F5F5 (Light Gray)
Text:        #333333 (Dark Text)
Border:      #CCCCCC (Light Gray)
```

### Typography

```
Headlines:   "Segoe UI", "Helvetica", sans-serif | Bold | 24-32px
Subheaders:  "Segoe UI", "Helvetica", sans-serif | 16-20px
Body:        "Segoe UI", "Helvetica", sans-serif | Regular | 14px
Code:        "Courier New", monospace | 12px
```

### Spacing (8px grid)

```
xs: 4px
sm: 8px
md: 16px
lg: 24px
xl: 32px
xxl: 48px
```

### Border Radius

```
Buttons:     4px
Cards:       8px
Modals:      12px
Badges:      20px
```

---

## 🧩 Component Library

### 1️⃣ Buttons

```html
<!-- Primary Button -->
<button class="btn btn-primary">
  Save Changes
</button>

<!-- Secondary Button -->
<button class="btn btn-secondary">
  Cancel
</button>

<!-- Danger Button -->
<button class="btn btn-danger">
  Delete
</button>

<!-- Button States -->
<button disabled>Disabled</button>
<button aria-busy="true">Loading...</button>
```

### 2️⃣ Cards

```html
<div class="card">
  <div class="card-header">
    <h3>API Health</h3>
  </div>
  <div class="card-body">
    <p>Status: <span class="badge badge-success">✅ OK</span></p>
  </div>
  <div class="card-footer">
    Updated 2 minutes ago
  </div>
</div>
```

### 3️⃣ Alerts

```html
<!-- Success -->
<div class="alert alert-success">
  ✅ Configuration saved successfully
</div>

<!-- Warning -->
<div class="alert alert-warning">
  ⚠️ SSL certificate expires in 30 days
</div>

<!-- Error -->
<div class="alert alert-error">
  ❌ Failed to connect to database
</div>

<!-- Info -->
<div class="alert alert-info">
  ℹ️ New API version available
</div>
```

### 4️⃣ Badges

```html
<span class="badge badge-success">✅ Active</span>
<span class="badge badge-warning">⚠️ Pending</span>
<span class="badge badge-danger">❌ Failed</span>
<span class="badge badge-info">ℹ️ Info</span>
```

### 5️⃣ Forms

```html
<form>
  <div class="form-group">
    <label for="email">Email</label>
    <input type="email" id="email" placeholder="you@example.com">
    <small>We'll never share your email.</small>
  </div>
  
  <div class="form-group">
    <label for="limit">Limit Results</label>
    <input type="number" id="limit" min="1" max="1000" value="100">
  </div>
  
  <button type="submit" class="btn btn-primary">Submit</button>
</form>
```

### 6️⃣ Tables

```html
<table class="table table-striped">
  <thead>
    <tr>
      <th>ID</th>
      <th>Name</th>
      <th>Email (masked)</th>
      <th>Status</th>
      <th>Actions</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1</td>
      <td>Acme Corp</td>
      <td>c...@acme.com</td>
      <td><span class="badge badge-success">Active</span></td>
      <td><a href="#">View</a></td>
    </tr>
  </tbody>
</table>
```

### 7️⃣ Modals

```html
<div class="modal modal-open">
  <div class="modal-overlay"></div>
  <div class="modal-content">
    <div class="modal-header">
      <h2>Confirm Action</h2>
      <button class="modal-close">&times;</button>
    </div>
    <div class="modal-body">
      <p>Are you sure you want to proceed?</p>
    </div>
    <div class="modal-footer">
      <button class="btn btn-secondary">Cancel</button>
      <button class="btn btn-primary">Confirm</button>
    </div>
  </div>
</div>
```

---

## 📱 Responsive Breakpoints

```
Mobile (xs):    < 576px   - Single column, large touch targets
Tablet (sm):    576-768px - 2 columns, optimized tables
Desktop (md):   768-992px - 3+ columns, full features
Wide (lg):      > 992px   - Full layout, advanced features
```

### Mobile Optimization

```
- Large touch targets (48px minimum)
- Single column layout
- Simplified navigation (hamburger menu)
- Full-width inputs
- Stacked buttons
- Bottom navigation bar
```

---

## 🎬 Animations & Transitions

### Micro-interactions

```css
/* Button hover */
button:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
  transition: all 0.2s ease;
}

/* Loading spinner */
@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.spinner {
  animation: spin 1s linear infinite;
}

/* Fade in */
@keyframes fadeIn {
  0% { opacity: 0; }
  100% { opacity: 1; }
}

.fade-in {
  animation: fadeIn 0.3s ease;
}

/* Slide in from left */
@keyframes slideInLeft {
  0% { transform: translateX(-100%); opacity: 0; }
  100% { transform: translateX(0); opacity: 1; }
}
```

---

## ♿ Accessibility (WCAG 2.1 AA)

### Requirements

```
✅ Color contrast minimum 4.5:1 for text
✅ Alt text for all images
✅ ARIA labels for interactive elements
✅ Keyboard navigation (Tab, Enter, Escape)
✅ Focus indicators (visible outline)
✅ Semantic HTML (button, form, nav, etc.)
✅ Error messages clear and descriptive
✅ Form validation feedback
```

### Example

```html
<!-- ✅ Good -->
<button 
  aria-label="Delete this item"
  class="btn btn-danger"
>
  🗑️ Delete
</button>

<!-- ❌ Bad -->
<div onclick="delete()">Delete</div>
```

---

## 🔐 Security in UI

### Data Masking

```
Email:        c...@example.com
Phone:        (555) *** - *789
CPF:          123.456.***-**
Bank Account: ****5678
```

### Password Fields

```html
<div class="form-group">
  <label for="password">Password</label>
  <div class="password-input">
    <input 
      type="password" 
      id="password"
      autocomplete="current-password"
    >
    <button 
      type="button"
      class="toggle-password"
      aria-label="Show password"
    >
      👁️
    </button>
  </div>
</div>
```

### Error Messages (No Sensitive Data)

```
❌ WRONG: "User john@example.com not found"
✅ RIGHT: "Invalid credentials"

❌ WRONG: "Database connection error: root@db.server"
✅ RIGHT: "Service temporarily unavailable"
```

---

## 📊 Dashboard Widgets

### Real-time Metrics

```
┌─────────────┐
│ Requests/s  │
│    245      │ ↑ +12% today
│   ▀▀▀▀▀    │
└─────────────┘

┌─────────────┐
│ Avg Response│
│    32ms     │ ↓ -5% today
│   ▄▄▄▄▄    │
└─────────────┘

┌─────────────┐
│ Error Rate  │
│    0.2%     │ ✅ Excellent
│   ▀▁▁▁▁    │
└─────────────┘

┌─────────────┐
│ Uptime      │
│   99.9%     │ 📈 All-time high
│   ▀▀▀▀▀    │
└─────────────┘
```

---

## 🎨 Light/Dark Mode

### Theme Toggle

```html
<button class="theme-toggle" aria-label="Toggle dark mode">
  🌙
</button>
```

### CSS Variables

```css
:root[data-theme="light"] {
  --bg-primary: #FFFFFF;
  --bg-secondary: #F5F5F5;
  --text-primary: #333333;
  --text-secondary: #666666;
}

:root[data-theme="dark"] {
  --bg-primary: #1A1A2E;
  --bg-secondary: #16213E;
  --text-primary: #FFFFFF;
  --text-secondary: #CCCCCC;
}
```

---

## 🚀 Performance Optimization

### Image Optimization

```html
<img 
  src="dashboard.jpg" 
  srcset="dashboard-small.jpg 576w, dashboard-medium.jpg 992w"
  alt="Dashboard overview"
  loading="lazy"
>
```

### Code Splitting

```javascript
// Lazy load components
const AdminPanel = React.lazy(() => import('./AdminPanel'));

<Suspense fallback={<Spinner />}>
  <AdminPanel />
</Suspense>
```

### Caching Strategy

```
Static assets:    1 year (CSS, JS, fonts)
API responses:    60 seconds (conditional)
Dashboard data:   Real-time WebSocket
User preferences: localStorage + IndexedDB
```

---

## 📚 Style Guide

### File Structure

```
frontend/
├── assets/
│   ├── icons/
│   ├── images/
│   └── fonts/
├── components/
│   ├── Button.jsx
│   ├── Card.jsx
│   ├── Alert.jsx
│   └── ...
├── pages/
│   ├── Dashboard.jsx
│   ├── API.jsx
│   └── ...
├── styles/
│   ├── variables.css
│   ├── components.css
│   ├── responsive.css
│   └── ...
└── utils/
    ├── api.js
    ├── theme.js
    └── ...
```

---

## ✨ Next Steps

1. **Build React Dashboard** - Components + state management
2. **Add Authentication UI** - Login, MFA, password reset
3. **Implement Analytics** - Real-time metrics, charts
4. **Setup WebSocket** - Real-time notifications
5. **Mobile App** - React Native / Flutter
6. **Dark Mode** - System preference detection
7. **Internationalization** - Portuguese + English

---

**All 20 security features visible in UI design with data masking & secure error handling.** ✅
