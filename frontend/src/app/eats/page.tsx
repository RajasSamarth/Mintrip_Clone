"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import {
  MapPin,
  Star,
  ChevronRight,
  ChevronDown,
  Utensils,
  Coffee,
  Wine,
  Wheat,
  Sparkles,
  AlertCircle,
} from "lucide-react";
import { api } from "@/lib/api";
import { PlaceDetailModal } from "@/components/chat/PlaceDetailModal";

const EAT_CATEGORIES = [
  { key: "restaurant", label: "Restaurants", icon: Utensils },
  { key: "cafe", label: "Cafes", icon: Coffee },
  { key: "bar", label: "Bars & Pubs", icon: Wine },
  { key: "bakery", label: "Bakeries", icon: Wheat },
  { key: "other", label: "Other Eats", icon: Sparkles },
];

const ICON_BY_CATEGORY = {
  restaurant: Utensils,
  cafe: Coffee,
  bar: Wine,
  bakery: Wheat,
  other: Sparkles,
};

const CATEGORY_LABEL = {
  restaurant: "Restaurant",
  cafe: "Cafe",
  bar: "Bar",
  bakery: "Bakery",
  other: "Eats",
};

const POPULAR_DESTINATIONS = [
  { city: "Delhi", country: "India", label: "Delhi, India" },
  { city: "Mumbai", country: "India", label: "Mumbai, India" },
  { city: "Bangalore", country: "India", label: "Bengaluru, India" },
  { city: "Goa", country: "India", label: "Goa, India" },
  { city: "Bangkok", country: "Thailand", label: "Bangkok, Thailand" },
  { city: "Paris", country: "France", label: "Paris, France" },
  { city: "Rome", country: "Italy", label: "Rome, Italy" },
  { city: "Tokyo", country: "Japan", label: "Tokyo, Japan" },
];

