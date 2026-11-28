'use client';

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Search,
  MapPin,
  Calendar,
  Users,
  ChevronRight,
  ChevronLeft,
  Star,
  Sparkles,
  Plane,
  Building2,
  Utensils,
  Compass,
  ArrowRight,
  X,
  Menu,
  User,
  MessageSquare,
} from 'lucide-react';
import { api } from '@/lib/api';
import { AddToTripModal } from '@/components/common/AddToTripModal';

interface DestinationItem {
  id: string;
  title: string;
  cardTitle: string;
  locationCaption: string;
  country: string;
  airportCode: string;
  city: string;
  coordinates: [number, number];
  tagline: string;
  rating: number;
  reviews: string;
  priceFrom: string;
  bestTime: string;
  tags: string[];
  heroImage: string;
  cardImage: string;
  fallbackGradient: string;
}

interface FeaturedEat {
  id: string;
  name: string;
  destination: string;
  cuisine: string;
  priceTier: string;
  signatureDish: string;
  image: string;
  isLivePlace?: boolean;
}

const DESTINATIONS: DestinationItem[] = [
  {
    id: 'norway',
    title: 'Norway',
    cardTitle: 'Norway',
    locationCaption: 'Lofoten Islands, Norway',
    country: 'Norway',
    airportCode: 'BOO',
    city: 'Lofoten Islands',
    coordinates: [13.61, 68.15],
    tagline:
      'Dramatic fjords, crimson rorbuer cabins, and dancing aurora skies above Arctic waters.',
    rating: 5,
    reviews: '2.4k',
    priceFrom: '$1,240',
    bestTime: 'Sep – Mar',
    tags: ['Fjords', 'Northern Lights', 'Arctic'],
    heroImage:
      'https://images.unsplash.com/photo-1579033461380-adb47c3eb938?auto=format&fit=crop&w=2000&q=85',
    cardImage:
      'https://images.unsplash.com/photo-1579033461380-adb47c3eb938?auto=format&fit=crop&w=900&q=85',
    fallbackGradient: 'from-slate-900 via-blue-950 to-cyan-900',
  },
  {
    id: 'istanbul',
    title: 'Istanbul',
    cardTitle: 'Istanbul',
    locationCaption: 'Hagia Sophia, Istanbul, Turkey',
    country: 'Turkey',
    airportCode: 'IST',
    city: 'Istanbul',
    coordinates: [28.9784, 41.0082],
    tagline:
      'Where sunlit domes, Bosphorus ferries, and centuries of spice-market history meet.',
    rating: 5,
    reviews: '4.1k',
    priceFrom: '$890',
    bestTime: 'Apr – Oct',
    tags: ['Culture', 'Architecture', 'Culinary'],
    heroImage:
      'https://images.unsplash.com/photo-1524231757912-21f4fe3a7200?auto=format&fit=crop&w=2000&q=85',
    cardImage:
      'https://images.unsplash.com/photo-1524231757912-21f4fe3a7200?auto=format&fit=crop&w=800&q=80',
    fallbackGradient: 'from-amber-950 via-stone-900 to-blue-950',
  },
  {
    id: 'indonesia',
    title: 'Indonesia',
    cardTitle: 'Indonesia',
    locationCaption: 'Bali Rice Terraces, Indonesia',
    country: 'Indonesia',
    airportCode: 'DPS',
    city: 'Ubud, Bali',
    coordinates: [115.2625, -8.5069],
    tagline:
      'Emerald volcanic valleys, sacred temple springs, and misty morning jungle ridges.',
    rating: 5,
    reviews: '5.8k',
    priceFrom: '$960',
    bestTime: 'May – Sep',
    tags: ['Wellness', 'Jungle', 'Temples'],
    heroImage:
      'https://images.unsplash.com/photo-1537996194471-e657df975ab4?auto=format&fit=crop&w=2000&q=85',
    cardImage:
      'https://images.unsplash.com/photo-1537996194471-e657df975ab4?auto=format&fit=crop&w=800&q=80',
    fallbackGradient: 'from-emerald-950 via-teal-950 to-slate-900',
  },
  {
    id: 'himalayas',
    title: 'Himalayas',
    cardTitle: 'Mount Everest',
    locationCaption: 'Mount Everest, Nepal',
    country: 'Nepal',
    airportCode: 'KTM',
    city: 'Khumbu Valley',
    coordinates: [86.925, 27.9881],
    tagline:
      'High-altitude Sherpa trails, prayer-flag ridges, and crisp sunrise views over the roof of the world.',
    rating: 5,
    reviews: '1.9k',
    priceFrom: '$1,480',
    bestTime: 'Oct – Nov',
    tags: ['Trekking', 'Peaks', 'Expedition'],
    heroImage:
      'https://images.unsplash.com/photo-1544735716-392fe2489ffa?auto=format&fit=crop&w=2000&q=85',
    cardImage:
      'https://images.unsplash.com/photo-1544735716-392fe2489ffa?auto=format&fit=crop&w=800&q=80',
    fallbackGradient: 'from-sky-950 via-slate-900 to-indigo-950',
  },
  {
    id: 'egypt',
    title: 'Egypt',
    cardTitle: 'Egypt',
    locationCaption: 'Pyramids of Giza, Egypt',
    country: 'Egypt',
    airportCode: 'CAI',
    city: 'Giza & Cairo',
    coordinates: [31.1342, 29.9792],
    tagline:
      'Golden desert horizons, ancient limestone wonders, and twilight Nile felucca sails.',
    rating: 5,
    reviews: '3.6k',
    priceFrom: '$920',
    bestTime: 'Oct – Apr',
    tags: ['History', 'Desert', 'Nile'],
    heroImage:
      'https://images.unsplash.com/photo-1503177119275-0aa32b3a9368?auto=format&fit=crop&w=2000&q=85',
    cardImage:
      'https://images.unsplash.com/photo-1503177119275-0aa32b3a9368?auto=format&fit=crop&w=800&q=80',
    fallbackGradient: 'from-amber-950 via-orange-950 to-stone-900',
  },
  {
    id: 'sydney',
    title: 'Sydney',
    cardTitle: 'Sydney',
    locationCaption: 'Sydney Harbour, Australia',
    country: 'Australia',
    airportCode: 'SYD',
    city: 'Sydney',
    coordinates: [151.2153, -33.8568],
    tagline:
      'Sculptural white sails, coastal cliff walks, and sunlit Pacific coves.',
    rating: 5,
    reviews: '4.7k',
    priceFrom: '$1,350',
    bestTime: 'Sep – Nov',
    tags: ['Harbour', 'Coastal', 'Design'],
    heroImage:
      'https://images.unsplash.com/photo-1506973035872-a4ec16b8e8d9?auto=format&fit=crop&w=2000&q=85',
    cardImage:
      'https://images.unsplash.com/photo-1506973035872-a4ec16b8e8d9?auto=format&fit=crop&w=800&q=80',
    fallbackGradient: 'from-blue-950 via-cyan-950 to-slate-900',
  },
];

const POPULAR_WIDGET_DESTINATIONS = [
  { label: 'Kyoto', subtitle: 'Japan', airportCode: 'KIX' },
  { label: 'Paris', subtitle: 'France', airportCode: 'CDG' },
  { label: 'Rome', subtitle: 'Italy', airportCode: 'FCO' },
  { label: 'Dubai', subtitle: 'UAE', airportCode: 'DXB' },
  { label: 'Delhi', subtitle: 'India', airportCode: 'DEL' },
  { label: 'Istanbul', subtitle: 'Turkey', airportCode: 'IST' },
  { label: 'Bali', subtitle: 'Indonesia', airportCode: 'DPS' },
  { label: 'Sydney', subtitle: 'Australia', airportCode: 'SYD' },
];

const MOUNTAIN_BANNER_IMAGE =
  'https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=2200&q=85';

const FALLBACK_EATS: FeaturedEat[] = [
  {
    id: 'eat-1',
    name: 'Fiskekrogen Henningsvær',
    destination: 'Norway',
    cuisine: 'Arctic Seafood',
    priceTier: '$$$',
    signatureDish: 'Pan-Seared Skrei Cod & King Crab Bisque',
    image:
      'https://images.unsplash.com/photo-1559339352-11d035aa65de?auto=format&fit=crop&w=900&q=80',
  },
  {
    id: 'eat-2',
    name: 'Karaköy Lokantası',
    destination: 'Istanbul',
    cuisine: 'Modern Ottoman & Meze',
    priceTier: '$$$',
    signatureDish: 'Charred Octopus, Sour Cherry Yaprak Sarma & Sea Bass',
    image:
      'https://images.unsplash.com/photo-1544148103-0773bf10d330?auto=format&fit=crop&w=900&q=80',
  },
];

