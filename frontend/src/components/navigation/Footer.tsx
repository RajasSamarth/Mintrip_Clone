"use client";

import Link from "next/link";

export default function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="mt-20 border-t border-line bg-cream/60 px-5 py-14 sm:px-8">
      <div className="mx-auto max-w-[1440px]">
        <div className="grid gap-8 lg:grid-cols-4">
          <div className="flex flex-col gap-4">
            <span className="text-[22px] font-semibold tracking-[-0.04em] text-ink">mindtrip</span>
            <p className="text-sm leading-relaxed text-muted">
              An AI travel assistant with taste. Build the trip around how you travel, keep every idea and booking in one place.
            </p>
            <div className="flex flex-wrap gap-2 text-xs text-muted">
              <span className="rounded-full border border-line bg-white/60 px-3 py-1">OpenStreetMap</span>
              <span className="rounded-full border border-line bg-white/60 px-3 py-1">Wikivoyage</span>
              <span className="rounded-full border border-line bg-white/60 px-3 py-1">OSRM</span>
              <span className="rounded-full border border-line bg-white/60 px-3 py-1">Unsplash</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-8 sm:grid-cols-3 lg:grid-cols-4">
            {[
              {
                title: "For Travelers",
                items: [
                  { label: "Stays", href: "/stays" },
                  { label: "Flights", href: "/flights" },
                  { label: "Eats", href: "/inspiration" },
                  { label: "Experiences", href: "/inspiration" },
                  { label: "Events", href: "/inspiration" },
                  { label: "Trips", href: "/trips" },
                  { label: "Inspiration", href: "/inspiration" },
                  { label: "Help", href: "#help" },
                ],
              },
              {
                title: "for Business",
                items: [
                  { label: "Overview", href: "#business-overview" },
                  { label: "Destinations", href: "#business-destinations" },
                  { label: "Hotels", href: "#business-hotels" },
                  { label: "How It Works", href: "#business-how-it-works" },
                  { label: "Packages", href: "#business-packages" },
                  { label: "Book a Demo", href: "#business-contact" },
                ],
              },
              {
                title: "for Creators",
                items: [
                  { label: "Become a Creator", href: "#creator-program" },
                  { label: "Creator Academy", href: "#creator-academy" },
                ],
              },
              {
                title: "Company",
                items: [
                  { label: "About", href: "#about" },
                  { label: "Team", href: "#team" },
                  { label: "Press", href: "#press" },
                  { label: "Media Kit", href: "#media-kit" },
                  { label: "Contact", href: "#contact" },
                  { label: "Resources", href: "#resources" },
                  { label: "Mindtrip App", href: "https://apps.apple.com/app/mindtrip-ai-travel-companion/id6503107567", external: true },
                ],
              },
            ].map((column) => (
              <div key={column.title}>
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">{column.title}</h3>
                <ul className="space-y-2 text-sm text-ink/70">
                  {column.items.map((item) => (
                    <li key={item.label}>
                      {item.external ? (
                        <a
                          href={item.href}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="hover:text-ink transition-colors"
                        >
                          {item.label}
                        </a>
                      ) : (
                        <Link href={item.href} className="hover:text-ink transition-colors">
                          {item.label}
                        </Link>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-14 flex flex-col gap-4 border-t border-line pt-8 text-xs text-muted sm:flex-row sm:items-center sm:justify-between">
          <span>© {year} Mindtrip, Inc.</span>
          <div className="flex gap-4 sm:flex-col sm:gap-2">
            <a href="#privacy" className="hover:text-ink transition-colors">
              Privacy Policy
            </a>
            <a href="#terms" className="hover:text-ink transition-colors">
              Terms of Service
            </a>
          </div>
          <div className="flex gap-4">
            <a href="https://www.instagram.com/mindtrip.ai" target="_blank" rel="noopener noreferrer" className="hover:text-ink transition-colors" aria-label="Instagram">
              <img src="/images/mindtrip/instagram.png" alt="Instagram" className="size-5" />
            </a>
            <a href="https://www.tiktok.com/@mindtrip.ai" target="_blank" rel="noopener noreferrer" className="hover:text-ink transition-colors" aria-label="TikTok">
              <img src="/images/mindtrip/tiktok.png" alt="TikTok" className="size-5" />
            </a>
            <a href="https://www.facebook.com/mindtripai" target="_blank" rel="noopener noreferrer" className="hover:text-ink transition-colors" aria-label="Facebook">
              <img src="/images/mindtrip/facebook.png" alt="Facebook" className="size-5" />
            </a>
            <a href="https://x.com/mindtripai" target="_blank" rel="noopener noreferrer" className="hover:text-ink transition-colors" aria-label="X">
              <img src="/images/mindtrip/x.png" alt="X" className="size-5" />
            </a>
            <a href="https://www.youtube.com/channel/UCk3qrdSv9ahuWwwLG1mmQGA" target="_blank" rel="noopener noreferrer" className="hover:text-ink transition-colors" aria-label="YouTube">
              <img src="/images/mindtrip/youtube.png" alt="YouTube" className="size-5" />
            </a>
            <a href="https://www.linkedin.com/company/mindtripai" target="_blank" rel="noopener noreferrer" className="hover:text-ink transition-colors" aria-label="LinkedIn">
              <img src="/images/mindtrip/linkedin.png" alt="LinkedIn" className="size-5" />
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}