# Services Landing Page Template
This project is a professional services landing page template built with modern web technologies. It serves as a foundational template that can be customized for any service-based business including consulting firms, agencies, healthcare practices, law firms, and more.

## Tech Stack
- **React** - UI library
- **Vite** - Build tool
- **Tailwind CSS** - Utility-first CSS framework
- **Framer Motion** - Animation library
- **pnpm** - Package manager
- **React Router** - Routing library

## Core Requirements

### Tech Stack & Setup
- React + Vite with JavaScript (no TypeScript)
- Tailwind CSS for all styling (no external CSS, CSS modules, or inline styles unless absolutely necessary)

### Folder Structure
```
src/
  components/    # Reusable UI components
  pages/         # Page-level components
  utils/         # Utility functions
  App.jsx        # Main application component
  main.jsx       # Entry point
public/          # Public assets
```

### Layout & Structure
- Structure components to reflect high-level semantic sections of the page
- Current template structure:
```jsx
<Router>
  <div className="min-h-screen bg-white">
    <Navigation />
    <main>
      <Hero />
      <About />
      <Statistics />
      <Team />
      <Services />
      <Testimonials />
      <LocationsBanner />
    </main>
    <Footer />
  </div>
</Router>
```
- Components are modular and can be easily customized or removed
- Each section uses semantic HTML for accessibility

### Routing & Links
- Implement all accessible routes from the original site
- No empty or dead links — all navigation should lead to a functional page or section
- Use react-router-dom for multi-page routing
- Replicate smooth scrolling for anchor links if present

### Styling
- Match the visual style of the source site as closely as possible using Tailwind classes
- Ensure full responsiveness across breakpoints
- Use Tailwind spacing scales and responsive utilities instead of arbitrary pixel values unless needed for precision

### Animations & Interactivity
- Recreate animations and micro-interactions from the original site
- Use Framer Motion or Tailwind transitions for performance-friendly effects
- Avoid excessive animations or layout shifts that harm UX or accessibility

### HTML Semantics & Accessibility
- Use semantic HTML (header, nav, main, section, footer) instead of generic `<div>` containers
- Add descriptive alt text for all images, aria-label for icons, and correct heading levels

## Features
- Modern React with hooks and functional components
- Fast refresh with Vite
- Responsive design capabilities with Tailwind
- Smooth animations with Framer Motion
- Import aliases configured (`@/` points to `src/`)
- Optimized for performance

## UI Component Libraries
While the primary goal is to match the original site's design as closely as possible, the AI agent may consider using these component libraries for functionality:
- **Magic UI** ([magicui.design](https://magicui.design/)) - 150+ free and open-source animated components built with React, Tailwind CSS, and Motion
- **shadcn/ui** ([ui.shadcn.com](https://ui.shadcn.com/)) - A collection of beautifully designed, accessible components that can be copied and customized

> **Important**: These libraries should be used primarily for functionality and interaction patterns. The visual styling must still adhere to the original website's design. Component styles should be customized to match the target site's look and feel.

## Getting Started
```bash
# Install dependencies
pnpm install
# Start development server
pnpm dev
# Build for production
pnpm build
# Preview production build
pnpm preview
```

## Import Aliases
This project is configured with import aliases for cleaner imports:
```javascript
// Instead of this:
import Component from '../../components/Component'
// You can use:
import Component from '@/components/Component'
```