const AI_PRESET_PROMPTS: string[] = [
  'Plan a 3-day food tour in Rome',
  'Romantic long weekend in Paris',
  '3 days in Kyoto temples & tea',
  '5 quiet days in the Swiss Alps',
  'Plan 4 days in Dubai with desert safari',
];

function MindtripLogo({ className = '' }: { className?: string }) {
  return (
    <div className={`flex items-center gap-2.5 select-none ${className}`}>
      <div className="relative flex items-center justify-center w-9 h-9 rounded-xl bg-white/15 backdrop-blur-md border border-white/30 shadow-sm">
        <svg
          viewBox="0 0 36 36"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="w-6 h-6 text-white"
        >
          <circle
            cx="18"
            cy="18"
            r="12"
            stroke="currentColor"
            strokeWidth="2"
            strokeOpacity="0.9"
          />
          <path
            d="M6.5 18H29.5"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeOpacity="0.55"
            strokeLinecap="round"
          />
          <path
            d="M18 6C21.5 9.8 23.2 13.8 23.2 18C23.2 22.2 21.5 26.2 18 30"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeOpacity="0.55"
            strokeLinecap="round"
          />
          <path
            d="M8.5 21.5C13.5 19.5 20.5 15.2 28.5 9.5C24.2 15.8 19.8 19.5 15.5 21.8L18.2 24.5L13.2 23.4L8.5 21.5Z"
            fill="currentColor"
          />
        </svg>
      </div>
      <span
        className="text-[23px] sm:text-[24px] font-bold tracking-tight text-white"
        style={{ fontFamily: "'Outfit', sans-serif" }}
      >
        mindtrip
      </span>
    </div>
  );
}