export default function EatsPage() {
  const [eats, setEats] = useState<any[]>([]);
  const [destination, setDestination] = useState("Delhi");
  const [category, setCategory] = useState("restaurant");
  const [selectedEat, setSelectedEat] = useState<any | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [loading, setLoading] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState("");
  const [hasSearched, setHasSearched] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {}
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    async function initialFetch() {
      setLoading(true);
      try {
        const res = await api(
          `/eats?destination=${encodeURIComponent(destination)}&category=${category}&limit=50&auto_scrape=false`
        );
        const json = await res.json();
        if (json.eats && Array.isArray(json.eats) && json.eats.length > 0) {
          setEats(json.eats);
        } else {
          executeSearch(destination);
        }
      } catch (err) {
        console.warn("Initial eats load failed, triggering search:", err);
        executeSearch(destination);
      } finally {
        setLoading(false);
      }
    }
    initialFetch();
  }, []);

  async function fetchEatDetail(eatId: string) {
    setDetailLoading(true);
    try {
      const res = await api(`/eats/${encodeURIComponent(eatId)}/detail`, {
        method: "GET",
      });
      const json = await res.json();
      setSelectedEat(json);
    } catch (err) {
      console.warn("Failed to fetch eat detail:", err);
      const existing = eats.find((e) => e.id === eatId);
      setSelectedEat(existing || null);
    } finally {
      setDetailLoading(false);
    }
  }

  async function executeSearch(targetDest?: string, targetCat?: string) {
    const dest = (targetDest || destination).trim();
    const cat = (targetCat || category).trim();
    if (!dest) {
      setErrorMsg("Please enter a destination city (e.g. Delhi, Paris, Bangkok).");
      return;
    }

    setDestination(dest);
    setCategory(cat);
    setLoading(true);
    setHasSearched(true);
    setErrorMsg("");
    setLoadingStatus(`Live scraping Google Maps for ${cat} in ${dest}...`);

    try {
      const res = await api(
        `/eats?destination=${encodeURIComponent(dest)}&category=${encodeURIComponent(cat)}&limit=50&auto_scrape=true&live=true`,
        { method: "GET" }
      );
      const json = await res.json();
      if (json.eats && Array.isArray(json.eats) && json.eats.length > 0) {
        setEats(json.eats);
      } else {
        setEats([]);
        setErrorMsg(
          json.message ||
            `No ${cat} found for "${dest}". Please verify the destination or try another category.`
        );
      }
    } catch (err: any) {
      console.warn("Eats search request failed:", err);
      setEats([]);
      setErrorMsg("Could not fetch eats. Please check network connection and try again.");
    } finally {
      setLoading(false);
      setLoadingStatus("");
    }
  }

  const filteredEats = useMemo(() => {
    return (eats || []).filter((e: any) => {
      if (category !== "other" && e.category && e.category !== category) return false;
      if (category === "other" && ["restaurant", "cafe", "bar", "bakery"].includes(e.category || ""))
        return false;
      return true;
    });
  }, [eats, category]);

  function formatPriceLevel(eat: any): string {
    const pl = eat.price_level;
    if (pl && pl > 0) return "₹".repeat(Math.min(4, pl));
    if (eat.price_range) return eat.price_range;
    return "₹₹";
  }

  function heroPhoto(eat: any): string | null {
    const photos = Array.isArray(eat.photos) && eat.photos.length > 0 ? eat.photos : [];
    for (const p of photos) {
      if (p && p.includes("googleusercontent")) return p;
    }
    return null;
  }

  return (
    <div className="min-h-screen bg-[#fbfbfa] text-stone-900 pb-24">
      <header className="border-b border-stone-200/80 bg-white/90 backdrop-blur-md sticky top-0 z-30 shadow-xs">
        <div className="mx-auto max-w-[1440px] px-4 py-3.5 sm:px-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-amber-600 text-white flex items-center justify-center font-bold shadow-xs">
              <Utensils className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-stone-900">Eats & Dining</h1>
              <p className="text-xs text-stone-500">Real restaurants, cafes & bars from Google Maps</p>
            </div>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-[1440px] px-4 sm:px-6 py-6">
        <div className="rounded-3xl border border-stone-200/90 bg-white p-6 shadow-sm mb-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
            {/* Destination Input */}
            <div className="lg:col-span-6 xl:col-span-7">
              <div className="relative group">
                <MapPin className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
                <input
                  type="text"
                  value={destination}
                  onChange={(e) => setDestination(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && executeSearch()}
                  placeholder="e.g. Delhi, Paris, Bangkok, Rome"
                  className="w-full rounded-2xl border border-stone-200 bg-stone-50/50 pl-12 pr-4 py-3 text-sm font-semibold text-stone-900 placeholder:text-stone-400 focus:border-amber-500 focus:bg-white focus:ring-1 focus:ring-amber-500 focus:outline-hidden transition-all"
                />
              </div>
              <p className="text-[10px] text-stone-400 mt-1">
                Enter a city to find live restaurants, cafes, bars & bakeries
              </p>
            </div>

            {/* Category Selector */}
            <div className="lg:col-span-3 xl:col-span-2 flex flex-col items-end">
              <label className="block text-[10px] font-bold uppercase tracking-wider text-stone-500 mb-2 text-right">
                Category
              </label>
              <div className="relative w-full max-w-sm">
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full rounded-xl border border-stone-200 bg-white pl-10 pr-4 py-2.5 text-sm font-semibold text-stone-900 placeholder:text-stone-400 focus:border-amber-500 focus:bg-white focus:ring-1 focus:ring-amber-500 focus:outline-hidden transition-all appearance-none cursor-pointer"
                >
                  {EAT_CATEGORIES.map((c) => (
                    <option key={c.key} value={c.key}>
                      {c.label}
                    </option>
                  ))}
                </select>
                <div className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400 pointer-events-none">
                  <Utensils className="w-4 h-4" />
                </div>
                <div className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400 pointer-events-none">
                  <ChevronDown className="w-4 h-4" />
                </div>
              </div>
            </div>

            {/* Search Button */}
            <div className="lg:col-span-3 xl:col-span-3 flex items-end">
              <button
                type="button"
                onClick={() => executeSearch()}
                disabled={loading}
                className="w-full rounded-2xl bg-stone-900 py-3 px-6 text-sm font-bold text-white shadow-xs hover:bg-stone-800 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <div className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                    <span className="ml-1">Searching…</span>
                  </>
                ) : (
                  <>
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      className="w-4 h-4"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                      />
                    </svg>
                    <span className="ml-1">
                      Search {category.charAt(0).toUpperCase() + category.slice(1)}s
                    </span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Popular destination quick chips */}
          <div className="mt-6 pt-4 border-t border-stone-100 flex flex-wrap items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-stone-400 mr-1">
              Popular:
            </span>
            {POPULAR_DESTINATIONS.map((pop) => (
              <button
                key={pop.city}
                type="button"
                onClick={() => setDestination(pop.city)}
                className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-all border ${
                  destination.toLowerCase() === pop.city.toLowerCase()
                    ? "bg-amber-600 border-amber-600 text-white shadow-sm"
                    : "border-stone-200 bg-white text-stone-600 hover:bg-stone-50 hover:border-stone-300"
                }`}
              >
                {pop.city}
              </button>
            ))}
          </div>
        </div>

        {loading && (
          <div className="rounded-2xl bg-amber-500/10 border border-amber-300/40 p-4 mb-6 flex items-center gap-3 text-amber-900 text-xs font-semibold animate-pulse">
            <div className="w-4 h-4 rounded-full border-2 border-amber-600/30 border-t-amber-600 animate-spin shrink-0" />
            <span>{loadingStatus || `Live scraping Google Maps for ${destination}...`}</span>
          </div>
        )}

        {errorMsg && (
          <div className="rounded-2xl bg-rose-50 border border-rose-200 p-4 mb-6 flex items-center gap-3 text-rose-800 text-xs font-medium">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-[1fr]">
          <main>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-base font-bold text-stone-900">
                  {filteredEats.length} {category.charAt(0).toUpperCase() + category.slice(1)}{filteredEats.length !== 1 ? "s" : ""} Available
                </h2>
                <p className="text-xs text-stone-500">in {destination} • Sorted by rating</p>
              </div>
            </div>

            {!loading && filteredEats.length === 0 && (
              <div className="rounded-3xl border border-stone-200/90 bg-white p-16 text-center">
                <Utensils className="w-16 h-16 text-stone-300 mx-auto mb-4" />
                <h3 className="text-base font-bold text-stone-900 mb-1">
                  {hasSearched ? `No ${category} found for "${destination}"` : "Discover great places to eat"}
                </h3>
                <p className="text-xs text-stone-500 mb-6">
                  {hasSearched
                    ? `We could not find any live ${category} listings for ${destination}. Please verify the city name or try another category.`
                    : "Search for a city to discover authentic restaurants, cafes, bars and bakeries nearby."}
                </p>
                {hasSearched && (
                  <button
                    type="button"
                    onClick={() => setErrorMsg("")}
                    className="rounded-full bg-stone-900 px-4 py-2 text-xs font-bold text-white hover:bg-stone-800"
                  >
                    Try Another Destination
                  </button>
                )}
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
              {filteredEats.map((eat: any, idx) => {
                const photos = Array.isArray(eat.photos) && eat.photos.length > 0 ? eat.photos : [];
                const catKey: string = (eat.category || category) as string;
                const catLabel =
                  CATEGORY_LABEL[catKey as keyof typeof CATEGORY_LABEL] ||
                  eat.category ||
                  category;
                const CatIcon =
                  ICON_BY_CATEGORY[catKey as keyof typeof ICON_BY_CATEGORY] || Utensils;

                return (
                  <article
                    key={`${eat.id || "eat"}-${idx}`}
                    onClick={() => fetchEatDetail(eat.id || eat.name)}
                    className="rounded-3xl border border-stone-200/80 bg-white shadow-xs overflow-hidden flex flex-col hover:shadow-md hover:border-stone-400 transition-all group cursor-pointer"
                  >
                    <div className="relative h-48 w-full overflow-hidden bg-stone-100">
                      {heroPhoto(eat) ? (
                        <Image
                          src={heroPhoto(eat)!}
                          alt={eat.name}
                          className="object-cover group-hover:scale-105 transition-transform duration-500"
                          fill
                          sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
                          priority={idx < 3}
                        />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center bg-stone-100">
                          <MapPin className="w-8 h-8 text-stone-400" />
                        </div>
                      )}
                      <div className="absolute top-3 left-3 flex items-center gap-1.5 rounded-full border border-white/50 bg-white/80 px-2.5 py-1 text-[10px] font-semibold text-stone-800 backdrop-blur shadow-xs">
                        <CatIcon className={`w-3 h-3 ${category === "restaurant" ? "text-amber-600" : "text-stone-600"}`} />
                        <span>{catLabel}</span>
                      </div>
                      {eat.rating != null && (
                        <div className="absolute top-3 right-3 bg-white/95 backdrop-blur-md px-2.5 py-1 rounded-full text-xs font-black text-stone-900 shadow-xs flex items-center gap-1">
                          <span className="text-amber-500 font-bold">★</span>
                          <span>{typeof eat.rating === "number" ? eat.rating.toFixed(1) : eat.rating}</span>
                        </div>
                      )}
                    </div>

                    <div className="p-4 flex-1 flex flex-col justify-between">
                      <div>
                        <div className="flex items-start justify-between gap-2 mb-1">
                          <h3 className="font-bold text-sm text-stone-900 group-hover:text-amber-700 transition-colors line-clamp-1">
                            {eat.name}
                          </h3>
                          {eat.rating != null && (
                            <span className="flex items-center gap-1 rounded-full border border-line bg-white px-2 py-0.5 text-[11px] font-medium text-ink shrink-0">
                              <Star size={12} className="text-amber-400 fill-amber-400" />
                              {typeof eat.rating === "number" ? eat.rating.toFixed(1) : eat.rating}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-stone-500 line-clamp-1 mb-2.5">
                          {eat.address || `${eat.destination || destination}`}
                        </p>
                        {eat.review_count > 0 && (
                          <p className="text-[11px] font-semibold text-stone-400 mb-3">
                            {eat.review_count.toLocaleString()} verified reviews
                          </p>
                        )}
                        <div className="flex items-center gap-2 mb-3">
                          <span className="rounded-lg bg-stone-100 px-2 py-0.5 text-[10px] font-bold text-stone-600">
                            {formatPriceLevel(eat)}
                          </span>
                          {eat.tags && eat.tags.length > 0 && (
                            <span className="rounded-lg bg-stone-50 px-1.5 py-0.5 text-[10px] font-medium text-stone-400 truncate max-w-[120px]">
                              {eat.tags[0]}
                            </span>
                          )}
                        </div>
                      </div>

                      <div>
                        <button
                          type="button"
                          onClick={() => fetchEatDetail(eat.id || eat.name)}
                          className="w-full mt-3 rounded-xl bg-stone-900/90 py-2 px-3 text-xs font-bold text-white hover:bg-stone-900 transition-colors flex items-center justify-center gap-1.5 shadow-2xs"
                        >
                          {detailLoading ? (
                            <>
                              <div className="w-3 h-3 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                              <span className="ml-1">Loading details...</span>
                            </>
                          ) : (
                            <>
                              <span>View Details</span>
                              <ChevronRight className="w-3.5 h-3.5" />
                            </>
                          )}
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

      {selectedEat && (
        <PlaceDetailModal card={selectedEat} onClose={() => setSelectedEat(null)} />
      )}
    </div>
  );
}
