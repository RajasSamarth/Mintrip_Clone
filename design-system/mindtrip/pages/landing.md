# Design System — Landing Page Override (MindTrip)

> **LOGIC:** This file overrides `MASTER.md` for the landing page only.

---

**Project:** MindTrip  
**Page:** Landing  
**Product Type:** AI Trip Planner / Travel Booking / Itinerary Builder (flights, hotels, restaurants)  
**Target Audience:** Budget travelers, luxury travelers, digital nomads, families, solo adventurers  
**Style:** Aurora UI (vibrant gradients, Northern Lights effect, mesh gradients, luminous, atmospheric)

---

## Page Pattern: Scroll-Triggered Storytelling + Trust & Authority

**Section Order:**
1. **Intro Hook (Hero)** — Mission + credibility + primary CTA (sticky)
2. **Chapter 1: Problem** — Travel planning is chaotic, fragmented across sites
3. **Chapter 2: Journey** — AI chatbot builds complete itinerary (flights + hotels + restaurants)
4. **Chapter 3: Solution** — One plan, every budget, every traveler type
5. **Trust & Proof** — Testimonials, ratings, social proof (before final CTA)
6. **Climax CTA** — Final conversion CTA

**CTA Placement:** Mini CTA at end of each chapter + sticky hero CTA + final climax CTA

**Conversion:** Social proof before final CTA. Verified testimonials with photo, name, role. Star ratings (gold), verified badges (green).

---

## Color Palette (Aurora UI — Adventure Orange + Map Teal)

| Role | Hex | CSS Variable | Usage |
|------|-----|-------------|-------|
| Primary | `#EA580C` | `--color-primary` | Headings, key accents |
| Secondary | `#0891B2` | `--color-secondary` | Map/location elements, secondary actions |
| Accent/CTA | `#D97706` | `--color-accent` | Primary buttons, CTAs |
| Background | `#FFF7ED` | `--color-background` | Page background |
| Foreground | `#0F172A` | `--color-foreground` | Body text |
| Card | `#FFFFFF` | `--color-card` | Cards, white surfaces |
| Muted | `#FDF4F0` | `--color-muted` | Testimonial backgrounds, subtle sections |
| Border | `#FCEAE1` | `--color-border` | Dividers, card borders |
| Destructive | `#DC2626` | `--color-destructive` | Error states, destructive actions |

**Gradient Effects:** Large flowing CSS/SVG gradients, mesh gradients, Northern Lights atmospheric blobs, subtle 8–12s animations, depth via color layering.

---

## Typography

- **Headings:** Outfit (geometric, modern)
- **Body:** Work Sans
- **CSS Import:** Google Fonts Outfit + Work Sans (300–700 weights)

---

## Components

### AI Itinerary Chatbot Form
- Visible label per input (not placeholder-only)
- Error message below related field, connected with `aria-describedby`
- Validate on blur (not keystroke)
- Focus ring: `focus:ring-2 focus:ring-orange-500`
- Mobile input height ≥44px (touch target)
- Password/show-hide not applicable (text input for travel preferences)
- Autocomplete attributes for destination, dates, travelers

### Buttons
- Primary: `#D97706` bg, `#000000` text, `cursor-pointer`, 150–300ms hover transition
- Secondary: transparent bg, `#EA580C` border, `#0F172A` text
- All clickable elements: `cursor:pointer`
- Pressed state: `opacity: 0.9`, `translateY(-1px)` (no layout shift)

### Cards
- Background: `#FFFFFF`, border-radius 12px, padding 24px, shadow-md
- Hover: shadow-lg, translateY(-2px)
- `cursor:pointer` on interactive cards

### Icons
- **No emojis** — use Lucide React SVG icons
- Consistent stroke width (1.5px–2px)
- Decorative icons beside visible text: `aria-hidden="true"`
- Meaningful standalone icons: text alternative + accessible name
- Icon controls: accessible name + selected/pressed/expanded state

---

## Accessibility (Critical)

- Focus rings visible on every interactive control (`focus:ring-2 focus:ring-orange-500`)
- Focus not obscured — sticky header offset with `scroll-padding-top`
- `prefers-reduced-motion`: disable parallax/scroll-scrub, render final readable state
- Color contrast ≥4.5:1 for normal text
- Keyboard nav: tab order matches visual order
- Skip to main content link
- Form errors: `aria-live="polite"` or `role="alert"`, inline errors + error summary
- Toast: `aria-live="polite"`, no focus steal, auto-dismiss 3–5s

---

## Responsive Breakpoints

- 375px (small phone), 768px (tablet), 1024px (laptop), 1440px (desktop)
- Mobile-first design
- No horizontal scroll on mobile
- Viewport meta: `width=device-width, initial-scale=1` (never disable zoom)
- Prefer `min-h-dvh` over `100vh` on mobile

---

## Anti-Patterns (Do NOT Use)

- ❌ Emojis as icons (use Lucide SVG)
- ❌ Missing `cursor:pointer` on clickables
- ❌ Layout-shifting hovers
- ❌ Low contrast text (< 4.5:1)
- ❌ Instant state changes (always 150–300ms transitions)
- ❌ Invisible focus states
- ❌ Relying on hover-only interactions (mobile touch)
- ❌ Placeholder-only labels
- ❌ Color-only meaning (add icon/text for errors/success)

---

## Pre-Delivery Checklist (Landing Page)

- [ ] No emojis used as icons (Lucide SVG)
- [ ] All icons from Lucide, consistent stroke width
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover states with smooth transitions (150–300ms)
- [ ] Light mode text contrast 4.5:1 minimum
- [ ] Focus states visible for keyboard nav
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive: 375px, 768px, 1024px, 1440px
- [ ] No content hidden behind fixed navbar
- [ ] No horizontal scroll on mobile
- [ ] AI form: visible labels, inline errors, focus on first invalid field after submit
- [ ] Social proof section before final CTA
- [ ] Next.js App Router (`app/page.tsx`), `Image fill` for responsive images