export default function MindtripPage() {
  const router = useRouter();
  const [isScrolledPastHero, setIsScrolledPastHero] = useState<boolean>(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState<boolean>(false);

  // Hero Carousel State
  const [activeDestIndex, setActiveDestIndex] = useState<number>(0);
  const [heroAutoPlay, setHeroAutoPlay] = useState<boolean>(true);

  // Overlapping Search Widget State
  const [bookingTab, setBookingTab] = useState<'hotels' | 'flights'>('hotels');
  const [flightOrigin, setFlightOrigin] = useState<string>('DEL');
  const [searchDestination, setSearchDestination] = useState<string>('Kyoto');
  const [checkInDate, setCheckInDate] = useState<string>(() => {
    const d = new Date();
    d.setDate(d.getDate() + 14);
    return d.toISOString().split('T')[0];
  });
  const [checkOutDate, setCheckOutDate] = useState<string>(() => {
    const d = new Date();
    d.setDate(d.getDate() + 18);
    return d.toISOString().split('T')[0];
  });
  const [guestCount, setGuestCount] = useState<number>(2);
  const [showGuestPopover, setShowGuestPopover] = useState<boolean>(false);
  const [showDestDropdown, setShowDestDropdown] = useState<boolean>(false);

  // Global Quick Search Modal State
  const [quickSearchOpen, setQuickSearchOpen] = useState<boolean>(false);
  const [quickSearchQuery, setQuickSearchQuery] = useState<string>('');

  // Live backend hydration for Culinary Picks & Trips preview
  const [featuredEats, setFeaturedEats] = useState<FeaturedEat[]>(FALLBACK_EATS);
  const [addToTripPlace, setAddToTripPlace] = useState<any | null>(null);
  const [trips, setTrips] = useState<any[]>([]);

  const heroSectionRef = useRef<HTMLElement | null>(null);
  const exploreSectionRef = useRef<HTMLElement | null>(null);
  const searchWidgetRef = useRef<HTMLDivElement | null>(null);
  const [exploreAnimKey, setExploreAnimKey] = useState<number>(0);
  const [exploreVisible, setExploreVisible] = useState<boolean>(false);
  const [widgetAnimKey, setWidgetAnimKey] = useState<number>(0);

  const activeDestination = DESTINATIONS[activeDestIndex];

  // Hydrate real trips & eats from FastAPI backend via Next.js /api proxy
  useEffect(() => {
    let mounted = true;
    async function loadHomeData() {
      try {
        const tripsRes = await api('/trips?limit=6');
        const tripsJson = await tripsRes.json();
        if (mounted && Array.isArray(tripsJson.trips)) {
          setTrips(tripsJson.trips);
        }
      } catch {
        // Gracefully ignore if backend is offline
      }

      try {
        const eatsRes = await api('/eats?limit=4&auto_scrape=false');
        const eatsJson = await eatsRes.json();
        if (mounted && Array.isArray(eatsJson.eats) && eatsJson.eats.length > 0) {
          const mapped: FeaturedEat[] = eatsJson.eats.slice(0, 2).map((e: any) => ({
            id: String(e.id),
            name: e.name,
            destination: e.destination || e.city || 'Curated',
            cuisine: e.category ? String(e.category).toUpperCase() : 'DINING',
            priceTier: e.price_range || (e.price_level ? '$'.repeat(Math.min(4, e.price_level)) : '$$'),
            signatureDish: e.description || e.address || 'Local culinary favorite',
            image:
              (Array.isArray(e.photos) && e.photos[0]) ||
              'https://images.unsplash.com/photo-1559339352-11d035aa65de?auto=format&fit=crop&w=900&q=80',
            isLivePlace: true,
          }));
          setFeaturedEats(mapped);
        }
      } catch {
        // Fallback to curated eats preview
      }
    }
    loadHomeData();
    return () => {
      mounted = false;
    };
  }, []);

  // Inject animations cleanly
  useEffect(() => {
    const style = document.createElement('style');
    style.textContent = `
      @keyframes heroFadeSlideUp {
        0% { opacity: 0; transform: translateY(22px); filter: blur(4px); }
        100% { opacity: 1; transform: translateY(0); filter: blur(0); }
      }
      @keyframes heroBadgeFadeIn {
        0% { opacity: 0; transform: translateX(16px); }
        100% { opacity: 1; transform: translateX(0); }
      }
      @keyframes sectionRevealUp {
        0% { opacity: 0; transform: translateY(34px) scale(0.985); filter: blur(4px); }
        100% { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
      }
      @keyframes plateReveal {
        0% { opacity: 0; transform: translateY(36px) scale(0.96); }
        100% { opacity: 1; transform: translateY(0) scale(1); }
      }
      @keyframes slideFromLeft {
        0% { opacity: 0; transform: translateX(-28px); }
        100% { opacity: 1; transform: translateX(0); }
      }
      @keyframes slideFromRight {
        0% { opacity: 0; transform: translateX(28px); }
        100% { opacity: 1; transform: translateX(0); }
      }
      @keyframes slideFromTop {
        0% { opacity: 0; transform: translateY(-22px); }
        100% { opacity: 1; transform: translateY(0); }
      }
      @keyframes slideFromBottom {
        0% { opacity: 0; transform: translateY(22px); }
        100% { opacity: 1; transform: translateY(0); }
      }
      @keyframes microPulseRing {
        0% { box-shadow: 0 0 0 0 rgba(25, 88, 158, 0.28); }
        100% { box-shadow: 0 0 0 10px rgba(25, 88, 158, 0); }
      }
      @keyframes iconFloatHop {
        0%, 100% { transform: translateY(0) scale(1); }
        45% { transform: translateY(-4px) scale(1.14); }
      }
      @keyframes starTwinkle {
        0%, 100% { transform: scale(1) rotate(0deg); }
        50% { transform: scale(1.24) rotate(12deg); }
      }
      @keyframes bubblePop {
        0%, 100% { transform: scale(1) rotate(0deg); }
        40% { transform: scale(1.18) rotate(-8deg); }
        75% { transform: scale(0.96) rotate(4deg); }
      }
      @keyframes heroCardGlossSweep {
        0% { transform: translateX(-140%) skewX(-22deg); }
        100% { transform: translateX(240%) skewX(-22deg); }
      }
      @keyframes autoProgressFill {
        0% { stroke-dashoffset: 113.1; }
        100% { stroke-dashoffset: 0; }
      }
      @keyframes sheenSweep {
        0% { transform: translateX(-120%) skewX(-20deg); }
        100% { transform: translateX(220%) skewX(-20deg); }
      }
      .hero-deck-stage { perspective: 1250px; transform-style: preserve-3d; }
      .hero-deck-card { transform-origin: 50% 115%; will-change: transform, opacity, filter; }
      .animate-hero-eyebrow { animation: heroFadeSlideUp 0.75s cubic-bezier(0.22, 1, 0.36, 1) forwards; }
      .animate-hero-title { animation: heroFadeSlideUp 0.85s cubic-bezier(0.22, 1, 0.36, 1) 0.08s both; }
      .animate-hero-desc { animation: heroFadeSlideUp 0.9s cubic-bezier(0.22, 1, 0.36, 1) 0.16s both; }
      .animate-hero-cta { animation: heroFadeSlideUp 0.95s cubic-bezier(0.22, 1, 0.36, 1) 0.24s both; }
      .animate-hero-location { animation: heroBadgeFadeIn 0.85s cubic-bezier(0.22, 1, 0.36, 1) 0.14s both; }
      .animate-reveal-banner { animation: sectionRevealUp 0.85s cubic-bezier(0.22, 1, 0.36, 1) 0.05s both; }
      .animate-reveal-header { animation: sectionRevealUp 0.85s cubic-bezier(0.22, 1, 0.36, 1) 0.3s both; }
      .animate-reveal-card { animation: sectionRevealUp 0.85s cubic-bezier(0.22, 1, 0.36, 1) var(--stagger-delay, 0.35s) both; }
      .animate-widget-plate { animation: plateReveal 0.65s cubic-bezier(0.22, 1, 0.36, 1) 0.05s both; }
      .animate-widget-tabs { animation: slideFromTop 0.6s cubic-bezier(0.22, 1, 0.36, 1) 0.25s both; }
      .animate-widget-pills { animation: slideFromRight 0.6s cubic-bezier(0.22, 1, 0.36, 1) 0.32s both; }
      .animate-widget-col-1 { animation: slideFromLeft 0.6s cubic-bezier(0.22, 1, 0.36, 1) 0.38s both; }
      .animate-widget-col-2 { animation: slideFromBottom 0.6s cubic-bezier(0.22, 1, 0.36, 1) 0.48s both; }
      .animate-widget-col-3 { animation: slideFromTop 0.6s cubic-bezier(0.22, 1, 0.36, 1) 0.58s both; }
      .animate-widget-col-4 { animation: slideFromBottom 0.6s cubic-bezier(0.22, 1, 0.36, 1) 0.68s both; }
      .animate-widget-cta { animation: slideFromRight 0.65s cubic-bezier(0.22, 1, 0.36, 1) 0.78s both; }
      .btn-micro {
        position: relative;
        overflow: hidden;
        transition: transform 0.25s cubic-bezier(0.22, 1, 0.36, 1),
                    box-shadow 0.25s cubic-bezier(0.22, 1, 0.36, 1),
                    background-color 0.25s ease,
                    border-color 0.25s ease;
      }
      .btn-micro:hover { transform: translateY(-2px); }
      .btn-micro:active { transform: scale(0.96) translateY(0); }
      .btn-micro::after {
        content: '';
        position: absolute;
        top: 0; left: 0; width: 45%; height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.24), transparent);
        transform: translateX(-140%) skewX(-20deg);
        pointer-events: none;
      }
      .btn-micro:hover::after { animation: sheenSweep 0.75s cubic-bezier(0.22, 1, 0.36, 1); }
      .card-micro {
        transition: transform 0.38s cubic-bezier(0.22, 1, 0.36, 1),
                    box-shadow 0.38s cubic-bezier(0.22, 1, 0.36, 1),
                    border-color 0.3s ease;
      }
      .card-micro:hover {
        transform: translateY(-6px);
        box-shadow: 0 22px 38px -12px rgba(24, 40, 72, 0.14);
        border-color: rgba(25, 88, 158, 0.35);
      }
      .card-micro:active { transform: translateY(-2px) scale(0.992); }
      .ui-field-micro {
        position: relative;
        transition: transform 0.28s cubic-bezier(0.34, 1.56, 0.64, 1),
                    background-color 0.25s ease,
                    box-shadow 0.28s ease;
      }
      .ui-field-micro:hover, .ui-field-micro:focus-within {
        transform: translateY(-2px);
        background-color: rgba(245, 247, 250, 0.95);
        box-shadow: 0 8px 18px -10px rgba(24, 40, 72, 0.22);
      }
      .ui-field-micro:hover .ui-icon-micro, .ui-field-micro:focus-within .ui-icon-micro {
        animation: iconFloatHop 0.55s cubic-bezier(0.34, 1.56, 0.64, 1);
        color: #182848;
      }
      .ui-pill-micro {
        transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1),
                    box-shadow 0.28s ease,
                    border-color 0.25s ease,
                    background-color 0.25s ease;
      }
      .ui-pill-micro:hover {
        transform: translateY(-3px) scale(1.03);
        box-shadow: 0 10px 20px -8px rgba(24, 40, 72, 0.2);
        border-color: rgba(25, 88, 158, 0.45);
      }
      .ui-pill-micro:active { transform: scale(0.95); }
      .ui-pill-micro:hover .ui-pill-icon { animation: iconFloatHop 0.5s cubic-bezier(0.34, 1.56, 0.64, 1); }
      .ui-cta-spring {
        transition: transform 0.32s cubic-bezier(0.34, 1.56, 0.64, 1),
                    background-color 0.25s ease,
                    box-shadow 0.32s ease;
      }
      .ui-cta-spring:hover {
        transform: translateY(-3px) scale(1.015);
        box-shadow: 0 14px 24px -8px rgba(24, 40, 72, 0.35);
      }
      .ui-cta-spring:active { transform: scale(0.96); animation: microPulseRing 0.45s ease-out; }
      .hero-star-micro { transition: transform 0.28s cubic-bezier(0.34, 1.56, 0.64, 1); }
      .hero-location-card:hover .hero-star-micro { animation: starTwinkle 0.55s cubic-bezier(0.34, 1.56, 0.64, 1) both; }
      .hero-location-card:hover .hero-star-micro:nth-child(2) { animation-delay: 0.05s; }
      .hero-location-card:hover .hero-star-micro:nth-child(3) { animation-delay: 0.1s; }
      .hero-location-card:hover .hero-star-micro:nth-child(4) { animation-delay: 0.15s; }
      .hero-location-card:hover .hero-star-micro:nth-child(5) { animation-delay: 0.2s; }
      .hero-gonow-btn:hover .hero-bubble-icon { animation: bubblePop 0.55s cubic-bezier(0.34, 1.56, 0.64, 1); }
      .hero-fan-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; width: 48%; height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.28), transparent);
        transform: translateX(-150%) skewX(-22deg);
        z-index: 15;
        pointer-events: none;
      }
      .hero-fan-card:hover::before { animation: heroCardGlossSweep 0.85s cubic-bezier(0.22, 1, 0.36, 1); }
      .hero-auto-ring { stroke-dasharray: 113.1; animation: autoProgressFill 4000ms linear infinite; }
    `;
    document.head.appendChild(style);
    return () => {
      style.remove();
    };
  }, []);

  // Scroll listener for translucent-to-solid top nav bar
  useEffect(() => {
    const handleScroll = () => {
      if (heroSectionRef.current) {
        const heroHeight = heroSectionRef.current.offsetHeight;
        setIsScrolledPastHero(window.scrollY > heroHeight * 0.72);
      }
    };
    handleScroll();
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Observe daytime mountain & popular destination section on scroll
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setExploreVisible(true);
          }
        });
      },
      { threshold: 0.12 }
    );
    if (exploreSectionRef.current) {
      observer.observe(exploreSectionRef.current);
    }
    return () => observer.disconnect();
  }, []);

  // Replay search widget choreographed animation every time user scrolls into it
  useEffect(() => {
    const widgetObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setWidgetAnimKey((prev) => prev + 1);
          }
        });
      },
      { threshold: 0.25 }
    );
    if (searchWidgetRef.current) {
      widgetObserver.observe(searchWidgetRef.current);
    }
    return () => widgetObserver.disconnect();
  }, []);

  // Auto-advance hero carousel every 4 seconds
  useEffect(() => {
    if (!heroAutoPlay) return;
    const timer = setInterval(() => {
      setActiveDestIndex((prev) => (prev + 1) % DESTINATIONS.length);
    }, 4000);
    return () => clearInterval(timer);
  }, [heroAutoPlay]);

  const handleGoNowScroll = () => {
    setSearchDestination(activeDestination.title);
    setExploreVisible(true);
    setExploreAnimKey((prev) => prev + 1);

    if (exploreSectionRef.current) {
      const headerOffset = 68;
      const elementPosition =
        exploreSectionRef.current.getBoundingClientRect().top + window.scrollY;
      window.scrollTo({
        top: elementPosition - headerOffset,
        behavior: 'smooth',
      });
    }
  };

  const launchAiPlannerWithPrompt = (promptText: string) => {
    router.push(`/chat?q=${encodeURIComponent(promptText)}`);
  };

  const handleWidgetSearch = () => {
    const dest = searchDestination.trim() || 'Kyoto';
    if (bookingTab === 'hotels') {
      const params = new URLSearchParams({
        destination: dest,
        check_in: checkInDate,
        check_out: checkOutDate,
        adults: String(guestCount),
        auto_search: '1',
      });
      router.push(`/stays?${params.toString()}`);
    } else {
      const params = new URLSearchParams({
        origin: flightOrigin.trim() || 'DEL',
        destination: dest,
        date: checkInDate,
        return_date: checkOutDate,
        adults: String(guestCount),
        auto_search: '1',
      });
      router.push(`/flights?${params.toString()}`);
    }
  };

  const navLinks = [
    { href: '/stays', label: 'Hotels' },
    { href: '/flights', label: 'Flights' },
    { href: '/eats', label: 'Eats' },
    { href: '/experiences', label: 'Experiences' },
    { href: '/chat', label: 'AI Chat' },
    { href: '/trips', label: 'Trips', badge: trips.length },
  ];

  const featuredTrip = trips[0] || null;
  const featuredTripStops =
    featuredTrip?.days?.[0]?.stops?.slice(0, 2) || [];

  return (
    <div
      className="min-h-screen bg-[#F5F7FA] text-[#182848] antialiased selection:bg-[#19589E] selection:text-white"
      style={{ fontFamily: "'Work Sans', sans-serif" }}
    >
      {/* TOP NAVIGATION BAR */}
      <header
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
          isScrolledPastHero
            ? 'bg-[#182848]/85 backdrop-blur-md border-b border-white/15 shadow-lg shadow-[#182848]/20 py-3.5'
            : 'bg-gradient-to-b from-black/55 via-black/25 to-transparent py-5'
        }`}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between gap-4">
          <Link
            href="/"
            className="focus:outline-none group transition-transform duration-200 hover:scale-[1.02]"
            aria-label="mindtrip Home"
          >
            <MindtripLogo />
          </Link>

          <nav
            className="hidden md:flex items-center gap-1.5 lg:gap-2"
            style={{ fontFamily: "'Outfit', sans-serif" }}
          >
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="relative px-3.5 py-2 rounded-full text-[15px] lg:text-[16px] font-semibold text-white/90 hover:text-white hover:bg-white/12 transition-all duration-200 flex items-center gap-1.5"
              >
                <span>{link.label}</span>
                {link.badge !== undefined && link.badge > 0 && (
                  <span className="ml-0.5 px-1.5 py-0.5 text-[11px] font-bold rounded-full bg-amber-400 text-[#182848]">
                    {link.badge}
                  </span>
                )}
              </Link>
            ))}
          </nav>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setQuickSearchOpen(true)}
              className="flex items-center justify-between w-40 sm:w-52 lg:w-56 px-4 py-2 rounded-full bg-black/30 hover:bg-black/45 border border-white/25 backdrop-blur-md text-white/90 text-[15px] transition-all duration-200 group"
            >
              <span className="truncate">Ask AI / Search</span>
              <Search className="w-4 h-4 text-white/80 group-hover:text-white transition-colors" />
            </button>

            <Link
              href="/trips"
              title="Your Saved Trips"
              className="w-9 h-9 rounded-full bg-white/15 hover:bg-white/25 border border-white/30 backdrop-blur-md flex items-center justify-center text-white transition-all"
            >
              <User className="w-4 h-4" />
            </Link>

            <button
              type="button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-2 rounded-xl bg-white/15 text-white hover:bg-white/25"
              aria-label="Toggle Menu"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {mobileMenuOpen && (
          <div className="md:hidden bg-[#182848]/95 backdrop-blur-md border-t border-white/15 px-4 pt-3 pb-5 space-y-1.5 shadow-xl">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMobileMenuOpen(false)}
                className="w-full flex items-center justify-between px-4 py-3 rounded-xl text-left text-base font-semibold text-white/85 hover:bg-white/10"
              >
                <span>{link.label}</span>
                {link.badge !== undefined && link.badge > 0 && (
                  <span className="px-2 py-0.5 text-xs font-bold rounded-full bg-amber-400 text-[#182848]">
                    {link.badge} trips
                  </span>
                )}
              </Link>
            ))}
          </div>
        )}
      </header>

      <main>
        {/* SECTION A: INTERACTIVE DESTINATION SHOWCASE HERO */}
        <section
          ref={heroSectionRef}
          className="relative w-full min-h-[780px] h-screen max-h-[960px] overflow-hidden bg-[#0F172A] select-none"
        >
          {DESTINATIONS.map((dest, idx) => {
            const isCurrent = idx === activeDestIndex;
            return (
              <div
                key={dest.id}
                className={`absolute inset-0 transition-all duration-[1200ms] ease-out ${
                  isCurrent ? 'opacity-100 scale-100' : 'opacity-0 scale-105'
                }`}
                style={{ transitionProperty: 'opacity, transform' }}
              >
                <div className={`w-full h-full bg-gradient-to-br ${dest.fallbackGradient}`}>
                  <img
                    src={dest.heroImage}
                    alt={dest.locationCaption}
                    className="w-full h-full object-cover object-center"
                  />
                </div>
                <div className="absolute inset-0 bg-gradient-to-r from-black/70 via-black/35 to-black/30" />
                <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-transparent to-black/30" />
              </div>
            );
          })}

          <div className="relative z-10 max-w-7xl mx-auto h-full px-4 sm:px-6 lg:px-8 pt-28 pb-10 flex flex-col justify-between">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start my-auto pt-4">
              <div
                key={`hero-left-${activeDestination.id}`}
                className="lg:col-span-7 space-y-5"
              >
                <div className="animate-hero-eyebrow inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white/12 border border-white/25 backdrop-blur-md text-white/90 text-xs font-semibold tracking-wider uppercase">
                  <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                  <span>AI-Curated Destination Showcase</span>
                </div>

                <h1
                  className="animate-hero-title text-5xl sm:text-6xl lg:text-[74px] font-extrabold text-white tracking-tight leading-[1.03] drop-shadow-sm"
                  style={{ fontFamily: "'Outfit', sans-serif" }}
                >
                  {activeDestination.title}
                </h1>

                <p className="animate-hero-desc max-w-xl text-base sm:text-lg text-white/85 leading-relaxed font-normal">
                  {activeDestination.tagline}
                </p>

                <div className="animate-hero-cta pt-2 flex flex-wrap items-center gap-4">
                  <button
                    type="button"
                    onClick={handleGoNowScroll}
                    className="hero-gonow-btn btn-micro group relative inline-flex items-center gap-3 px-7 py-3.5 rounded-2xl bg-white/14 hover:bg-white text-white hover:text-[#182848] border-[1.5px] border-white/80 backdrop-blur-md font-semibold text-base shadow-lg shadow-black/25 transition-all duration-300"
                  >
                    <span>Go Now</span>
                    <span className="hero-bubble-icon relative flex items-center justify-center w-6 h-6 rounded-full bg-white/20 group-hover:bg-[#19589E] group-hover:text-white transition-colors">
                      <MessageSquare className="w-3.5 h-3.5" />
                    </span>
                  </button>

                  <button
                    type="button"
                    onClick={() =>
                      launchAiPlannerWithPrompt(
                        `Plan a 4-day trip to ${activeDestination.title} (${activeDestination.locationCaption})`
                      )
                    }
                    className="group/ai inline-flex items-center gap-2 px-5 py-3.5 rounded-2xl text-white/85 hover:text-white text-sm font-medium hover:bg-white/10 transition-all active:scale-95"
                  >
                    <span>Plan with AI ({activeDestination.priceFrom})</span>
                    <ArrowRight className="w-4 h-4 transition-transform duration-300 group-hover/ai:translate-x-1.5" />
                  </button>
                </div>
              </div>

              <div
                key={`hero-right-${activeDestination.id}`}
                className="animate-hero-location lg:col-span-5 flex flex-col lg:items-end justify-center lg:pt-8"
              >
                <div className="hero-location-card group/loc inline-flex flex-col lg:items-end bg-black/25 hover:bg-black/35 backdrop-blur-md border border-white/15 hover:border-amber-300/40 rounded-2xl px-5 py-3.5 transition-all duration-300 hover:-translate-y-0.5">
                  <div className="flex items-center gap-1 mb-1.5">
                    {[...Array(5)].map((_, i) => (
                      <Star
                        key={i}
                        className="hero-star-micro w-4 h-4 fill-[#F59E0B] text-[#F59E0B]"
                      />
                    ))}
                  </div>
                  <div className="flex items-center gap-1.5 text-white font-medium text-sm sm:text-base">
                    <MapPin className="w-4 h-4 text-amber-400 shrink-0 transition-transform duration-300 group-hover/loc:-translate-y-1 group-hover/loc:scale-110" />
                    <span>{activeDestination.locationCaption}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Bottom Controls + Overlapped Fanned Card Deck */}
            <div className="relative w-full pt-4 pb-4 flex flex-col lg:flex-row items-center justify-between gap-6">
              <div className="flex items-center gap-3 order-2 lg:order-1">
                <button
                  type="button"
                  onClick={() => {
                    setHeroAutoPlay(false);
                    setActiveDestIndex(
                      (prev) => (prev - 1 + DESTINATIONS.length) % DESTINATIONS.length
                    );
                  }}
                  className="group/prev relative w-11 h-11 rounded-full bg-white/15 hover:bg-white/30 border border-white/30 backdrop-blur-md flex items-center justify-center text-white transition-all duration-200 hover:scale-105 active:scale-90"
                  aria-label="Previous Destination"
                >
                  <ChevronLeft className="w-5 h-5 transition-transform duration-200 group-hover/prev:-translate-x-0.5" />
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setHeroAutoPlay(false);
                    setActiveDestIndex((prev) => (prev + 1) % DESTINATIONS.length);
                  }}
                  className="group/next relative w-11 h-11 rounded-full bg-white/15 hover:bg-white/30 border border-white/30 backdrop-blur-md flex items-center justify-center text-white transition-all duration-200 hover:scale-105 active:scale-90"
                  aria-label="Next Destination"
                >
                  {heroAutoPlay && (
                    <svg
                      key={`ring-${activeDestIndex}`}
                      viewBox="0 0 44 44"
                      className="pointer-events-none absolute inset-0 w-full h-full -rotate-90"
                    >
                      <circle
                        cx="22"
                        cy="22"
                        r="18"
                        fill="none"
                        stroke="#FBBF24"
                        strokeWidth="2"
                        strokeLinecap="round"
                        className="hero-auto-ring"
                      />
                    </svg>
                  )}
                  <ChevronRight className="w-5 h-5 transition-transform duration-200 group-hover/next:translate-x-0.5" />
                </button>
                <span className="ml-2 text-xs font-semibold tracking-widest text-white/75 uppercase">
                  0{activeDestIndex + 1} / 0{DESTINATIONS.length}
                </span>
              </div>

              <div className="hero-deck-stage relative flex items-center justify-center h-[285px] sm:h-[325px] w-full lg:w-[64%] lg:ml-auto lg:mr-4 order-1 lg:order-2 overflow-visible">
                <div className="relative w-full h-full flex items-center justify-center">
                  {DESTINATIONS.map((dest, idx) => {
                    const total = DESTINATIONS.length;
                    let offset = idx - activeDestIndex;
                    if (offset > total / 2) offset -= total;
                    if (offset < -total / 2) offset += total;

                    if (Math.abs(offset) > 2) return null;

                    const absOffset = Math.abs(offset);
                    const isCenter = offset === 0;
                    const rotateZDeg = offset * 8;
                    const rotateYDeg = offset * -5;
                    const translateX = offset * 92;
                    const translateY = absOffset === 0 ? -6 : absOffset === 1 ? 8 : 22;
                    const translateZ = isCenter ? 60 : -absOffset * 35;
                    const scaleVal = isCenter ? 1.08 : 1 - absOffset * 0.08;
                    const zIndex = isCenter ? 50 : 30 - absOffset * 10;

                    return (
                      <button
                        key={dest.id}
                        type="button"
                        onClick={() => {
                          setHeroAutoPlay(false);
                          setActiveDestIndex(idx);
                        }}
                        style={{
                          transform: `translate3d(${translateX}px, ${translateY}px, ${translateZ}px) rotateZ(${rotateZDeg}deg) rotateY(${rotateYDeg}deg) scale(${scaleVal})`,
                          zIndex,
                          filter: isCenter
                            ? 'brightness(1.04)'
                            : `brightness(${0.86 - absOffset * 0.1})`,
                          transitionProperty: 'transform, opacity, box-shadow, filter',
                          transitionDuration: '850ms',
                          transitionTimingFunction: 'cubic-bezier(0.22, 1, 0.36, 1)',
                        }}
                        className={`hero-deck-card hero-fan-card group absolute w-[164px] sm:w-[190px] h-[224px] sm:h-[262px] rounded-[22px] overflow-hidden focus:outline-none active:scale-95 ${
                          isCenter
                            ? 'ring-2 ring-white shadow-[0_30px_60px_-12px_rgba(0,0,0,0.85)]'
                            : 'ring-1 ring-white/40 opacity-95 hover:opacity-100 shadow-[0_18px_36px_-14px_rgba(0,0,0,0.68)]'
                        }`}
                      >
                        <div className={`w-full h-full bg-gradient-to-b ${dest.fallbackGradient}`}>
                          <img
                            src={dest.cardImage}
                            alt={dest.cardTitle}
                            className="w-full h-full object-cover group-hover:scale-108 transition-transform duration-700 ease-out"
                          />
                        </div>
                        <div className="absolute inset-0 rounded-[24px] ring-1 ring-inset ring-white/30 pointer-events-none" />
                        <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/15 to-white/10" />
                        <div
                          className={`absolute inset-x-0 px-3 text-center transition-all duration-300 group-hover:-translate-y-1 ${
                            isCenter ? 'bottom-5' : 'bottom-4'
                          }`}
                        >
                          <span
                            style={{ fontFamily: "'Outfit', sans-serif" }}
                            className={`text-white font-bold tracking-tight drop-shadow ${
                              isCenter ? 'text-[17px] sm:text-[20px]' : 'text-[15px] sm:text-[17px]'
                            }`}
                          >
                            {dest.cardTitle}
                          </span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* SECTION B: DAYTIME MOUNTAIN BANNER & OVERLAPPING SEARCH WIDGET */}
        <section ref={exploreSectionRef} className="relative">
          <div className="relative h-[430px] sm:h-[470px] w-full overflow-hidden bg-sky-900">
            <img
              src={MOUNTAIN_BANNER_IMAGE}
              alt="Snow-capped mountain peaks above clouds"
              className="w-full h-full object-cover object-center"
            />
            <div className="absolute inset-0 bg-gradient-to-r from-[#0F294A]/75 via-[#19589E]/40 to-transparent" />
            <div className="absolute inset-0 bg-gradient-to-t from-black/40 via-transparent to-black/15" />

            <div
              key={`banner-text-${exploreAnimKey}`}
              className="relative z-10 max-w-7xl mx-auto h-full px-4 sm:px-6 lg:px-8 flex flex-col justify-center pb-16 animate-reveal-banner"
            >
              <span className="inline-flex items-center gap-2 w-fit px-3.5 py-1.5 rounded-full bg-white/20 backdrop-blur-md border border-white/30 text-white text-xs font-semibold uppercase tracking-wider mb-4">
                <Sparkles className="w-3.5 h-3.5 text-amber-300" />
                <span>Seamless Global Booking</span>
              </span>
              <h2
                className="max-w-2xl text-3xl sm:text-5xl lg:text-[52px] font-extrabold text-white leading-[1.12] tracking-tight drop-shadow-sm"
                style={{ fontFamily: "'Outfit', sans-serif" }}
              >
                It&apos;s A Big World Out There, Go Explore.
              </h2>
              <p className="max-w-xl text-sm sm:text-base text-white/90 mt-3 leading-relaxed">
                Search live hotels, real-time Google Flights, curated dining, and
                AI-crafted multi-day itineraries with interactive maps.
              </p>
            </div>
          </div>

          {/* Overlapping Search Widget */}
          <div
            ref={searchWidgetRef}
            key={`search-widget-${exploreAnimKey}-${widgetAnimKey}`}
            className="relative z-20 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 -mt-24 sm:-mt-28"
          >
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div className="relative inline-flex items-center bg-white rounded-t-[16px] p-1.5 shadow-sm border-t border-x border-slate-200/80 animate-widget-tabs">
                <span
                  aria-hidden="true"
                  style={{
                    transform:
                      bookingTab === 'hotels' ? 'translateX(0%)' : 'translateX(100%)',
                  }}
                  className="pointer-events-none absolute top-1.5 left-1.5 w-[calc(50%-6px)] h-[calc(100%-12px)] rounded-[12px] bg-[#182848] shadow-md shadow-[#182848]/25 transition-transform duration-300 ease-[cubic-bezier(0.34,1.56,0.64,1)]"
                />

                <button
                  type="button"
                  onClick={() => setBookingTab('hotels')}
                  className={`relative z-10 group flex items-center justify-center gap-2 px-5 py-2.5 rounded-[12px] text-sm font-semibold transition-colors duration-250 active:scale-95 ${
                    bookingTab === 'hotels'
                      ? 'text-white'
                      : 'text-[#182848]/75 hover:text-[#182848]'
                  }`}
                >
                  <Building2
                    className={`w-4 h-4 transition-transform duration-300 ${
                      bookingTab === 'hotels'
                        ? 'scale-110 text-amber-300'
                        : 'group-hover:scale-110 group-hover:-rotate-6'
                    }`}
                  />
                  <span>Hotels</span>
                </button>

                <button
                  type="button"
                  onClick={() => setBookingTab('flights')}
                  className={`relative z-10 group flex items-center justify-center gap-2 px-5 py-2.5 rounded-[12px] text-sm font-semibold transition-colors duration-250 active:scale-95 ${
                    bookingTab === 'flights'
                      ? 'text-white'
                      : 'text-[#182848]/75 hover:text-[#182848]'
                  }`}
                >
                  <Plane
                    className={`w-4 h-4 transition-transform duration-300 ${
                      bookingTab === 'flights'
                        ? 'scale-110 translate-x-0.5 -translate-y-0.5 text-amber-300'
                        : 'group-hover:translate-x-0.5 group-hover:-translate-y-0.5'
                    }`}
                  />
                  <span>Flights</span>
                </button>
              </div>

              <div className="hidden md:flex items-center gap-2 pb-2 animate-widget-pills">
                <Link
                  href="/eats"
                  className="ui-pill-micro btn-micro group inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-white/95 hover:bg-white text-[#182848] text-xs font-semibold shadow-sm border border-slate-200/70"
                >
                  <Utensils className="ui-pill-icon w-3.5 h-3.5 text-[#19589E]" />
                  <span>Curated Eats</span>
                </Link>
                <Link
                  href="/chat"
                  className="ui-pill-micro btn-micro group inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-white/95 hover:bg-white text-[#182848] text-xs font-semibold shadow-sm border border-slate-200/70"
                >
                  <Sparkles className="ui-pill-icon w-3.5 h-3.5 text-amber-500" />
                  <span>AI Trip Planner</span>
                </Link>
                <Link
                  href="/trips"
                  className="ui-pill-micro btn-micro group inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-white/95 hover:bg-white text-[#182848] text-xs font-semibold shadow-sm border border-slate-200/70"
                >
                  <Compass className="ui-pill-icon w-3.5 h-3.5 text-[#19589E]" />
                  <span>My Trips ({trips.length})</span>
                </Link>
              </div>
            </div>

            <div className="bg-white rounded-b-[16px] rounded-tr-[16px] shadow-xl shadow-[#182848]/8 border border-slate-200/80 p-3 sm:p-4 animate-widget-plate">
              <div className="grid grid-cols-1 md:grid-cols-12 gap-3 md:gap-0 items-center">
                {bookingTab === 'flights' && (
                  <div className="ui-field-micro group/col md:col-span-2 px-3 py-2 rounded-xl md:border-r border-slate-200 animate-widget-col-1">
                    <label className="flex items-center gap-1.5 text-xs font-bold text-[#182848] uppercase tracking-wider mb-1">
                      <Plane className="ui-icon-micro w-3.5 h-3.5 text-[#19589E]" />
                      <span>From</span>
                    </label>
                    <input
                      type="text"
                      value={flightOrigin}
                      onChange={(e) => setFlightOrigin(e.target.value.toUpperCase())}
                      placeholder="DEL, SFO, JFK"
                      className="w-full text-sm font-medium text-slate-700 placeholder:text-slate-400 focus:outline-none bg-transparent uppercase"
                    />
                  </div>
                )}

                <div
                  className={`ui-field-micro group/col relative px-3 py-2 rounded-xl md:border-r border-slate-200 animate-widget-col-1 ${
                    bookingTab === 'flights' ? 'md:col-span-2' : 'md:col-span-3'
                  }`}
                >
                  <label className="flex items-center gap-1.5 text-xs font-bold text-[#182848] uppercase tracking-wider mb-1">
                    <MapPin className="ui-icon-micro w-3.5 h-3.5 text-[#19589E]" />
                    <span>{bookingTab === 'flights' ? 'To' : 'Destinations'}</span>
                  </label>
                  <input
                    type="text"
                    value={searchDestination}
                    onFocus={() => setShowDestDropdown(true)}
                    onBlur={() => setTimeout(() => setShowDestDropdown(false), 180)}
                    onChange={(e) => setSearchDestination(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleWidgetSearch()}
                    placeholder={bookingTab === 'flights' ? 'BOM, KIX, CDG' : 'Where Are You Going?'}
                    className="w-full text-sm font-medium text-slate-700 placeholder:text-slate-400 focus:outline-none bg-transparent"
                  />
                  {showDestDropdown && (
                    <div className="absolute left-0 top-full mt-2 w-64 bg-white rounded-2xl shadow-xl border border-slate-100 py-2 z-30">
                      <div className="px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-slate-400">
                        Popular Destinations
                      </div>
                      {POPULAR_WIDGET_DESTINATIONS.map((d) => (
                        <button
                          key={d.label}
                          type="button"
                          onMouseDown={() => {
                            setSearchDestination(
                              bookingTab === 'flights' ? d.airportCode : d.label
                            );
                            setShowDestDropdown(false);
                          }}
                          className="w-full px-3.5 py-2 text-left text-sm hover:bg-slate-50 hover:pl-4 transition-all flex items-center justify-between"
                        >
                          <span className="font-semibold text-[#182848]">{d.label}</span>
                          <span className="text-xs text-slate-400">
                            {bookingTab === 'flights' ? d.airportCode : d.subtitle}
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                <div className="ui-field-micro group/col md:col-span-2 px-3 py-2 rounded-xl md:border-r border-slate-200 animate-widget-col-2">
                  <label className="flex items-center gap-1.5 text-xs font-bold text-[#182848] uppercase tracking-wider mb-1">
                    <Calendar className="ui-icon-micro w-3.5 h-3.5 text-[#19589E]" />
                    <span>{bookingTab === 'flights' ? 'Depart' : 'Check In'}</span>
                  </label>
                  <input
                    type="date"
                    value={checkInDate}
                    onChange={(e) => setCheckInDate(e.target.value)}
                    className="w-full text-sm font-medium text-slate-700 focus:outline-none bg-transparent cursor-pointer"
                  />
                </div>

                <div className="ui-field-micro group/col md:col-span-2 px-3 py-2 rounded-xl md:border-r border-slate-200 animate-widget-col-3">
                  <label className="flex items-center gap-1.5 text-xs font-bold text-[#182848] uppercase tracking-wider mb-1">
                    <Calendar className="ui-icon-micro w-3.5 h-3.5 text-[#19589E]" />
                    <span>{bookingTab === 'flights' ? 'Return' : 'Check Out'}</span>
                  </label>
                  <input
                    type="date"
                    value={checkOutDate}
                    onChange={(e) => setCheckOutDate(e.target.value)}
                    className="w-full text-sm font-medium text-slate-700 focus:outline-none bg-transparent cursor-pointer"
                  />
                </div>

                <div
                  className={`ui-field-micro group/col relative px-3 py-2 rounded-xl animate-widget-col-4 ${
                    bookingTab === 'flights' ? 'md:col-span-1' : 'md:col-span-2'
                  }`}
                >
                  <label className="flex items-center gap-1.5 text-xs font-bold text-[#182848] uppercase tracking-wider mb-1">
                    <Users className="ui-icon-micro w-3.5 h-3.5 text-[#19589E]" />
                    <span>{bookingTab === 'flights' ? 'Pax' : 'Guest'}</span>
                  </label>
                  <button
                    type="button"
                    onClick={() => setShowGuestPopover(!showGuestPopover)}
                    className="w-full text-left text-sm font-medium text-slate-700 focus:outline-none truncate"
                  >
                    {guestCount} {guestCount > 1 ? 'Guests' : 'Guest'}
                  </button>

                  {showGuestPopover && (
                    <div className="absolute left-0 top-full mt-2 w-56 bg-white rounded-2xl shadow-xl border border-slate-100 p-4 z-30">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-sm font-bold text-[#182848]">Travelers</div>
                          <div className="text-xs text-slate-400">Adults & Children</div>
                        </div>
                        <div className="flex items-center gap-2.5">
                          <button
                            type="button"
                            onClick={() => setGuestCount(Math.max(1, guestCount - 1))}
                            className="w-7 h-7 rounded-full border border-slate-200 flex items-center justify-center text-slate-600 hover:bg-slate-100 active:scale-90 transition-transform"
                          >
                            -
                          </button>
                          <span className="text-sm font-bold w-4 text-center">{guestCount}</span>
                          <button
                            type="button"
                            onClick={() => setGuestCount(Math.min(9, guestCount + 1))}
                            className="w-7 h-7 rounded-full border border-slate-200 flex items-center justify-center text-slate-600 hover:bg-slate-100 active:scale-90 transition-transform"
                          >
                            +
                          </button>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setShowGuestPopover(false)}
                        className="btn-micro mt-3 w-full py-1.5 rounded-xl bg-[#19589E] text-white text-xs font-semibold"
                      >
                        Apply
                      </button>
                    </div>
                  )}
                </div>

                <div className="md:col-span-3 md:pl-3 animate-widget-cta">
                  <button
                    type="button"
                    onClick={handleWidgetSearch}
                    className="ui-cta-spring btn-micro group w-full py-4 px-5 rounded-[12px] bg-[#182848] hover:bg-[#19589E] text-white font-semibold text-sm flex items-center justify-center gap-2 shadow-md shadow-[#182848]/20"
                  >
                    <span>{bookingTab === 'hotels' ? 'Search Hotels' : 'Search Flights'}</span>
                    <ChevronRight className="w-4 h-4 transition-transform duration-300 group-hover:translate-x-1.5" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* SECTION C: POPULAR DESTINATION & DISCOVERY BAND */}
        <section
          key={`popular-band-${exploreAnimKey}`}
          className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-16 pb-20"
        >
          <div
            className={`flex items-center justify-between mb-8 ${
              exploreVisible ? 'animate-reveal-header' : 'opacity-0'
            }`}
          >
            <div>
              <h2
                className="text-2xl sm:text-3xl font-extrabold text-[#182848] tracking-tight"
                style={{ fontFamily: "'Outfit', sans-serif" }}
              >
                Popular Destination
              </h2>
              <p
                className="text-base text-slate-600 mt-1 italic"
                style={{ fontFamily: "'Instrument Serif', serif" }}
              >
                Handpicked journeys ready to customize with mindtrip AI
              </p>
            </div>
            <Link
              href="/inspiration"
              className="group inline-flex items-center gap-1.5 text-sm font-bold text-[#19589E] hover:text-[#182848] transition-colors"
            >
              <span>Explore All</span>
              <ChevronRight className="w-4 h-4 transition-transform duration-300 group-hover:translate-x-1" />
            </Link>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {DESTINATIONS.map((dest, idx) => (
              <div
                key={dest.id}
                style={{ '--stagger-delay': `${0.34 + idx * 0.08}s` } as React.CSSProperties}
                className={`card-micro group bg-white rounded-[20px] overflow-hidden border border-slate-200/75 shadow-sm flex flex-col ${
                  exploreVisible ? 'animate-reveal-card' : 'opacity-0'
                }`}
              >
                <div className="relative h-56 overflow-hidden">
                  <img
                    src={dest.cardImage}
                    alt={dest.locationCaption}
                    className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700 ease-out"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/65 via-transparent to-black/15" />

                  <div className="absolute top-3.5 right-3.5 flex items-center gap-1 px-2.5 py-1 rounded-full bg-black/45 backdrop-blur-md text-white text-xs font-semibold transition-transform duration-300 group-hover:scale-105">
                    <Star className="w-3.5 h-3.5 fill-[#F59E0B] text-[#F59E0B]" />
                    <span>5.0</span>
                    <span className="text-white/70">({dest.reviews})</span>
                  </div>

                  <div className="absolute bottom-3.5 left-4 right-4 flex items-end justify-between text-white">
                    <div>
                      <h3
                        className="text-xl font-bold leading-tight"
                        style={{ fontFamily: "'Outfit', sans-serif" }}
                      >
                        {dest.title}
                      </h3>
                      <p className="text-xs text-white/85 flex items-center gap-1 mt-0.5">
                        <MapPin className="w-3 h-3 text-amber-400" />
                        {dest.locationCaption}
                      </p>
                    </div>
                    <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-white/20 backdrop-blur-md">
                      From {dest.priceFrom}
                    </span>
                  </div>
                </div>

                <div className="p-5 flex-1 flex flex-col justify-between space-y-4">
                  <div>
                    <div className="flex flex-wrap gap-1.5 mb-2.5">
                      {dest.tags.map((tag) => (
                        <span
                          key={tag}
                          className="px-2.5 py-0.5 rounded-full bg-[#F5F7FA] group-hover:bg-[#19589E]/10 text-[#19589E] text-xs font-semibold transition-colors"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                    <p className="text-sm text-slate-600 line-clamp-2">{dest.tagline}</p>
                  </div>

                  <div className="pt-3 border-t border-slate-100 flex items-center justify-between gap-2">
                    <button
                      type="button"
                      onClick={() =>
                        launchAiPlannerWithPrompt(`Create a 3-day itinerary for ${dest.title}`)
                      }
                      className="btn-micro group/btn flex-1 inline-flex items-center justify-center gap-1.5 py-2.5 px-3 rounded-xl bg-[#19589E] hover:bg-[#182848] text-white text-xs font-semibold"
                    >
                      <Sparkles className="w-3.5 h-3.5 transition-transform duration-300 group-hover/btn:rotate-45" />
                      <span>Plan with AI</span>
                    </button>
                    <Link
                      href={`/stays?destination=${encodeURIComponent(dest.title)}&auto_search=1`}
                      className="btn-micro py-2.5 px-3.5 rounded-xl bg-[#F5F7FA] hover:bg-slate-200/80 text-[#182848] text-xs font-semibold"
                    >
                      Stays
                    </Link>
                    <Link
                      href={`/flights?origin=${encodeURIComponent(flightOrigin || 'DEL')}&destination=${encodeURIComponent(dest.airportCode)}`}
                      className="btn-micro py-2.5 px-3 rounded-xl bg-[#F5F7FA] hover:bg-slate-200/80 text-[#182848] text-xs font-semibold"
                    >
                      Flights
                    </Link>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Curated Eats & Live Trip Teaser Band */}
          <div className="mt-16 grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-7 bg-white rounded-[22px] p-6 border border-slate-200/80 shadow-sm">
              <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-2.5">
                  <div className="w-9 h-9 rounded-xl bg-[#19589E]/10 flex items-center justify-center text-[#19589E]">
                    <Utensils className="w-5 h-5" />
                  </div>
                  <div>
                    <h3
                      className="text-lg font-bold text-[#182848]"
                      style={{ fontFamily: "'Outfit', sans-serif" }}
                    >
                      mindtrip Culinary Picks
                    </h3>
                    <p className="text-xs text-slate-500">
                      Real restaurants ready to explore or add to your trip
                    </p>
                  </div>
                </div>
                <Link
                  href="/eats"
                  className="text-xs font-bold text-[#19589E] hover:underline flex items-center gap-1"
                >
                  <span>All Eats</span>
                  <ChevronRight className="w-3.5 h-3.5" />
                </Link>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {featuredEats.map((eat) => (
                  <div
                    key={eat.id}
                    className="card-micro group rounded-2xl border border-slate-100 bg-[#F5F7FA]/70 p-3.5 flex flex-col justify-between gap-3"
                  >
                    <div className="flex items-center gap-3">
                      <img
                        src={eat.image}
                        alt={eat.name}
                        referrerPolicy="no-referrer"
                        className="w-16 h-16 rounded-xl object-cover shrink-0 transition-transform duration-500 group-hover:scale-105"
                      />
                      <div className="min-w-0">
                        <span className="text-[11px] font-bold uppercase text-[#19589E]">
                          {eat.destination} • {eat.priceTier}
                        </span>
                        <h4 className="text-sm font-bold text-[#182848] truncate">{eat.name}</h4>
                        <p className="text-xs text-slate-500 truncate">{eat.signatureDish}</p>
                      </div>
                    </div>
                    {eat.isLivePlace ? (
                      <button
                        type="button"
                        onClick={() =>
                          setAddToTripPlace({
                            id: eat.id,
                            name: eat.name,
                            destination: eat.destination,
                            address: eat.signatureDish,
                          })
                        }
                        className="btn-micro group/add w-full py-2 rounded-xl bg-white hover:bg-[#182848] text-[#182848] hover:text-white border border-slate-200 text-xs font-semibold flex items-center justify-center gap-1.5"
                      >
                        <span>Add to Trip</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    ) : (
                      <Link
                        href={`/eats?destination=${encodeURIComponent(eat.destination)}`}
                        className="btn-micro group/add w-full py-2 rounded-xl bg-white hover:bg-[#182848] text-[#182848] hover:text-white border border-slate-200 text-xs font-semibold flex items-center justify-center gap-1.5"
                      >
                        <span>Explore in {eat.destination}</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="card-micro lg:col-span-5 bg-gradient-to-br from-[#182848] to-[#19589E] rounded-[22px] p-6 text-white flex flex-col justify-between shadow-lg">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="px-3 py-1 rounded-full bg-white/15 text-xs font-semibold">
                    Live Itinerary Workspace
                  </span>
                  <span className="text-xs text-white/80">
                    {featuredTrip
                      ? `${featuredTrip.stop_count || featuredTripStops.length} Saved Stops`
                      : `${trips.length} Trips`}
                  </span>
                </div>
                <h3
                  className="text-xl font-extrabold leading-snug"
                  style={{ fontFamily: "'Outfit', sans-serif" }}
                >
                  {featuredTrip?.title || 'Start Your Custom Trip Itinerary'}
                </h3>
                <p className="text-xs text-white/80 mt-1">
                  {featuredTrip
                    ? `${featuredTrip.destination} • ${featuredTrip.day_count || 3} Days • ${featuredTrip.traveler_type || 'Explorer'}`
                    : 'Day-by-day plans, MapLibre routes, flights, and boutique stays in one place'}
                </p>

                <div className="mt-4 space-y-2">
                  {featuredTripStops.length > 0 ? (
                    featuredTripStops.map((stop: any, idx: number) => (
                      <div
                        key={stop.id || idx}
                        className="px-3.5 py-2.5 rounded-xl bg-white/10 backdrop-blur-sm border border-white/15 flex items-center justify-between text-xs"
                      >
                        <span className="font-medium truncate pr-2">
                          {stop.place?.name || stop.notes || `Stop ${idx + 1}`}
                        </span>
                        <span className="text-amber-300 font-semibold shrink-0 capitalize">
                          {stop.time_slot || 'Afternoon'}
                        </span>
                      </div>
                    ))
                  ) : (
                    <div className="px-3.5 py-2.5 rounded-xl bg-white/10 backdrop-blur-sm border border-white/15 text-xs text-white/85">
                      Open the Trip Builder or ask AI Concierge to generate your first itinerary.
                    </div>
                  )}
                </div>
              </div>

              <Link
                href={featuredTrip ? `/trip/${featuredTrip.id}` : '/trips'}
                className="btn-micro group mt-5 w-full py-3 rounded-xl bg-white text-[#182848] hover:bg-amber-300 font-bold text-sm flex items-center justify-center gap-2"
              >
                <span>Open Full Trip Builder</span>
                <ArrowRight className="w-4 h-4 transition-transform duration-300 group-hover:translate-x-1" />
              </Link>
            </div>
          </div>
        </section>
      </main>

      {/* GLOBAL QUICK SEARCH MODAL */}
      {quickSearchOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-start justify-center pt-20 px-4"
          onClick={() => setQuickSearchOpen(false)}
        >
          <div
            className="w-full max-w-xl bg-white rounded-3xl shadow-2xl border border-slate-200 overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-4 border-b border-slate-100 flex items-center gap-3">
              <Search className="w-5 h-5 text-[#19589E]" />
              <input
                type="text"
                autoFocus
                value={quickSearchQuery}
                onChange={(e) => setQuickSearchQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && quickSearchQuery.trim()) {
                    const q = quickSearchQuery.trim();
                    setQuickSearchOpen(false);
                    setQuickSearchQuery('');
                    launchAiPlannerWithPrompt(q);
                  }
                }}
                placeholder="Ask mindtrip AI or search destinations, eats, hotels..."
                className="flex-1 text-sm sm:text-base text-[#182848] placeholder:text-slate-400 focus:outline-none"
              />
              <button
                type="button"
                onClick={() => setQuickSearchOpen(false)}
                className="p-1.5 rounded-full hover:bg-slate-100 text-slate-400"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 space-y-4">
              <div>
                <div className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
                  Instant AI Trip Prompts
                </div>
                <div className="flex flex-wrap gap-2">
                  {AI_PRESET_PROMPTS.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => {
                        setQuickSearchOpen(false);
                        launchAiPlannerWithPrompt(prompt);
                      }}
                      className="px-3 py-1.5 rounded-full bg-[#F5F7FA] hover:bg-[#19589E] text-[#182848] hover:text-white text-xs font-semibold transition-colors"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <div className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
                  Jump to Destination
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {DESTINATIONS.map((d) => (
                    <button
                      key={d.id}
                      type="button"
                      onClick={() => {
                        setQuickSearchOpen(false);
                        launchAiPlannerWithPrompt(`Plan a complete trip to ${d.title}`);
                      }}
                      className="flex items-center gap-2 p-2 rounded-xl hover:bg-slate-50 border border-slate-100 text-left"
                    >
                      <img
                        src={d.cardImage}
                        alt={d.title}
                        className="w-8 h-8 rounded-lg object-cover"
                      />
                      <span className="text-xs font-bold text-[#182848]">{d.title}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Add To Trip Modal */}
      <AddToTripModal
        isOpen={Boolean(addToTripPlace)}
        onClose={() => setAddToTripPlace(null)}
        itemType="place"
        itemData={addToTripPlace}
      />

      {/* SHARED FOOTER */}
      <footer className="bg-[#182848] text-white/80 py-12 border-t border-white/10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row items-center justify-between gap-6">
          <MindtripLogo />
          <div className="flex flex-wrap items-center justify-center gap-6 text-sm">
            {navLinks.map((l) => (
              <Link key={l.href} href={l.href} className="hover:text-white transition-colors">
                {l.label}
              </Link>
            ))}
          </div>
          <p className="text-xs text-white/50">
            © 2026 mindtrip AI Travel • Next.js 14 + FastAPI + MapLibre GL
          </p>
        </div>
      </footer>
    </div>
  );
}
