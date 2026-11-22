"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Plane,
  Hotel,
  Utensils,
  MapPin,
  MessageCircle,
  Clock,
  Users,
  Star,
  CheckCircle,
  ChevronRight,
  Mail,
  Phone,
  Check,
  Zap,
  Heart,
  Leaf,
} from "lucide-react";
import { Logo } from "@/components/navigation/Logo";

/* ------------------------------------------------------------------ */
/*  Landing Page                                                      */
/* ------------------------------------------------------------------ */

export default function LandingPage() {
  const [scrolled, setScrolled] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (video) {
      video.muted = true;
      video.play().catch(() => {
        // Autoplay may be blocked until user interaction.
      });
    }

    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      videoRef.current?.pause();
    };
  }, []);

  return (
    <div className="min-h-screen bg-[#FFF7ED] text-[#0F172A]">
      {/* Skip link */}
      <a
        href="#hero"
        className="skip-link focus-ring-aurora px-4 py-2 text-sm font-semibold"
      >
        Skip to content
      </a>

      {/* Existing Header from layout.tsx */}
      <HeaderPlaceholder />

      {/* Aurora decorative layer */}
      <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
        <div className="blob-gradient inset-0"></div>
      </div>

      <main>
        {/* ========== 1. HERO ========== */}
        <section
          id="hero"
          className="relative overflow-hidden py-20 sm:py-28 lg:py-32"
        >
          <div className="absolute inset-0 -z-10">
            <video
              ref={videoRef}
              autoPlay
              muted
              loop
              playsInline
              className="absolute inset-0 w-full h-full object-cover"
            >
              <source src="/images/mindtrip/landing page shot.mp4" type="video/mp4" />
            </video>
            <div className="absolute inset-0 bg-[#0F172A]/55" />
            <div
              className="absolute inset-0 bg-gradient-to-t from-[#0F172A]/80 via-transparent to-transparent"
            />
          </div>

          <div className="relative z-10 mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-8 text-center">
            <span className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-medium text-white/90 backdrop-blur uppercase tracking-wider animate-fade-up">
              AI travel assistant
            </span>
            <h1 className="mt-6 font-heading text-[3rem] sm:text-[4.5rem] lg:text-[5.5rem] font-bold leading-[1.05] tracking-tight text-white text-balance animate-fade-up">
              Plan your perfect trip in minutes.
            </h1>
            <p className="mt-6 max-w-[60ch] mx-auto text-white/90 text-lg leading-relaxed sm:text-xl animate-fade-up">
              Mindtrip finds your flights, hotels, and restaurants — then builds a
              complete itinerary that fits your budget and travel style.
            </p>
            <div className="mt-12 flex flex-wrap items-center justify-center gap-4 animate-fade-up">
              <Link
                href="/chat"
                className="btn-aurora-primary inline-flex items-center justify-center gap-2 px-8 py-4 text-xl font-semibold"
              >
                Build my itinerary <ArrowRight className="size-5" />
              </Link>
              <Link
                href="/chat"
                className="btn-aurora-secondary inline-flex items-center justify-center gap-2 px-8 py-4 text-xl font-semibold"
              >
                Explore destinations <ArrowRight className="size-5" />
              </Link>
            </div>
          </div>
        </section>

        {/* ========== 2. HOW IT WORKS ========== */}
        <section id="how-it-works" className="py-24 sm:py-32 border-t border-[#FCEAE1] bg-[#FFF7ED]">
          <div className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-8">
            <div className="max-w-[720px] mx-auto text-center mb-20 sm:mb-28 animate-fade-up">
              <h2 className="font-heading text-3xl sm:text-[3rem] font-bold leading-[1.15] tracking-tight text-[#0F172A] text-balance">
                From idea to itinerary in 3 steps
              </h2>
              <p className="mt-6 text-lg text-[#475569] leading-relaxed">
                Tell us where you want to go, and Mindtrip handles the rest —
                flights, hotels, restaurants, and everything in between.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 sm:gap-8">
              {[
                {
                  step: "1",
                  title: "Tell us your trip",
                  desc: "Destination, dates, travelers, budget, and interests.",
                  icon: <MapPin className="size-6" />,
                  color: "bg-orange-500/10 text-orange-500 border-orange-500/20",
                  gradient: "from-orange-500/20 to-orange-500/5",
                  cta: "Start planning",
                },
                {
                  step: "2",
                  title: "AI builds your plan",
                  desc: "Flights, hotels, restaurants, and activities in one itinerary.",
                  icon: <Zap className="size-6" />,
                  color: "bg-[#0891B2]/10 text-[#0891B2] border-[#0891B2]/20",
                  gradient: "from-[#0891B2]/20 to-[#0891B2]/5",
                  cta: "View example plans",
                },
                {
                  step: "3",
                  title: "Book and go",
                  desc: "Book directly or let your assistant handle the details.",
                  icon: <CheckCircle className="size-6" />,
                  color: "bg-[#D97706]/10 text-[#D97706] border-[#D97706]/20",
                  gradient: "from-[#D97706]/20 to-[#D97706]/5",
                  cta: "Book your trip",
                },
              ].map((item, idx) => (
                <div
                  key={item.title}
                  className={`card-aurora p-8 sm:p-10 flex flex-col items-center text-center group relative overflow-hidden animate-fade-up`}
                  style={{ animationDelay: `${idx * 100}ms` }}
                >
                  {/* Colored accent glow */}
                  <div
                    className={`absolute top-0 left-0 w-full h-1 bg-gradient-to-r ${item.gradient} opacity-0 group-hover:opacity-100 transition-opacity duration-300`}
                  ></div>

                  <div className="relative z-10 size-16 rounded-full flex items-center justify-center mb-8 ${item.color} shadow-lg group-hover:scale-110 transition-transform duration-300">
                    {item.step}
                  </div>
                  <div
                    className={`relative z-10 size-14 rounded-full flex items-center justify-center mb-8 ${item.color.replace("/10", "/20")} group-hover:rotate-12 transition-transform duration-500`}
                  >
                    {item.icon}
                  </div>
                  <h3
                    className={`relative z-10 font-heading text-lg font-semibold text-[#0F172A] mb-3 group-hover:text-[#D97706] transition-colors duration-300`}
                  >
                    {item.title}
                  </h3>
                  <p
                    className={`relative z-10 text-[#475569] leading-relaxed mb-8`}
                  >
                    {item.desc}
                  </p>
                  <Link
                    href="/chat"
                    className={`relative z-10 inline-flex items-center gap-1.5 text-sm font-semibold text-[#D97706] hover:text-[#EA580C] underline-offset-4 group-hover:underline transition-all`}
                  >
                    {item.cta} <ArrowRight className="size-4" />
                  </Link>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ========== 3. AI ITINERARY BUILDER ========== */}
        <section id="ai-itinerary" className="py-24 sm:py-32 bg-white">
          <div className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-8">
            <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center animate-fade-up">
              <div>
                <h2 className="font-heading text-3xl sm:text-[3rem] font-bold leading-[1.15] tracking-tight text-[#0F172A] text-balance">
                  Your AI travel assistant builds the full plan
                </h2>
                <p className="mt-6 text-lg text-[#475569] leading-relaxed">
                  From finding flights under your budget to booking boutique hotels
                  and the best local restaurants — Mindtrip plans every detail so you
                  don&apos;t have to.
                </p>
                <ul className="mt-10 space-y-5">
                  {[
                    {
                      text: "Flights — filtered by price, timing, and airline preference",
                      icon: <Plane className="size-5" />,
                      color: "text-[#D97706]",
                    },
                    {
                      text: "Hotels — matched to your budget and travel style",
                      icon: <Hotel className="size-5" />,
                      color: "text-[#0891B2]",
                    },
                    {
                      text: "Restaurants — local gems and family-friendly spots",
                      icon: <Utensils className="size-5" />,
                      color: "text-[#D97706]",
                    },
                    {
                      text: "Activities — things locals actually love",
                      icon: <MapPin className="size-5" />,
                      color: "text-[#0891B2]",
                    },
                  ].map((feature, idx) => (
                    <li
                      key={feature.text}
                      className="flex items-start gap-4 animate-fade-up"
                      style={{ animationDelay: `${idx * 100}ms` }}
                    >
                      <div
                        className={`size-8 rounded-full flex-shrink-0 flex items-center justify-center ${feature.color} bg-[${feature.color.replace("text-", "bg-").replace("500", "500/10")}]`}
                      >
                        {feature.icon}
                      </div>
                      <p className="text-[#0F172A] leading-relaxed">
                        {feature.text}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="relative animate-floaty">
                <div
                  className={`absolute inset-0 rounded-2xl blur-[40px] bg-orange-500/20`}
                ></div>
                <div className="relative rounded-2xl border border-[#FCEAE1] bg-white shadow-xl overflow-hidden">
                  <form
                    className="p-6 sm:p-8 space-y-5 animate-fade-up"
                    onSubmit={(e) => {
                      e.preventDefault();
                    }}
                  >
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div className="col-span-2 sm:col-span-1">
                        <label
                          htmlFor="destination"
                          className="block mb-2 text-sm font-medium text-[#0F172A]"
                        >
                          Destination
                        </label>
                        <input
                          id="destination"
                          type="text"
                          placeholder="e.g. Kyoto, Japan"
                          className="w-full px-4 py-3 rounded-lg border border-[#FCEAE1] bg-white text-[#0F172A] focus:ring-2 focus-ring-aurora focus:border-[#D97706] transition-colors"
                          autoComplete="destination"
                          required
                        />
                      </div>
                      <div className="col-span-2 sm:col-span-1">
                        <label
                          htmlFor="travelers"
                          className="block mb-2 text-sm font-medium text-[#0F172A]"
                        >
                          Travelers
                        </label>
                        <input
                          id="travelers"
                          type="number"
                          placeholder="2"
                          min="1"
                          className="w-full px-4 py-3 rounded-lg border border-[#FCEAE1] bg-white text-[#0F172A] focus:ring-2 focus-ring-aurora focus:border-[#D97706] transition-colors"
                          autoComplete="additional-info"
                          required
                        />
                      </div>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div className="col-span-2 sm:col-span-1">
                        <label
                          htmlFor="checkin"
                          className="block mb-2 text-sm font-medium text-[#0F172A]"
                        >
                          Check-in
                        </label>
                        <input
                          id="checkin"
                          type="date"
                          className="w-full px-4 py-3 rounded-lg border border-[#FCEAE1] bg-white text-[#0F172A] focus:ring-2 focus-ring-aurora focus:border-[#D97706] transition-colors"
                          required
                        />
                      </div>
                      <div className="col-span-2 sm:col-span-1">
                        <label
                          htmlFor="checkout"
                          className="block mb-2 text-sm font-medium text-[#0F172A]"
                        >
                          Check-out
                        </label>
                        <input
                          id="checkout"
                          type="date"
                          className="w-full px-4 py-3 rounded-lg border border-[#FCEAE1] bg-white text-[#0F172A] focus:ring-2 focus-ring-aurora focus:border-[#D97706] transition-colors"
                          required
                        />
                      </div>
                    </div>
                    <div>
                      <label
                        htmlFor="budget"
                        className="block mb-2 text-sm font-medium text-[#0F172A]"
                      >
                        Budget level
                      </label>
                      <select
                        id="budget"
                        className="w-full px-4 py-3 rounded-lg border border-[#FCEAE1] bg-white text-[#0F172A] focus:ring-2 focus-ring-aurora focus:border-[#D97706] transition-colors"
                      >
                        <option value="budget">Budget traveler</option>
                        <option value="mid">Mid-range</option>
                        <option value="luxury">Luxury</option>
                      </select>
                    </div>
                    <div>
                      <label
                        htmlFor="interests"
                        className="block mb-2 text-sm font-medium text-[#0F172A]"
                      >
                        Interests
                      </label>
                      <input
                        id="interests"
                        type="text"
                        placeholder="e.g. street food, hiking, museums"
                        className="w-full px-4 py-3 rounded-lg border border-[#FCEAE1] bg-white text-[#0F172A] focus:ring-2 focus-ring-aurora focus:border-[#D97706] transition-colors"
                        autoComplete="additional-info"
                      />
                    </div>
                    <button
                      type="submit"
                      className="w-full btn-aurora-primary px-8 py-4 text-lg font-semibold"
                    >
                      Build my itinerary <ArrowRight className="size-5 ml-2" />
                    </button>
                  </form>
                </div>
              </div>
            </div>

            <div className="mt-16 flex items-center justify-center gap-4 animate-fade-up">
              <Link
                href="/chat"
                className="btn-aurora-primary inline-flex items-center gap-2 px-8 py-4 text-xl font-semibold"
              >
                Build my itinerary <ArrowRight className="size-5" />
              </Link>
              <Link
                href="/chat"
                className="btn-aurora-secondary inline-flex items-center gap-2 px-8 py-4 text-xl font-semibold"
              >
                Get started <ArrowRight className="size-5" />
              </Link>
            </div>
          </div>
        </section>

        {/* ========== 4. DESTINATIONS ========== */}
        <section id="destinations" className="py-24 sm:py-32 border-t border-[#FCEAE1] bg-[#FFF7ED]">
          <div className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-8">
            <div className="max-w-[720px] mx-auto text-center mb-20 sm:mb-28 animate-fade-up">
              <h2 className="font-heading text-3xl sm:text-[3rem] font-bold leading-[1.15] tracking-tight text-[#0F172A] text-balance">
                Every trip, more you
              </h2>
              <p className="mt-6 text-lg text-[#475569] leading-relaxed">
                Whether you&apos;re a budget traveler, digital nomad, family, or solo
                adventurer — Mindtrip adapts to how you travel.
              </p>
            </div>

            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
              {[
                {
                  title: "Budget travelers",
                  desc: "Affordable flights, hostels, local eats.",
                  icon: <Users className="size-5" />,
                  color: "text-orange-500 bg-orange-500/10",
                },
                {
                  title: "Luxury travelers",
                  desc: "Boutique hotels, fine dining, private experiences.",
                  icon: <Star className="size-5" />,
                  color: "text-[#0891B2] bg-[#0891B2]/10",
                },
                {
                  title: "Digital nomads",
                  desc: "Work-friendly stays, reliable Wi-Fi worldwide.",
                  icon: <Clock className="size-5" />,
                  color: "text-[#D97706] bg-[#D97706]/10",
                },
                {
                  title: "Families",
                  desc: "Kid-friendly activities, family suites.",
                  icon: <Heart className="size-5" />,
                  color: "text-orange-500 bg-orange-500/10",
                },
                {
                  title: "Solo adventurers",
                  desc: "Safe, social, off-the-beaten-path itineraries.",
                  icon: <Plane className="size-5" />,
                  color: "text-[#0891B2] bg-[#0891B2]/10",
                },
                {
                  title: "Foodies",
                  desc: "Hidden restaurants, local food tours.",
                  icon: <Leaf className="size-5" />,
                  color: "text-[#D97706] bg-[#D97706]/10",
                },
              ].map((item, idx) => (
                <a
                  key={item.title}
                  href="/chat"
                  className="card-aurora p-6 flex flex-col gap-3 group animate-fade-up"
                  style={{ animationDelay: `${idx * 80}ms` }}
                >
                  <div
                    className={`size-10 rounded-lg flex items-center justify-center ${item.color} group-hover:scale-110 transition-transform duration-300`}
                  >
                    {item.icon}
                  </div>
                  <h3 className="font-heading text-base font-semibold text-[#0F172A] group-hover:text-[#D97706] transition-colors duration-300">
                    {item.title}
                  </h3>
                  <p className="text-sm text-[#475569] leading-relaxed">
                    {item.desc}
                  </p>
                </a>
              ))}
            </div>
          </div>
        </section>

        {/* ========== 5. CLIMAX CTA ========== */}
        <section id="cta" className="py-32 sm:py-40 relative overflow-hidden">
          <div className="blob-gradient inset-0 absolute -z-10"></div>
          <div className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-8 py-24 sm:py-32 rounded-3xl border border-[#FCEAE1] bg-white shadow-2xl text-center animate-fade-up">
            <div className="absolute -top-4 -right-4 size-20 rounded-full bg-orange-500/10 blur-2xl"></div>
            <h2 className="font-heading text-3xl sm:text-[4rem] font-bold leading-[1.1] tracking-tight text-[#0F172A]">
              Ready to plan your next trip?
            </h2>
            <p className="mt-6 text-lg text-[#475569] leading-relaxed max-w-[60ch] mx-auto">
              Your AI travel assistant is waiting. Build your complete itinerary —
              flights, hotels, restaurants, and more — in minutes.
            </p>
            <div className="mt-12 flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/chat"
                className="btn-aurora-primary inline-flex items-center justify-center gap-2 px-8 py-4 text-xl font-semibold shadow-lg"
              >
                Build my itinerary <ArrowRight className="size-5" />
              </Link>
              <Link
                href="/chat"
                className="btn-aurora-secondary inline-flex items-center justify-center gap-2 px-8 py-4 text-xl font-semibold"
              >
                Get started <ArrowRight className="size-5" />
              </Link>
            </div>
          </div>
        </section>

        <hr className="border-[#FCEAE1] my-0" />
      </main>

      {/* Footer */}
      <footer className="border-t border-[#FCEAE1] bg-[#FFF7ED] py-12">
        <div className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-6 animate-fade-up">
            <div className="flex items-center gap-2">
              <Logo light={false} />
              <span className="font-heading text-sm font-semibold text-[#0F172A]">
                Mindtrip
              </span>
            </div>
            <nav className="flex flex-col sm:flex-row gap-4 sm:gap-8 text-sm">
              <Link
                href="#"
                className="text-[#475569] hover:text-[#D97706] transition-colors"
              >
                Privacy
              </Link>
              <Link
                href="#"
                className="text-[#475569] hover:text-[#D97706] transition-colors"
              >
                Terms
              </Link>
              <Link
                href="#"
                className="text-[#475569] hover:text-[#D97706] transition-colors"
              >
                Help
              </Link>
            </nav>
            <div className="mt-4 sm:mt-0 flex items-center gap-4">
              <a
                href="mailto:hello@mindtrip.ai"
                className="flex items-center gap-2 text-sm text-[#475569] hover:text-[#D97706] transition-colors"
              >
                <Mail className="size-4" /> hello@mindtrip.ai
              </a>
              <a
                href="tel:+15550100"
                className="flex items-center gap-2 text-sm text-[#475569] hover:text-[#D97706] transition-colors"
              >
                <Phone className="size-4" /> +1 (555) 0100
              </a>
            </div>
          </div>
          <p className="mt-8 sm:mt-6 text-center text-xs text-[#475569]">
            © 2026 Mindtrip. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}

// Placeholder — the real Header is rendered by layout.tsx
function HeaderPlaceholder() {
  return null;
}
