"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Menu, X } from "lucide-react";
import { Logo } from "@/components/navigation/Logo";

const NAV = [
  { href: "/stays", label: "Stays" },
  { href: "/flights", label: "Flights" },
  { href: "/eats", label: "Eats" },
  { href: "/experiences", label: "Experiences" },
  { href: "/inspiration?search=events", label: "Events" },
  { href: "/trips", label: "Trips" },
];

export function Header({ sticky }: { sticky?: boolean } = { sticky: true }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => setOpen(false), [pathname]);

  return (
    <header
      className={`sticky top-0 z-50 w-full transition-all duration-300 border-b ${
        scrolled || sticky
          ? "border-white/30 bg-white/80 backdrop-blur-md shadow-sm text-ink"
          : "border-transparent bg-transparent backdrop-blur-md text-ink"
      }`}
    >
      <div className="mx-auto flex h-16 w-full max-w-[1440px] items-center justify-between gap-6 px-5 sm:h-18 sm:px-8">
        <Logo light={false} />

        {/* Desktop Navigation */}
        <nav className="hidden items-center gap-1.5 md:flex" aria-label="Main Navigation">
          {NAV.map((item) => {
            const isActive = pathname === item.href || pathname?.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-full px-4 py-2 text-sm font-semibold transition-all ${
                  isActive
                    ? "bg-ink text-white shadow-xs"
                    : "text-ink/80 hover:bg-ink/5 hover:text-ink"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Right CTA */}
        <div className="hidden items-center gap-3 md:flex">
          <a href="https://apps.apple.com/app/mindtrip-ai-travel-companion/id6503107567" target="_blank" rel="noopener noreferrer" className="text-sm font-semibold text-ink/80 hover:text-ink transition-colors">
            Get app
          </a>
          <a href="#" className="text-sm font-semibold text-ink/80 hover:text-ink transition-colors">
            Log in
          </a>
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-2 rounded-full bg-[#D97706] px-5 py-2.5 text-sm font-semibold text-[#000000] shadow-sm transition-all hover:bg-[#D97706]/90 hover:shadow-md active:scale-[0.98]">
              <Link href="/chat">
                <Sparkle />
                Set up assistant
              </Link>
            </span>
            <span className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-5 py-2.5 text-sm font-semibold text-ink backdrop-blur hover:bg-white/20 transition-all">
              <Link href="/chat">
                Get started
              </Link>
            </span>
          </div>
        </div>

        {/* Mobile menu toggle button */}
        <button
          type="button"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((value) => !value)}
          className="inline-flex size-10 items-center justify-center rounded-full border border-line bg-white text-ink shadow-xs transition-colors hover:bg-ink/5 md:hidden"
        >
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* Mobile Menu Dropdown */}
      {open && (
        <div className="border-t border-line bg-paper/98 px-5 pb-6 pt-3 backdrop-blur-xl shadow-lg md:hidden">
          <nav className="flex flex-col gap-1" aria-label="Mobile Navigation">
            {NAV.map((item) => {
              const isActive = pathname === item.href;
              return (
                <span
                  key={item.href}
                  className={`rounded-xl px-4 py-3 text-base font-semibold transition-colors ${
                    isActive
                      ? "bg-ink text-white"
                      : "text-ink/85 hover:bg-ink/5 hover:text-ink"
                  }`}
                >
                  <Link href={item.href}>{item.label}</Link>
                </span>
              );
            })}
          </nav>
          <div className="mt-4 flex flex-col gap-3">
            <a href="https://apps.apple.com/app/mindtrip-ai-travel-companion/id6503107567" target="_blank" rel="noopener noreferrer" className="text-sm font-semibold text-ink/80 hover:text-ink transition-colors">
              Get app
            </a>
            <a href="#" className="text-sm font-semibold text-ink/80 hover:text-ink transition-colors">
              Log in
            </a>
            <span className="mt-2 flex items-center justify-center gap-2 rounded-full bg-[#D97706] px-5 py-3 text-sm font-semibold text-[#000000] shadow-sm hover:bg-[#D97706]/90 transition-all">
              <Link href="/chat">
                <Sparkle />
                Set up assistant
              </Link>
            </span>
            <span className="flex items-center justify-center gap-2 rounded-full border border-white/15 bg-white/10 px-5 py-3 text-sm font-semibold text-ink backdrop-blur hover:bg-white/20 transition-all">
              <Link href="/chat">
                Get started
              </Link>
            </span>
          </div>
        </div>
      )}
    </header>
  );
}

function Sparkle() {
  return (
    <svg viewBox="0 0 24 24" className="size-4 text-lime" fill="currentColor" aria-hidden="true">
      <path d="M17.991 5.27c1.466-.272 2.314-1.13 2.555-2.575.152 1.392 1.214 2.397 2.533 2.565-1.45.267-2.303 1.12-2.544 2.58a2.862 2.862 0 0 0-.806-1.732 2.887 2.887 0 0 0-1.738-.838ZM1.318 12.877C7.662 11.699 11.332 7.983 12.374 1.73c.657 6.026 5.256 10.375 10.964 11.1C17.063 13.987 13.37 17.68 12.328 24c-.317-2.877-1.45-5.414-3.488-7.499-2.085-2.084-4.6-3.262-7.522-3.624ZM.66 3.434C2.614 3.07 3.745 1.926 4.066 0c.202 1.857 1.62 3.197 3.378 3.42-1.933.356-3.07 1.494-3.392 3.44-.098-.886-.447-1.667-1.075-2.31C2.335 3.909 1.56 3.547.66 3.435Z" />
    </svg>
  );
}