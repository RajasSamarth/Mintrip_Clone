"use client";

import { useState, useEffect, useMemo, useRef } from "react";
import {
  Search,
  MapPin,
  Bed,
  Wifi,
  Coffee,
  Heart,
  X,
  Calendar,
  Users,
  Star,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  Sparkles,
  ShieldCheck,
  Building2,
  Check,
  AlertCircle,
  Plus
} from "lucide-react";
import { api } from "@/lib/api";
import NextImage from "next/image";
import { HotelDetailModal } from "@/components/stays/HotelDetailModal";
import { AddToTripModal } from "@/components/common/AddToTripModal";

export interface RoomType {
  name: string;
  description?: string;
  bed_type?: string;
  capacity?: number;
  price?: number | null;
  currency?: string;
  amenities?: string[];
}

export interface Hotel {
  id: string;
  name: string;
  destination: string;
  stars: number;
  rating: number | null;
  review_count: number;
  address: string;
  lat: number | null;
  lon: number | null;
  price_per_night: number | null;
  price_unavailable?: boolean;
  currency?: string;
  amenities: string[];
  photos: string[];
  room_types?: RoomType[];
  booking_url: string;
  description: string;
  source?: string;
}

function cleanHotelName(raw: string): string {
  if (!raw) return "";
  return raw
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[★☆・【】「」『』()\[\]]/g, " ")
    .replace(/\b(official site|official website|hotel & resort|hotels? & suites?)\b/gi, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function extractLocationSignature(name: string, address: string): string {
  const text = `${name} ${address}`.toLowerCase().normalize("NFKD").replace(/[\u0300-\u036f]/g, "");
  const tokens = [
    "ekimae", "gion", "nijo", "shijo", "sanjo", "gojo", "rokujo", "hachijo",
    "karasuma", "kawaramachi", "oike", "arashiyama", "kiyomizu", "fushimi",
    "higashiyama", "shimogyo", "nakagyo", "kamigyo", "sakyo", "minami", "kita",
    "station", "airport", "downtown", "central", "west", "east", "north", "south",
    "terminal", "connaught place", "aerocity", "changi", "times square", "shinjuku",
    "shibuya", "ginza", "roppongi", "asakusa", "ueno", "chandni chowk", "paharganj"
  ];
  const matched = tokens.filter((t) => new RegExp(`\\b${t}\\b`, "i").test(text));
  const numMatch = address.match(/\b\d+[-–]\d+\b/);
  if (numMatch) matched.push(numMatch[0]);
  return matched.sort().join("-");
}

function areSameHotel(h1: Hotel, h2: Hotel): boolean {
  const n1 = cleanHotelName(h1.name);
  const n2 = cleanHotelName(h2.name);
  if (!n1 || !n2) return false;

  // Exact normalized name match
  if (n1 === n2) {
    const loc1 = extractLocationSignature(h1.name, h1.address || "");
    const loc2 = extractLocationSignature(h2.name, h2.address || "");
    // If both specify different location signatures, they are DIFFERENT branches!
    if (loc1 && loc2 && loc1 !== loc2) {
      return false; // Keep both!
    }
    return true; // Duplicate!
  }

  // Substring match
  if (n1.includes(n2) || n2.includes(n1)) {
    const loc1 = extractLocationSignature(h1.name, h1.address || "");
    const loc2 = extractLocationSignature(h2.name, h2.address || "");
    if (loc1 && loc2 && loc1 !== loc2) {
      return false;
    }
    if (Math.abs(n1.length - n2.length) <= 8) {
      return true;
    }
  }

  return false;
}

const CURRENCIES: Record<string, { symbol: string; label: string; rateFromINR: number }> = {
  INR: { symbol: "₹", label: "Indian Rupee (INR)", rateFromINR: 1.0 },
  USD: { symbol: "$", label: "US Dollar (USD)", rateFromINR: 1 / 85.0 },
  EUR: { symbol: "€", label: "Euro (EUR)", rateFromINR: 1 / 92.0 },
  GBP: { symbol: "£", label: "British Pound (GBP)", rateFromINR: 1 / 108.0 },
  JPY: { symbol: "¥", label: "Japanese Yen (JPY)", rateFromINR: 1.78 },
};

const POPULAR_DESTINATIONS = [
  { city: "Kyoto", country: "Japan", label: "Kyoto, Japan" },
  { city: "Delhi", country: "India", label: "Delhi, India" },
  { city: "Rome", country: "Italy", label: "Rome, Italy" },
  { city: "Paris", country: "France", label: "Paris, France" },
  { city: "New York", country: "United States", label: "New York, USA" },
  { city: "Bali", country: "Indonesia", label: "Bali, Indonesia" },
];

const FALLBACK_HOTEL_IMAGE =
  "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=800&q=80";

function HotelCardImage({ src, alt }: { src?: string; alt: string }) {
  const [imgSrc, setImgSrc] = useState(src || FALLBACK_HOTEL_IMAGE);

  useEffect(() => {
    setImgSrc(src || FALLBACK_HOTEL_IMAGE);
  }, [src]);

  return (
    <img
      src={imgSrc}
      alt={alt}
      referrerPolicy="no-referrer"
      onError={() => {
        if (imgSrc !== FALLBACK_HOTEL_IMAGE) {
          setImgSrc(FALLBACK_HOTEL_IMAGE);
        }
      }}
      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
      loading="lazy"
    />
  );
}

export default function StaysPage() {
  const [hotels, setHotels] = useState<Hotel[]>([]);
  const [destination, setDestination] = useState("Kyoto");
  const [checkIn, setCheckIn] = useState("");
  const [checkOut, setCheckOut] = useState("");
  const [adults, setAdults] = useState(2);
  const [rooms, setRooms] = useState(1);
  const [selectedCurrency, setSelectedCurrency] = useState("INR");
  const [showCurrencyMenu, setShowCurrencyMenu] = useState(false);
  const [showGuestsMenu, setShowGuestsMenu] = useState(false);
  const [selectedHotel, setSelectedHotel] = useState<Hotel | null>(null);
  const [addToTripHotel, setAddToTripHotel] = useState<Hotel | null>(null);

  // Filters
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [starsFilter, setStarsFilter] = useState("");
  const [amenitiesFilter, setAmenitiesFilter] = useState<string[]>([]);

  // State
  const [loading, setLoading] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState("");
  const [hasSearched, setHasSearched] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const currencyMenuRef = useRef<HTMLDivElement>(null);
  const guestsMenuRef = useRef<HTMLDivElement>(null);

  // Initialize dates
  useEffect(() => {
    const today = new Date();
    const d1 = new Date(today);
    d1.setDate(today.getDate() + 14);
    const d2 = new Date(today);
    d2.setDate(today.getDate() + 17);

    setCheckIn(d1.toISOString().split("T")[0]);
    setCheckOut(d2.toISOString().split("T")[0]);
  }, []);

  // Close popovers on click outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (currencyMenuRef.current && !currencyMenuRef.current.contains(e.target as Node)) {
        setShowCurrencyMenu(false);
      }
      if (guestsMenuRef.current && !guestsMenuRef.current.contains(e.target as Node)) {
        setShowGuestsMenu(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Initial load
  useEffect(() => {
    async function initialFetch() {
      setLoading(true);
      try {
        const res = await api(`/hotels?destination=Kyoto&limit=50&auto_scrape=false`);
        const json = await res.json();
        if (json.hotels && json.hotels.length > 0) {
          setHotels(json.hotels);
        } else {
          executeSearch("Kyoto");
        }
      } catch (err) {
        console.warn("Initial hotels load failed, triggering search:", err);
        executeSearch("Kyoto");
      } finally {
        setLoading(false);
      }
    }
    initialFetch();
  }, []);

  // Execute Search Function
  async function executeSearch(targetDest?: string) {
    const dest = (targetDest || destination).trim();
    if (!dest) {
      setErrorMsg("Please enter a destination city (e.g. Kyoto, Delhi, Rome).");
      return;
    }

    setLoading(true);
    setHasSearched(true);
    setErrorMsg("");
    setLoadingStatus(`Live scraping Google Hotels for ${dest}...`);

    try {
      const payload = {
        destination: dest,
        check_in: checkIn || undefined,
        check_out: checkOut || undefined,
        adults,
        rooms,
        currency: selectedCurrency,
        live: true,
      };

      const res = await api("/hotels/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const json = await res.json();
      if (json.hotels && json.hotels.length > 0) {
        setHotels(json.hotels);
      } else {
        setHotels([]);
        setErrorMsg(json.message || `No hotels found for "${dest}". Please verify the destination name or try different dates.`);
      }
    } catch (err: any) {
      console.warn("Hotel search request failed, checking existing cache:", err);
      try {
        const fallbackRes = await api(`/hotels?destination=${encodeURIComponent(dest)}&auto_scrape=false`);
        const fallbackJson = await fallbackRes.json();
        if (fallbackJson.hotels && fallbackJson.hotels.length > 0) {
          setHotels(fallbackJson.hotels);
        } else {
          setHotels([]);
          setErrorMsg(`No hotels found for "${dest}".`);
        }
      } catch {
        setHotels([]);
        setErrorMsg("Could not fetch hotels. Please check network connection and try again.");
      }
    } finally {
      setLoading(false);
      setLoadingStatus("");
    }
  }

  // Format price helper in active currency
  function formatHotelPrice(hotel: Hotel): { formatted: string; isUnavailable: boolean } {
    if (hotel.price_unavailable || hotel.price_per_night == null || hotel.price_per_night <= 0) {
      return { formatted: "Price unavailable", isUnavailable: true };
    }

    const curr = CURRENCIES[selectedCurrency] || CURRENCIES.INR;
    const hotelCurr = (hotel.currency || "INR").toUpperCase();
    let priceInCurrent = hotel.price_per_night;

    if (hotelCurr === "INR" && selectedCurrency !== "INR") {
      priceInCurrent = hotel.price_per_night * curr.rateFromINR;
    } else if (hotelCurr === "USD" && selectedCurrency === "INR") {
      priceInCurrent = hotel.price_per_night * 85.0;
    } else if (hotelCurr === "USD" && selectedCurrency !== "USD") {
      const inr = hotel.price_per_night * 85.0;
      priceInCurrent = inr * curr.rateFromINR;
    }

    return {
      formatted: `${curr.symbol} ${Math.round(priceInCurrent).toLocaleString("en-IN")}`,
      isUnavailable: false,
    };
  }

  // Filtered hotels with smart deduplication
  const filteredHotels = useMemo(() => {
    // Smart deduplication: filter out duplicates while preserving distinct branches
    const uniqueHotels: Hotel[] = [];
    for (const h of hotels) {
      let duplicateIndex = -1;
      for (let i = 0; i < uniqueHotels.length; i++) {
        if (areSameHotel(h, uniqueHotels[i])) {
          duplicateIndex = i;
          break;
        }
      }
      if (duplicateIndex === -1) {
        uniqueHotels.push(h);
      } else {
        // Keep the richer entry
        const existing = uniqueHotels[duplicateIndex];
        if (existing.price_unavailable && !h.price_unavailable) {
          uniqueHotels[duplicateIndex] = h;
        } else if ((h.address || "").length > (existing.address || "").length) {
          uniqueHotels[duplicateIndex] = h;
        } else if ((h.photos || []).length > (existing.photos || []).length) {
          uniqueHotels[duplicateIndex] = h;
        }
      }
    }

    return uniqueHotels.filter((h) => {
      // Star filter
      if (starsFilter && h.stars < parseInt(starsFilter, 10)) {
        return false;
      }
      // Price filters
      if (minPrice && h.price_per_night != null && h.price_per_night < parseFloat(minPrice)) {
        return false;
      }
      if (maxPrice && h.price_per_night != null && h.price_per_night > parseFloat(maxPrice)) {
        return false;
      }
      // Amenities filter
      if (amenitiesFilter.length > 0) {
        const hAmen = (h.amenities || []).map((a) => a.toLowerCase());
        const hasAll = amenitiesFilter.every((req) =>
          hAmen.some((a) => a.includes(req.toLowerCase()))
        );
        if (!hasAll) return false;
      }
      return true;
    });
  }, [hotels, starsFilter, minPrice, maxPrice, amenitiesFilter]);

  const toggleAmenity = (amenity: string) => {
    if (amenitiesFilter.includes(amenity)) {
      setAmenitiesFilter(amenitiesFilter.filter((a) => a !== amenity));
    } else {
      setAmenitiesFilter([...amenitiesFilter, amenity]);
    }
  };

  const clearAllFilters = () => {
    setMinPrice("");
    setMaxPrice("");
    setStarsFilter("");
    setAmenitiesFilter([]);
  };

  return (
    <div className="min-h-screen bg-[#fbfbfa] text-stone-900 pb-24">
      {/* Top Header Bar */}
      <header className="border-b border-stone-200/80 bg-white/90 backdrop-blur-md sticky top-0 z-30 shadow-xs">
        <div className="mx-auto max-w-[1440px] px-4 py-3.5 sm:px-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-stone-900 text-white flex items-center justify-center font-bold shadow-xs">
              <Building2 className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-stone-900">Google Hotels Search</h1>
              <p className="text-xs text-stone-500">Real-time room rates, guest ratings & authentic deals</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Currency Selector (Default: INR ₹) */}
            <div className="relative" ref={currencyMenuRef}>
              <button
                type="button"
                onClick={() => setShowCurrencyMenu(!showCurrencyMenu)}
                className="inline-flex items-center gap-1.5 rounded-full border border-stone-300 bg-white px-3.5 py-1.5 text-xs font-semibold text-stone-800 hover:bg-stone-50 shadow-xs transition-colors"
                title="Select currency (Default: INR)"
              >
                <span className="w-4 h-4 rounded-full bg-stone-100 flex items-center justify-center text-[10px] font-bold text-stone-800">
                  {CURRENCIES[selectedCurrency]?.symbol || "₹"}
                </span>
                <span>{selectedCurrency}</span>
                <ChevronDown className="w-3.5 h-3.5 text-stone-500" />
              </button>

              {showCurrencyMenu && (
                <div className="absolute right-0 mt-2 w-48 rounded-2xl border border-stone-200 bg-white py-1.5 shadow-xl z-50">
                  {Object.entries(CURRENCIES).map(([code, cur]) => (
                    <button
                      key={code}
                      onClick={() => {
                        setSelectedCurrency(code);
                        setShowCurrencyMenu(false);
                      }}
                      className={`w-full px-3.5 py-2 text-left text-xs font-medium flex items-center justify-between hover:bg-stone-50 transition-colors ${
                        selectedCurrency === code ? "text-stone-900 font-bold bg-stone-50" : "text-stone-600"
                      }`}
                    >
                      <span>{cur.label}</span>
                      <span className="font-bold text-stone-500">{cur.symbol}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <div className="mx-auto max-w-[1440px] px-4 sm:px-6 py-6">
        {/* Search & Filter Bar */}
        <div className="rounded-3xl border border-stone-200/90 bg-white p-5 shadow-sm mb-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
            {/* Destination Input */}
            <div className="md:col-span-1">
              <label className="block text-xs font-bold uppercase tracking-wider text-stone-500 mb-1.5">
                Destination
              </label>
              <div className="relative">
                <MapPin className="absolute left-3.5 top-3 w-4 h-4 text-stone-400" />
                <input
                  type="text"
                  value={destination}
                  onChange={(e) => setDestination(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && executeSearch()}
                  placeholder="e.g. Kyoto, Delhi, Rome, Paris"
                  className="w-full rounded-2xl border border-stone-200 bg-stone-50/50 py-2.5 pl-10 pr-3 text-sm font-semibold text-stone-900 placeholder:text-stone-400 focus:border-stone-900 focus:bg-white focus:outline-hidden transition-all"
                />
              </div>
            </div>

            {/* Check-in / Check-out Dates */}
            <div className="md:col-span-1">
              <label className="block text-xs font-bold uppercase tracking-wider text-stone-500 mb-1.5">
                Dates
              </label>
              <div className="grid grid-cols-2 gap-2">
                <div className="relative">
                  <input
                    type="date"
                    value={checkIn}
                    onChange={(e) => setCheckIn(e.target.value)}
                    className="w-full rounded-2xl border border-stone-200 bg-stone-50/50 py-2 px-2.5 text-xs font-semibold text-stone-900 focus:border-stone-900 focus:bg-white focus:outline-hidden"
                  />
                </div>
                <div className="relative">
                  <input
                    type="date"
                    value={checkOut}
                    onChange={(e) => setCheckOut(e.target.value)}
                    className="w-full rounded-2xl border border-stone-200 bg-stone-50/50 py-2 px-2.5 text-xs font-semibold text-stone-900 focus:border-stone-900 focus:bg-white focus:outline-hidden"
                  />
                </div>
              </div>
            </div>

            {/* Guests & Rooms Popover */}
            <div className="md:col-span-1 relative" ref={guestsMenuRef}>
              <label className="block text-xs font-bold uppercase tracking-wider text-stone-500 mb-1.5">
                Guests & Rooms
              </label>
              <button
                type="button"
                onClick={() => setShowGuestsMenu(!showGuestsMenu)}
                className="w-full rounded-2xl border border-stone-200 bg-stone-50/50 py-2.5 px-3.5 text-left text-sm font-semibold text-stone-900 flex items-center justify-between hover:bg-white transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Users className="w-4 h-4 text-stone-500" />
                  <span>
                    {adults} Guest{adults > 1 ? "s" : ""}, {rooms} Room{rooms > 1 ? "s" : ""}
                  </span>
                </div>
                <ChevronDown className="w-4 h-4 text-stone-400" />
              </button>

              {showGuestsMenu && (
                <div className="absolute left-0 right-0 mt-2 rounded-2xl border border-stone-200 bg-white p-4 shadow-xl z-40 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-stone-800">Adults</span>
                    <div className="flex items-center gap-2.5">
                      <button
                        type="button"
                        onClick={() => setAdults(Math.max(1, adults - 1))}
                        className="w-7 h-7 rounded-full border border-stone-300 flex items-center justify-center font-bold text-stone-700 hover:bg-stone-100"
                      >
                        -
                      </button>
                      <span className="text-xs font-bold w-4 text-center">{adults}</span>
                      <button
                        type="button"
                        onClick={() => setAdults(Math.min(10, adults + 1))}
                        className="w-7 h-7 rounded-full border border-stone-300 flex items-center justify-center font-bold text-stone-700 hover:bg-stone-100"
                      >
                        +
                      </button>
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-2 border-t border-stone-100">
                    <span className="text-xs font-bold text-stone-800">Rooms</span>
                    <div className="flex items-center gap-2.5">
                      <button
                        type="button"
                        onClick={() => setRooms(Math.max(1, rooms - 1))}
                        className="w-7 h-7 rounded-full border border-stone-300 flex items-center justify-center font-bold text-stone-700 hover:bg-stone-100"
                      >
                        -
                      </button>
                      <span className="text-xs font-bold w-4 text-center">{rooms}</span>
                      <button
                        type="button"
                        onClick={() => setRooms(Math.min(6, rooms + 1))}
                        className="w-7 h-7 rounded-full border border-stone-300 flex items-center justify-center font-bold text-stone-700 hover:bg-stone-100"
                      >
                        +
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Search Button */}
            <div className="md:col-span-1">
              <button
                type="button"
                onClick={() => executeSearch()}
                disabled={loading}
                className="w-full rounded-2xl bg-stone-900 py-2.5 px-4 text-sm font-bold text-white shadow-xs hover:bg-stone-800 active:scale-[0.99] disabled:opacity-50 transition-all flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <div className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                    <span>Searching...</span>
                  </>
                ) : (
                  <>
                    <Search className="w-4 h-4" />
                    <span>Search Hotels</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Popular destination quick chips */}
          <div className="mt-4 pt-3 border-t border-stone-100 flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-stone-400 mr-1">Popular:</span>
            {POPULAR_DESTINATIONS.map((pop) => (
              <button
                key={pop.city}
                onClick={() => {
                  setDestination(pop.city);
                  executeSearch(pop.city);
                }}
                className={`rounded-full px-3 py-1 text-xs font-semibold transition-all ${
                  destination.toLowerCase() === pop.city.toLowerCase()
                    ? "bg-stone-900 text-white shadow-xs"
                    : "bg-stone-100 text-stone-600 hover:bg-stone-200/70"
                }`}
              >
                {pop.city}
              </button>
            ))}
          </div>
        </div>

        {/* Live Loading Banner */}
        {loading && (
          <div className="rounded-2xl bg-amber-500/10 border border-amber-300/40 p-4 mb-6 flex items-center gap-3 text-amber-900 text-xs font-semibold animate-pulse">
            <div className="w-4 h-4 rounded-full border-2 border-amber-600/30 border-t-amber-600 animate-spin shrink-0" />
            <span>{loadingStatus || `Live scraping Google Hotels for ${destination}...`}</span>
          </div>
        )}

        {/* Error message */}
        {errorMsg && (
          <div className="rounded-2xl bg-rose-50 border border-rose-200 p-4 mb-6 flex items-center gap-3 text-rose-800 text-xs font-medium">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Main Layout: Filters Sidebar + Hotels Grid */}
        <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
          {/* Filters Sidebar */}
          <aside className="space-y-6">
            <div className="rounded-3xl border border-stone-200/90 bg-white p-5 shadow-sm sticky top-24">
              <div className="flex items-center justify-between mb-4 pb-2 border-b border-stone-100">
                <h3 className="text-xs font-bold uppercase tracking-wider text-stone-500">Filters</h3>
                {(minPrice || maxPrice || starsFilter || amenitiesFilter.length > 0) && (
                  <button
                    onClick={clearAllFilters}
                    className="text-xs font-bold text-stone-600 hover:text-stone-900 hover:underline"
                  >
                    Reset
                  </button>
                )}
              </div>

              {/* Star Rating Filter */}
              <div className="mb-5">
                <label className="block text-xs font-bold text-stone-700 mb-2">Star Rating</label>
                <div className="grid grid-cols-4 gap-1.5">
                  {["", "3", "4", "5"].map((st) => (
                    <button
                      key={st}
                      type="button"
                      onClick={() => setStarsFilter(st)}
                      className={`rounded-xl py-1.5 text-xs font-bold transition-all ${
                        starsFilter === st
                          ? "bg-stone-900 text-white"
                          : "bg-stone-100 text-stone-700 hover:bg-stone-200"
                      }`}
                    >
                      {st ? `${st}★+` : "All"}
                    </button>
                  ))}
                </div>
              </div>

              {/* Price Filter (No artificial minimums) */}
              <div className="mb-5">
                <label className="block text-xs font-bold text-stone-700 mb-2">
                  Price ({CURRENCIES[selectedCurrency]?.symbol})
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    value={minPrice}
                    onChange={(e) => setMinPrice(e.target.value)}
                    placeholder="Min"
                    className="w-full rounded-xl border border-stone-200 px-3 py-1.5 text-xs font-semibold focus:border-stone-900 focus:outline-hidden"
                  />
                  <span className="text-stone-400 font-bold">-</span>
                  <input
                    type="number"
                    value={maxPrice}
                    onChange={(e) => setMaxPrice(e.target.value)}
                    placeholder="Max"
                    className="w-full rounded-xl border border-stone-200 px-3 py-1.5 text-xs font-semibold focus:border-stone-900 focus:outline-hidden"
                  />
                </div>
              </div>

              {/* Amenities Filter */}
              <div>
                <label className="block text-xs font-bold text-stone-700 mb-2.5">Popular Amenities</label>
                <div className="space-y-2">
                  {["Free Wi-Fi", "Pool", "Spa", "Breakfast", "Parking", "Fitness center", "Pet-friendly"].map(
                    (am) => {
                      const checked = amenitiesFilter.includes(am);
                      return (
                        <label key={am} className="flex items-center gap-2 text-xs font-medium text-stone-700 cursor-pointer hover:text-stone-900">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleAmenity(am)}
                            className="rounded border-stone-300 text-stone-900 focus:ring-stone-900 w-4 h-4"
                          />
                          <span>{am}</span>
                        </label>
                      );
                    }
                  )}
                </div>
              </div>
            </div>
          </aside>

          {/* Results Grid */}
          <main>
            {/* Header / Summary */}
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-base font-bold text-stone-900">
                  {filteredHotels.length} Accommodation{filteredHotels.length !== 1 ? "s" : ""} Available
                </h2>
                <p className="text-xs text-stone-500">in {destination} • Sorted by relevance</p>
              </div>
            </div>

            {/* Empty State */}
            {!loading && filteredHotels.length === 0 && (
              <div className="rounded-3xl border border-stone-200/90 bg-white p-12 text-center">
                <Bed className="w-12 h-12 text-stone-300 mx-auto mb-3" />
                <h3 className="text-base font-bold text-stone-900 mb-1">
                  {hotels.length === 0 ? `No hotels found for "${destination}"` : "No stays matched your criteria"}
                </h3>
                <p className="text-xs text-stone-500 mb-4">
                  {hotels.length === 0
                    ? `We could not find any live hotel listings for ${destination}. Please verify the city name or try searching for another destination.`
                    : "Try clearing your filters or adjusting your price/star criteria."}
                </p>
                {hotels.length > 0 && (
                  <button
                    onClick={clearAllFilters}
                    className="rounded-full bg-stone-900 px-4 py-2 text-xs font-bold text-white hover:bg-stone-800"
                  >
                    Clear Filters
                  </button>
                )}
              </div>
            )}

            {/* Hotel Cards Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
              {filteredHotels.map((hotel, idx) => {
                const { formatted, isUnavailable } = formatHotelPrice(hotel);
                const heroPhoto =
                  hotel.photos?.[0] ||
                  "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=800&q=80";

                return (
                  <article
                    key={`${hotel.id || "hotel"}-${idx}`}
                    onClick={() => setSelectedHotel(hotel)}
                    className="rounded-3xl border border-stone-200/80 bg-white shadow-xs overflow-hidden flex flex-col hover:shadow-md hover:border-stone-400 transition-all group cursor-pointer"
                  >
                    {/* Photo Header */}
                    <div className="relative h-48 w-full overflow-hidden bg-stone-100">
                      <HotelCardImage src={hotel.photos?.[0]} alt={hotel.name} />

                      {/* Stars Badge */}
                      {hotel.stars > 0 && (
                        <div className="absolute top-3 left-3 bg-white/90 backdrop-blur-md px-2.5 py-1 rounded-full flex items-center gap-1 shadow-xs">
                          {[...Array(hotel.stars)].map((_, i) => (
                            <Star key={i} className="w-3 h-3 text-amber-500 fill-amber-500" />
                          ))}
                        </div>
                      )}

                      {/* Rating Badge */}
                      {hotel.rating != null && (
                        <div className="absolute top-3 right-3 bg-white/95 backdrop-blur-md px-2.5 py-1 rounded-full text-xs font-black text-stone-900 shadow-xs flex items-center gap-1">
                          <span className="text-amber-500 font-bold">★</span>
                          <span>{hotel.rating.toFixed(1)}</span>
                        </div>
                      )}
                    </div>

                    {/* Hotel Content */}
                    <div className="p-4 flex-1 flex flex-col justify-between">
                      <div>
                        {/* Title & Review count */}
                        <div className="flex items-start justify-between gap-2 mb-1">
                          <h3 className="font-bold text-sm text-stone-900 group-hover:text-amber-700 transition-colors line-clamp-1">
                            {hotel.name}
                          </h3>
                        </div>

                        {/* Address & Reviews */}
                        <p className="text-xs text-stone-500 line-clamp-1 mb-2.5">{hotel.address}</p>
                        {hotel.review_count > 0 && (
                          <p className="text-[11px] font-semibold text-stone-400 mb-3">
                            {hotel.review_count.toLocaleString()} verified reviews
                          </p>
                        )}

                        {/* Amenities Chips */}
                        {hotel.amenities && hotel.amenities.length > 0 && (
                          <div className="flex flex-wrap gap-1 mb-3">
                            {hotel.amenities.slice(0, 3).map((am, amIdx) => (
                              <span
                                key={`${am}-${amIdx}`}
                                className="rounded-lg bg-stone-100 px-2 py-0.5 text-[10px] font-bold text-stone-600"
                              >
                                {am}
                              </span>
                            ))}
                            {hotel.amenities.length > 3 && (
                              <span className="rounded-lg bg-stone-50 px-1.5 py-0.5 text-[10px] font-medium text-stone-400">
                                +{hotel.amenities.length - 3}
                              </span>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Price & Action Row */}
                      <div>
                        <div className="pt-3 border-t border-stone-100 flex items-center justify-between gap-2">
                          <div>
                            {isUnavailable ? (
                              <div>
                                <span className="inline-block rounded-full bg-amber-50 border border-amber-200/80 px-2.5 py-0.5 text-[11px] font-bold text-amber-800">
                                  Price unavailable
                                </span>
                                <p className="text-[10px] text-stone-400 mt-0.5">Check dates on site</p>
                              </div>
                            ) : (
                              <div>
                                <p className="text-base font-black text-stone-900 tracking-tight">
                                  {formatted}
                                </p>
                                <p className="text-[10px] text-stone-400 font-medium">/ night • total</p>
                              </div>
                            )}
                          </div>

                          {/* Action Buttons: Add to Trip & View Deal */}
                          <div className="flex items-center gap-1.5">
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setAddToTripHotel(hotel);
                              }}
                              className="rounded-xl border border-stone-200 bg-white px-2.5 py-1.5 text-xs font-bold text-stone-700 hover:bg-stone-50 hover:border-stone-900 flex items-center gap-1 transition-colors shadow-2xs"
                              title="Add to trip itinerary"
                            >
                              <Plus className="w-3.5 h-3.5 text-amber-600" />
                              <span>Trip</span>
                            </button>
                            <a
                              href={hotel.booking_url || `https://www.google.com/travel/hotels/${encodeURIComponent(destination)}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="rounded-xl border border-stone-300 bg-white px-3 py-1.5 text-xs font-bold text-stone-800 hover:bg-stone-50 hover:border-stone-400 flex items-center gap-1.5 transition-colors shadow-xs"
                            >
                              <span>{isUnavailable ? "Check" : "View Deal"}</span>
                              <ExternalLink className="w-3.5 h-3.5 text-stone-500" />
                            </a>
                          </div>
                        </div>

                        {/* View Rooms & Full Details Button */}
                        <button
                          type="button"
                          onClick={() => setSelectedHotel(hotel)}
                          className="w-full mt-3 rounded-xl bg-stone-900/90 py-2 px-3 text-xs font-bold text-white hover:bg-stone-900 transition-colors flex items-center justify-center gap-1.5 shadow-2xs"
                        >
                          <span>View Rooms & Details</span>
                          <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          </main>
        </div>
      </div>

      {/* Hotel Detail Modal */}
      <HotelDetailModal
        hotel={selectedHotel}
        onClose={() => setSelectedHotel(null)}
        selectedCurrency={selectedCurrency}
        currencies={CURRENCIES}
        onAddToTrip={(h) => setAddToTripHotel(h)}
      />

      {/* Add To Trip Modal */}
      <AddToTripModal
        isOpen={Boolean(addToTripHotel)}
        onClose={() => setAddToTripHotel(null)}
        itemType="hotel"
        itemData={addToTripHotel}
        currency={selectedCurrency}
      />
    </div>
  );
}
