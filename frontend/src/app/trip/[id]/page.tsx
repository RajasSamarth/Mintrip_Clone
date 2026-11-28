"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import {
  ChevronLeft,
  MapPin,
  Clock,
  Share2,
  MoreHorizontal,
  Bed,
  Plane,
  Star,
  Trash2,
  ExternalLink,
  Plus,
  Sparkles,
  ChevronDown,
  Check,
  Compass,
  Landmark,
  Eye,
  Loader2,
  GripVertical,
  MessageSquare,
  AlertCircle,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import {
  CURRENCIES,
  formatFlightPriceDisplay,
  formatPriceInCurrency,
  convertAmount,
} from "@/lib/currencies";
import { getDestinationPhoto, DEFAULT_DESTINATION_COVER } from "@/lib/destinations";
import { InteractiveMap } from "@/components/map/InteractiveMap";
import { PlaceDetailModal } from "@/components/chat/PlaceDetailModal";

const SLOT_LABEL: Record<string, string> = {
  morning: "Morning",
  afternoon: "Afternoon",
  evening: "Evening",
};

function formatFlightTime(timeStr?: string): string {
  if (!timeStr) return "";
  if (timeStr.includes("T")) {
    try {
      const d = new Date(timeStr);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return timeStr;
    }
  }
  return timeStr;
}

export default function TripPage({ params }: { params: { id: string } }) {
  const [trip, setTrip] = useState<any>(null);
  const [activeDay, setActiveDay] = useState(1);
  const [mapOpen, setMapOpen] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCurrency, setSelectedCurrency] = useState<string>("INR");
  const [showCurrencyDropdown, setShowCurrencyDropdown] = useState(false);
  const [heroPhoto, setHeroPhoto] = useState<string>("");

  // Recommended places state
  const [recommendedPlaces, setRecommendedPlaces] = useState<any[]>([]);
  const [loadingRecs, setLoadingRecs] = useState<boolean>(false);
  const [recCategory, setRecCategory] = useState<string>("all");
  const [addingStopId, setAddingStopId] = useState<string | null>(null);
  const [addedSuccessId, setAddedSuccessId] = useState<string | null>(null);
  const [selectedPlaceForModal, setSelectedPlaceForModal] = useState<any | null>(null);
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  // Confirm removal dialogs
  const [confirmRemoveType, setConfirmRemoveType] = useState<"hotel" | "flight" | null>(null);

  // Temporary "Booked" state
  const [bookedItem, setBookedItem] = useState<"hotel" | "flight" | null>(null);
  const [shareCopied, setShareCopied] = useState(false);
  const [showExportMenu, setShowExportMenu] = useState(false);

  // Recommendations search
  const [recSearchQuery, setRecSearchQuery] = useState("");
  const [recSearchResults, setRecSearchResults] = useState<any[]>([]);
  const [recSearchLoading, setRecSearchLoading] = useState(false);
  const [recSearchError, setRecSearchError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const res = await api(`/trips/${params.id}`);
        const json = await res.json();
        setTrip(json);
        setActiveDay(json?.days?.[0]?.day_index || 1);
        const detectedCurrency =
          json?.flight?.selected_currency ||
          json?.flight?.currency ||
          (json?.hotel?.currency ? (json.hotel.currency.toUpperCase() === "USD" ? "USD" : "INR") : null) ||
          "INR";
        setSelectedCurrency(detectedCurrency);

        const photo = json?.cover_photo || getDestinationPhoto(json?.destination);
        setHeroPhoto(photo);
      } catch (err: any) {
        console.error("Failed to load trip:", err);
        setError("We couldn't locate this itinerary. It may have expired or not been saved yet.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [params.id]);

  // Fetch recommended spots for destination
  useEffect(() => {
    if (!trip?.destination) return;
    async function fetchRecommendations() {
      setLoadingRecs(true);
      try {
        const res = await api(`/places/recommended?destination=${encodeURIComponent(trip.destination)}&limit=16`);
        if (res.ok) {
          const json = await res.json();
          setRecommendedPlaces(json.places || []);
        }
      } catch (err) {
        console.error("Failed to load recommended places:", err);
      } finally {
        setLoadingRecs(false);
      }
    }
    fetchRecommendations();
  }, [trip?.destination]);

  async function reloadTrip() {
    try {
      const res = await api(`/trips/${params.id}`);
      const json = await res.json();
      setTrip(json);
      const detectedCurrency =
        json?.flight?.selected_currency ||
        json?.flight?.currency ||
        selectedCurrency ||
        "INR";
      setSelectedCurrency(detectedCurrency);
      if (json?.cover_photo) {
        setHeroPhoto(json.cover_photo);
      }
    } catch (err) {
      console.error("Failed to reload trip:", err);
    }
  }

  async function handleRemoveHotel() {
    setConfirmRemoveType("hotel");
  }

  async function handleConfirmRemoveHotel() {
    setConfirmRemoveType(null);
    try {
      await api(`/trips/${params.id}/hotel`, { method: "DELETE" });
      await reloadTrip();
    } catch (err) {
      console.error("Failed to remove hotel:", err);
      setRecSearchError("Could not remove hotel. Please try again.");
    }
  }

  async function handleRemoveFlight() {
    setConfirmRemoveType("flight");
  }

  async function handleConfirmRemoveFlight() {
    setConfirmRemoveType(null);
    try {
      await api(`/trips/${params.id}/flight`, { method: "DELETE" });
      await reloadTrip();
    } catch (err) {
      console.error("Failed to remove flight:", err);
      setRecSearchError("Could not remove flight. Please try again.");
    }
  }

  async function handleCancelRemove() {
    setConfirmRemoveType(null);
  }

  // Temporary "Book" button handlers (UI-only, reflects booked state briefly)
  function handleBookHotel() {
    setBookedItem("hotel");
    setTimeout(() => setBookedItem(null), 4000);
  }

  function handleBookFlight() {
    setBookedItem("flight");
    setTimeout(() => setBookedItem(null), 4000);
  }

  // Recommendations search via Google Maps scraper
  async function handleRecSearch() {
    const q = recSearchQuery.trim();
    if (!q || !trip?.destination) return;
    setRecSearchLoading(true);
    setRecSearchError(null);
    try {
      const res = await api("/places/search/live", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: q,
          destination: trip.destination,
          category: recCategory === "all" ? undefined : recCategory,
          max_results: 8,
        }),
      });
      if (res.ok) {
        const json = await res.json();
        setRecSearchResults(json.places || []);
      } else {
        setRecSearchError("Search failed. Please try again.");
      }
    } catch (err) {
      console.error("Recommendation search failed:", err);
      setRecSearchError("Search failed. Please try again.");
    } finally {
      setRecSearchLoading(false);
    }
  }

  const handleDragStart = (index: number) => {
    setDraggedIndex(index);
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    if (draggedIndex === null || draggedIndex === index) return;
    setDragOverIndex(index);
  };

  const handleDropStop = async (dropIndex: number) => {
    if (draggedIndex === null || draggedIndex === dropIndex) {
      setDraggedIndex(null);
      setDragOverIndex(null);
      return;
    }
    const currentDay = trip?.days?.find((d: any) => d.day_index === activeDay);
    if (!currentDay) return;

    const currentStops = [...currentDay.stops];
    const [moved] = currentStops.splice(draggedIndex, 1);
    currentStops.splice(dropIndex, 0, moved);

    // Optimistic UI update
    setTrip((prev: any) => {
      if (!prev) return prev;
      const updatedDays = prev.days.map((d: any) => {
        if (d.day_index === activeDay) {
          return { ...d, stops: currentStops };
        }
        return d;
      });
      return { ...prev, days: updatedDays };
    });

    setDraggedIndex(null);
    setDragOverIndex(null);

    try {
      const stopIds = currentStops.map((s: any) => s.id);
      await api(`/trips/${params.id}/reorder`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ day_index: activeDay, stop_ids: stopIds }),
      });
    } catch (err) {
      console.warn("Could not save stop reorder:", err);
    }
  };

  async function handleAddStopToTrip(spot: any) {
    setAddingStopId(spot.id);
    try {
      const res = await api(`/trips/${params.id}/stops`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          day_index: activeDay,
          place_id: spot.id,
          time_slot: "afternoon",
          notes: spot.description?.slice(0, 160) || `Exploring ${spot.name}`,
        }),
      });
      if (res.ok) {
        setAddedSuccessId(spot.id);
        setTimeout(() => setAddedSuccessId(null), 3000);
        await reloadTrip();
      }
    } catch (err) {
      console.error("Failed to add stop to trip:", err);
    } finally {
      setAddingStopId(null);
    }
  }

  async function handleRemoveStop(stopId: number) {
    if (!confirm("Are you sure you want to remove this stop from your itinerary?")) return;
    try {
      await api(`/trips/${params.id}/stops/${stopId}`, { method: "DELETE" });
      await reloadTrip();
    } catch (err) {
      console.error("Failed to remove stop:", err);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-paper flex flex-col items-center justify-center p-6 text-center">
        <div className="shimmer size-16 rounded-full mb-4"></div>
        <p className="text-lg font-serif-italic text-ink">Preparing your journey...</p>
        <p className="text-xs text-muted mt-1">Loading stops, routes and maps</p>
      </div>
    );
  }

  if (error || !trip) {
    return (
      <div className="min-h-screen bg-paper flex flex-col items-center justify-center p-6 text-center">
        <h2 className="text-2xl font-serif-italic text-ink mb-2">Trip Not Found</h2>
        <p className="text-sm text-muted max-w-md mb-6">{error || "Could not load this trip."}</p>
        <div className="flex gap-3">
          <Link href="/trips" className="rounded-full border border-line bg-white px-5 py-2 text-sm font-medium text-ink hover:bg-ink/5">
            Browse trips
          </Link>
          <Link href="/chat" className="rounded-full bg-ink px-5 py-2 text-sm font-medium text-white hover:bg-ink-soft">
            Plan new trip
          </Link>
        </div>
      </div>
    );
  }

  const day = trip?.days?.find((d: any) => d.day_index === activeDay) || trip?.days?.[0];

  // Filter recommended spots
  const filteredSpots = recommendedPlaces.filter((spot) => {
    if (recCategory === "all") return true;
    if (recCategory === "attraction") {
      return ["attraction", "heritage", "landmark", "sight", "monument"].includes(spot.category?.toLowerCase());
    }
    if (recCategory === "nature") {
      return ["nature", "park", "garden", "mountain", "viewpoint"].includes(spot.category?.toLowerCase());
    }
    if (recCategory === "culture") {
      return ["culture", "temple", "museum", "historic", "sacred"].includes(spot.category?.toLowerCase());
    }
    if (recCategory === "dining") {
      return ["restaurant", "food", "cafe", "bar"].includes(spot.category?.toLowerCase());
    }
    return spot.category?.toLowerCase() === recCategory;
  });

  // Calculate pins for OpenStreetMap
  const dayStops = day?.stops || [];
  const dayPins = dayStops.map((s: any, i: number) => ({
    id: s.place_id || `stop-${s.id}`,
    name: s.place?.name || "Stop",
    category: s.place?.category || "attraction",
    lat: s.place?.lat || 0,
    lon: s.place?.lon || 0,
    rating: s.place?.rating,
    address: s.place?.address,
    photo: s.place?.photos?.[0],
    day_index: activeDay,
    order: i,
    label: String(i + 1),
    is_itinerary_stop: true,
  }));

  const hotelPins = trip?.hotel?.lat && trip?.hotel?.lon ? [{
    id: `hotel-${trip.hotel.id || "primary"}`,
    name: trip.hotel.name,
    category: "hotel",
    lat: trip.hotel.lat,
    lon: trip.hotel.lon,
    rating: trip.hotel.rating,
    address: trip.hotel.address,
    photo: trip.hotel.photos?.[0],
    label: "★",
    is_itinerary_stop: false,
  }] : [];

  const recPins = recommendedPlaces.filter((p) => p.lat && p.lon).map((p) => ({
    id: p.id,
    name: p.name,
    category: "recommended",
    lat: p.lat,
    lon: p.lon,
    rating: p.rating,
    address: p.address,
    photo: p.photos?.[0],
    label: "•",
    is_itinerary_stop: false,
  }));

  const allPins = [...dayPins, ...hotelPins, ...recPins];

  return (
    <div className="min-h-screen bg-paper">
      {/* Header with Specific Destination Photo */}
      <header className="relative h-[36vh] w-full overflow-hidden bg-stone-900">
        <Image
          src={heroPhoto || getDestinationPhoto(trip.destination)}
          alt={trip.title || trip.destination}
          className="absolute inset-0 size-full object-cover transition-opacity duration-700"
          sizes="(max-width: 768px) 100vw, 100vw"
          priority
          fill
          onError={() => setHeroPhoto(DEFAULT_DESTINATION_COVER)}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-ink/90 via-ink/30 to-transparent" />
        <div className="absolute bottom-0 left-0 right-0 p-6 sm:p-10 pb-10">
          <div className="max-w-[1400px] mx-auto px-4 sm:px-8">
            <div className="flex items-center gap-2 mb-3 flex-wrap">
              <Link
                href="/trips"
                className="inline-flex items-center gap-1.5 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-medium text-white backdrop-blur hover:bg-white/20 transition-all"
              >
                <ChevronLeft size={14} /> Trips
              </Link>
              <span className="rounded-full border border-white/15 bg-white/10 px-2 py-0.5 text-[10px] font-medium text-white/80 backdrop-blur">
                {trip.traveler_type || "Traveler"}
              </span>
              <span className="rounded-full border border-white/15 bg-white/10 px-2.5 py-0.5 text-[10px] font-medium text-white/80 backdrop-blur">
                {trip.budget
                  ? `${formatPriceInCurrency(
                      convertAmount(trip.budget, "USD", selectedCurrency),
                      selectedCurrency
                    )} budget`
                  : "Flexible budget"}
              </span>

              {/* Currency Selector Badge */}
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setShowCurrencyDropdown(!showCurrencyDropdown)}
                  className="inline-flex items-center gap-1 rounded-full border border-white/20 bg-white/15 px-2.5 py-0.5 text-[10px] font-bold text-white backdrop-blur hover:bg-white/25 transition-all shadow-2xs"
                  title="Switch itinerary display currency"
                >
                  <span>{CURRENCIES[selectedCurrency]?.symbol || "₹"}</span>
                  <span>{selectedCurrency}</span>
                  <ChevronDown size={11} className="opacity-80" />
                </button>
                {showCurrencyDropdown && (
                  <div className="absolute left-0 top-full mt-1.5 z-30 w-36 rounded-2xl border border-stone-200 bg-white p-1.5 shadow-xl text-stone-900 animate-fade-in">
                    {["INR", "USD", "EUR", "GBP", "AED", "JPY", "SGD", "CAD"].map((code) => {
                      const c = CURRENCIES[code];
                      return (
                        <button
                          key={code}
                          type="button"
                          onClick={() => {
                            setSelectedCurrency(code);
                            setShowCurrencyDropdown(false);
                          }}
                          className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-xl text-xs font-semibold transition-colors ${
                            selectedCurrency === code
                              ? "bg-stone-900 text-white"
                              : "text-stone-700 hover:bg-stone-100"
                          }`}
                        >
                          <span>{code}</span>
                          <span>{c.symbol}</span>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
            <div className="flex items-center justify-between gap-4 flex-wrap mb-2">
              <h1 className="text-[2.75rem] font-serif-italic text-white leading-[1.08] tracking-tight sm:text-[3.75rem]">{trip.title}</h1>
              <Link
                href={`/chat?trip_id=${trip.id}&session_id=${trip.session_id || ""}`}
                className="inline-flex items-center gap-2 rounded-full bg-white/20 hover:bg-white/30 backdrop-blur-md px-4 py-2 text-xs font-bold text-white shadow-sm border border-white/30 transition-all active:scale-95 shrink-0"
              >
                <Sparkles size={14} className="text-amber-300 animate-pulse" />
                <span>Ask AI Concierge</span>
              </Link>
            </div>
            <p className="mb-5 max-w-2xl text-white/90 text-base leading-relaxed sm:text-lg">{trip.summary}</p>
            <div className="flex items-center gap-4 text-xs sm:text-sm text-white/80 flex-wrap">
              <span className="flex items-center gap-1 font-medium">
                <MapPin size={14} className="text-amber-400" /> {trip.destination}
              </span>
              <span className="flex items-center gap-1">
                <Clock size={14} /> {trip.start_date} — {trip.end_date}
              </span>
              <span className="flex items-center gap-1">
                <Landmark size={14} /> {trip.day_count} days · {trip.stop_count} stops
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Layout (Itinerary Column: 68%, Map Column: 32% on right side) */}
      <div className="max-w-[1400px] mx-auto px-4 sm:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          
          {/* Main Left Column: Stays, Flights, Day Timeline, Recommended Spots */}
          <div className="lg:col-span-8 xl:col-span-8 space-y-8">
            
            {/* Booked Accommodations & Flights Overview */}
            <div className="space-y-4">
              {/* Hotel Section */}
              {trip.hotel ? (
                <div className="rounded-3xl border border-stone-200 bg-white p-5 shadow-xs overflow-hidden">
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                    <div className="flex items-center gap-4">
                      <div className="relative w-20 h-20 rounded-2xl overflow-hidden bg-stone-100 shrink-0 border border-stone-100">
                        <img
                          src={trip.hotel.photos?.[0] || "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=800&q=80"}
                          alt={trip.hotel.name}
                          className="w-full h-full object-cover"
                          referrerPolicy="no-referrer"
                        />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="inline-flex items-center gap-1 rounded-full bg-stone-100 px-2.5 py-0.5 text-[10px] font-bold text-stone-700">
                            <Bed className="w-3 h-3 text-amber-600" /> Booked Stay
                          </span>
                          {trip.hotel.stars > 0 && (
                            <span className="flex text-amber-500 text-xs">
                              {[...Array(trip.hotel.stars)].map((_, i) => (
                                <Star key={i} className="w-2.5 h-2.5 fill-amber-500" />
                              ))}
                            </span>
                          )}
                        </div>
                        <h3 className="text-base font-bold text-stone-900 mt-1">{trip.hotel.name}</h3>
                        <p className="text-xs text-stone-500 line-clamp-1">{trip.hotel.address}</p>
                        {trip.hotel.price_per_night && (
                          <p className="text-xs font-bold text-stone-900 mt-1">
                            {formatPriceInCurrency(
                              convertAmount(
                                trip.hotel.price_per_night,
                                (trip.hotel.currency || "INR").toUpperCase(),
                                selectedCurrency
                              ),
                              selectedCurrency
                            )}{" "}
                            <span className="text-[10px] text-stone-400 font-normal">/ night</span>
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="flex sm:flex-col items-center sm:items-end justify-between w-full sm:w-auto gap-2 border-t sm:border-t-0 pt-3 sm:pt-0 border-stone-100">
                      {confirmRemoveType === "hotel" ? (
                        <div className="flex flex-col items-center gap-2 w-full border border-stone-200 rounded-xl bg-stone-50 p-3">
                          <AlertCircle className="w-4 h-4 text-amber-600" />
                          <p className="text-xs font-semibold text-stone-800">Remove this hotel?</p>
                          <div className="flex gap-2 w-full">
                            <button
                              type="button"
                              onClick={handleConfirmRemoveHotel}
                              className="flex-1 px-3 py-1.5 rounded-xl bg-ink text-white text-xs font-bold hover:bg-ink-soft transition-colors"
                            >
                              Yes, remove
                            </button>
                            <button
                              type="button"
                              onClick={handleCancelRemove}
                              className="flex-1 px-3 py-1.5 rounded-xl border border-stone-300 text-stone-600 text-xs font-bold hover:bg-stone-100 transition-colors"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <a
                            href={trip.hotel.booking_url || `https://www.google.com/travel/hotels/${encodeURIComponent(trip.destination)}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="rounded-xl border border-stone-200 bg-white px-3 py-1.5 text-xs font-bold text-stone-800 hover:bg-stone-50 flex items-center gap-1.5 shadow-2xs transition-colors"
                          >
                            <span>View Deal</span>
                            <ExternalLink className="w-3 h-3 text-stone-400" />
                          </a>
                          {bookedItem === "hotel" ? (
                            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 text-emerald-700 px-2.5 py-0.5 text-[10px] font-bold">
                              <Check size={12} /> Booked
                            </span>
                          ) : (
                            <button
                              type="button"
                              onClick={handleBookHotel}
                              className="inline-flex items-center justify-center gap-1 rounded-xl border border-stone-200 bg-white px-3 py-1.5 text-xs font-bold text-stone-800 hover:bg-stone-50 shadow-2xs transition-colors"
                            >
                              <Plus size={12} /> Book
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={handleRemoveHotel}
                            className="text-[11px] font-semibold text-stone-400 hover:text-red-600 flex items-center gap-1 transition-colors"
                          >
                            <Trash2 className="w-3 h-3" />
                            <span>Remove stay</span>
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="rounded-3xl border border-dashed border-stone-200 bg-stone-50/50 p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-2xl bg-amber-50 border border-amber-200/60 text-amber-700 flex items-center justify-center shrink-0">
                      <Bed className="w-4 h-4" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-stone-900">No hotel booked yet</p>
                      <p className="text-[11px] text-stone-500">Browse verified stays in {trip.destination} with live rates</p>
                    </div>
                  </div>
                  <Link
                    href={`/stays?destination=${encodeURIComponent(trip.destination)}&auto_search=1`}
                    className="rounded-xl bg-white border border-stone-300 px-3 py-1.5 text-xs font-bold text-stone-800 hover:bg-stone-100 flex items-center gap-1 shadow-2xs transition-colors"
                  >
                    <Plus className="w-3 h-3 text-amber-600" />
                    <span>Find Stays</span>
                  </Link>
                </div>
              )}

              {/* Flight Section */}
              {trip.flight ? (
                <div className="rounded-3xl border border-stone-200 bg-white p-5 shadow-xs overflow-hidden">
                  {(() => {
                    const ret = trip.flight.return_flight || trip.flight.metadata?.return_flight;
                    const pax = trip.flight.passengers || trip.flight.metadata?.passengers || 1;
                    const isRoundTrip = Boolean(ret || trip.flight.trip_type === "round-trip");
                    return (
                      <div className="space-y-4">
                        {/* Outbound Leg */}
                        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                          <div className="flex items-center gap-4">
                            <div className="w-12 h-12 rounded-2xl bg-stone-900 text-white flex items-center justify-center font-black text-sm shrink-0">
                              {trip.flight.airline_code || trip.flight.airline?.slice(0, 2).toUpperCase() || <Plane className="w-5 h-5" />}
                            </div>
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="inline-flex items-center gap-1 rounded-full bg-stone-100 px-2.5 py-0.5 text-[10px] font-bold text-stone-700">
                                  <Plane className="w-3 h-3 text-sky-600" />
                                  {isRoundTrip ? "Outbound Flight" : "Booked Flight"}
                                </span>
                                <span className="text-xs font-bold text-stone-900">{trip.flight.airline}</span>
                                {trip.flight.flight_number && (
                                  <span className="text-[11px] text-stone-400">· {trip.flight.flight_number}</span>
                                )}
                              </div>
                              <p className="text-sm font-black text-stone-900 mt-1">
                                {trip.flight.origin} → {trip.flight.destination}{" "}
                                <span className="text-xs font-normal text-stone-500">
                                  ({formatFlightTime(trip.flight.departure_time)} - {formatFlightTime(trip.flight.arrival_time)})
                                </span>
                              </p>
                              <p className="text-[11px] text-stone-500">
                                {trip.flight.stops === 0 ? "Nonstop" : `${trip.flight.stops} stop(s)`} · {trip.flight.cabin || "Economy"}
                              </p>
                            </div>
                          </div>

                          <div className="flex sm:flex-col items-center sm:items-end justify-between w-full sm:w-auto gap-2 border-t sm:border-t-0 pt-3 sm:pt-0 border-stone-100">
                            {confirmRemoveType === "flight" ? (
                              <div className="flex flex-col items-center gap-2 w-full border border-stone-200 rounded-xl bg-stone-50 p-3">
                                <AlertCircle className="w-4 h-4 text-amber-600" />
                                <p className="text-xs font-semibold text-stone-800">Remove this flight?</p>
                                <div className="flex gap-2 w-full">
                                  <button
                                    type="button"
                                    onClick={handleConfirmRemoveFlight}
                                    className="flex-1 px-3 py-1.5 rounded-xl bg-ink text-white text-xs font-bold hover:bg-ink-soft transition-colors"
                                  >
                                    Yes, remove
                                  </button>
                                  <button
                                    type="button"
                                    onClick={handleCancelRemove}
                                    className="flex-1 px-3 py-1.5 rounded-xl border border-stone-300 text-stone-600 text-xs font-bold hover:bg-stone-100 transition-colors"
                                  >
                                    Cancel
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <>
                                <div className="text-left sm:text-right">
                                  <span className="text-base font-black text-stone-900">
                                    {formatFlightPriceDisplay(trip.flight, selectedCurrency)}
                                  </span>
                                  <span className="text-[10px] text-stone-400 block">
                                    {pax > 1 ? `total for ${pax} travelers` : "total (1 traveler)"}
                                  </span>
                                </div>
                                <div className="flex items-center gap-2 w-full">
                                  {bookedItem === "flight" ? (
                                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 text-emerald-700 px-2.5 py-0.5 text-[10px] font-bold">
                                      <Check size={12} /> Booked
                                    </span>
                                  ) : (
                                    <button
                                      type="button"
                                      onClick={handleBookFlight}
                                      className="flex-1 inline-flex items-center justify-center gap-1 rounded-xl border border-stone-200 bg-white px-3 py-1.5 text-xs font-bold text-stone-800 hover:bg-stone-50 shadow-2xs transition-colors"
                                    >
                                      <Plus size={12} /> Book
                                    </button>
                                  )}
                                  <button
                                    type="button"
                                    onClick={handleRemoveFlight}
                                    className="flex-1 text-[11px] font-semibold text-stone-400 hover:text-red-600 flex items-center justify-center gap-1 transition-colors"
                                  >
                                    <Trash2 className="w-3 h-3" />
                                    <span>Remove flight</span>
                                  </button>
                                </div>
                              </>
                            )}
                          </div>
                        </div>

                        {/* Return Flight if Round-Trip */}
                        {ret && (
                          <div className="pt-3 border-t border-stone-100 flex items-center justify-between gap-4">
                            <div className="flex items-center gap-4">
                              <div className="w-12 h-12 rounded-2xl bg-amber-50 border border-amber-200/80 text-amber-900 flex items-center justify-center font-black text-sm shrink-0">
                                {ret.airline_code || ret.airline?.slice(0, 2).toUpperCase() || <Plane className="w-5 h-5 rotate-180" />}
                              </div>
                              <div>
                                <div className="flex items-center gap-2">
                                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-[10px] font-bold text-amber-900">
                                    <Plane className="w-3 h-3 text-amber-700 rotate-180" /> Return Flight
                                  </span>
                                  <span className="text-xs font-bold text-stone-900">{ret.airline}</span>
                                  {ret.flight_number && (
                                    <span className="text-[11px] text-stone-400">· {ret.flight_number}</span>
                                  )}
                                </div>
                                <p className="text-sm font-black text-stone-900 mt-1">
                                  {ret.origin} → {ret.destination}{" "}
                                  <span className="text-xs font-normal text-stone-500">
                                    ({formatFlightTime(ret.departure_time)} - {formatFlightTime(ret.arrival_time)})
                                  </span>
                                </p>
                                <p className="text-[11px] text-stone-500">
                                  {ret.stops === 0 ? "Nonstop" : `${ret.stops} stop(s)`} · Return date: {ret.date || "Scheduled"}
                                </p>
                              </div>
                            </div>
                            <div className="hidden sm:block text-right">
                              <span className="inline-block text-[10px] font-bold uppercase tracking-wider text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full">
                                Round-trip Included
                              </span>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </div>
              ) : (
                <div className="rounded-3xl border border-dashed border-stone-200 bg-stone-50/50 p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-2xl bg-sky-50 border border-sky-200/60 text-sky-700 flex items-center justify-center shrink-0">
                      <Plane className="w-4 h-4" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-stone-900">No flight linked yet</p>
                      <p className="text-[11px] text-stone-500">Search live airline routes to {trip.destination}</p>
                    </div>
                  </div>
                  <Link
                    href={`/flights?destination=${encodeURIComponent(trip.destination)}`}
                    className="rounded-xl bg-white border border-stone-300 px-3 py-1.5 text-xs font-bold text-stone-800 hover:bg-stone-100 flex items-center gap-1 shadow-2xs transition-colors"
                  >
                    <Plus className="w-3 h-3 text-sky-600" />
                    <span>Find Flights</span>
                  </Link>
                </div>
              )}
            </div>

            {/* Day Selector */}
            <div className="flex items-baseline justify-between pt-2">
              <div>
                <h2 className="text-2xl font-serif-italic tracking-tight text-ink">Day-by-day Itinerary</h2>
                <p className="text-xs text-muted">Select a day to view stops and route timeline</p>
              </div>
              <div className="flex gap-2 overflow-x-auto thin-scrollbar pb-1 no-scrollbar">
                {trip.days.map((d: any) => (
                  <button
                    key={d.day_index}
                    onClick={() => setActiveDay(d.day_index)}
                    className={`shrink-0 rounded-full border px-4 py-1.5 text-xs font-bold transition-all ${
                      activeDay === d.day_index
                        ? "bg-ink border-ink text-white shadow-xs"
                        : "bg-white border-line text-ink/70 hover:bg-ink/5"
                    }`}
                  >
                    Day {d.day_index}
                  </button>
                ))}
              </div>
            </div>

            {/* Selected Day Timeline & Stops */}
            {trip.days.map((d: any) => {
              if (d.day_index !== activeDay && trip.days.length > 1) return null;
              return (
                <section key={d.day_index} className="rounded-3xl border border-stone-200 bg-white p-6 shadow-xs space-y-4">
                  <div className="flex items-center justify-between border-b border-stone-100 pb-3">
                    <div>
                      <h3 className="text-lg font-bold text-ink">
                        Day {d.day_index} {d.date ? `· ${d.date}` : ""}
                      </h3>
                      <p className="text-xs text-ink/75 mt-0.5">{d.summary || `Exploring the wonders of ${trip.destination}`}</p>
                    </div>
                    <span className="rounded-full bg-stone-100 px-3 py-1 text-[11px] font-bold text-stone-700">
                      {d.stops.length} {d.stops.length === 1 ? "stop" : "stops"}
                    </span>
                  </div>

                  {d.stops.length === 0 ? (
                    <div className="py-10 text-center rounded-2xl border border-dashed border-stone-200 bg-stone-50/40">
                      <Compass className="w-8 h-8 text-stone-400 mx-auto mb-2" />
                      <p className="text-sm font-bold text-stone-800">No stops scheduled for Day {d.day_index}</p>
                      <p className="text-xs text-stone-500 mt-1 max-w-sm mx-auto">
                        Choose from the famous locations below to add must-see spots directly to this day!
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {d.stops.map((stop: any, i: number) => {
                        const place = stop.place;
                        const isDragging = draggedIndex === i;
                        const isDragOver = dragOverIndex === i;
                        return (
                          <article
                            key={stop.id || i}
                            draggable={true}
                            onDragStart={() => handleDragStart(i)}
                            onDragOver={(e) => handleDragOver(e, i)}
                            onDrop={() => handleDropStop(i)}
                            onDragEnd={() => {
                              setDraggedIndex(null);
                              setDragOverIndex(null);
                            }}
                            className={`flex items-start gap-3 rounded-2xl border p-4 transition-all bg-white hover:border-stone-400 hover:shadow-xs group ${
                              isDragOver
                                ? "border-amber-500 bg-amber-50/30 scale-[1.01] shadow-sm"
                                : isDragging
                                ? "opacity-50 border-dashed border-stone-300"
                                : i === 0
                                ? "border-l-4 border-l-ink border-stone-200"
                                : "border-stone-200"
                            }`}
                          >
                            <div className="flex items-center gap-1.5 shrink-0">
                              <span title="Drag to reorder stop" className="inline-flex">
                                <GripVertical
                                  size={16}
                                  className="cursor-grab active:cursor-grabbing text-stone-300 hover:text-stone-700 transition-colors"
                                />
                              </span>
                              <div className="rounded-full border border-stone-200 bg-stone-100 size-7 text-ink font-bold text-xs flex items-center justify-center">
                                {i + 1}
                              </div>
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center justify-between gap-2 mb-1">
                                <span className="text-[10px] font-bold uppercase tracking-wider text-muted">
                                  {SLOT_LABEL[stop.time_slot] || stop.time_slot || "Afternoon"}
                                </span>
                                <div className="flex items-center gap-2">
                                  {stop.duration_mins && (
                                    <span className="rounded-full border border-line px-2 py-0.5 text-[10px] font-medium text-muted">
                                      {stop.duration_mins} min
                                    </span>
                                  )}
                                  <button
                                    type="button"
                                    onClick={() => handleRemoveStop(stop.id)}
                                    className="opacity-0 group-hover:opacity-100 text-stone-400 hover:text-red-600 transition-opacity p-0.5"
                                    title="Remove this stop"
                                  >
                                    <Trash2 size={13} />
                                  </button>
                                </div>
                              </div>
                              <h4 className="text-base font-bold text-ink leading-tight">{place?.name || stop.notes || "Stop"}</h4>
                              <p className="text-xs text-stone-500 mt-0.5">
                                {place?.category ? place.category.charAt(0).toUpperCase() + place.category.slice(1) : "Attraction"}
                                {place?.address ? ` · ${place.address}` : ""}
                              </p>
                              <p className="mt-1.5 text-xs leading-relaxed text-stone-700">{stop.notes || place?.description || ""}</p>
                            </div>
                            {place?.photos?.[0] && (
                              <div className="ml-2 shrink-0 w-14 h-14 rounded-xl overflow-hidden border border-stone-200">
                                <img
                                  src={place.photos[0]}
                                  alt={place.name}
                                  className="size-full object-cover"
                                  referrerPolicy="no-referrer"
                                />
                              </div>
                            )}
                          </article>
                        );
                      })}
                    </div>
                  )}
                </section>
              );
            })}

            {/* Recommended Famous Spots Section */}
            <section className="rounded-3xl border border-stone-200 bg-white p-6 shadow-xs space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-stone-100 pb-4">
                <div>
                  <div className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 border border-amber-200/80 px-2.5 py-0.5 text-[10px] font-bold text-amber-800 mb-1.5">
                    <Sparkles size={11} className="text-amber-600" />
                    <span>Recommended in {trip.destination}</span>
                  </div>
                  <h3 className="text-xl font-bold text-stone-900">Famous Spots & Must-See Locations</h3>
                  <p className="text-xs text-stone-500 mt-0.5">
                    Top-rated landmarks and iconic sites. Click to add them directly to Day {activeDay}!
                  </p>
                </div>

                {/* Category Filter Pills */}
                <div className="flex gap-1.5 overflow-x-auto no-scrollbar py-1">
                  {[
                    { id: "all", label: "All" },
                    { id: "attraction", label: "Attractions" },
                    { id: "nature", label: "Nature & Views" },
                    { id: "culture", label: "Culture" },
                    { id: "dining", label: "Dining" },
                  ].map((cat) => (
                    <button
                      key={cat.id}
                      type="button"
                      onClick={() => setRecCategory(cat.id)}
                      className={`px-3 py-1 rounded-full text-xs font-bold transition-all whitespace-nowrap ${
                        recCategory === cat.id
                          ? "bg-stone-900 text-white shadow-2xs"
                          : "bg-stone-100 text-stone-600 hover:bg-stone-200"
                      }`}
                    >
                      {cat.label}
                    </button>
                  ))}
                </div>

                {/* Search Box */}
                <div className="flex items-center gap-2 min-w-[200px]">
                  <input
                    type="text"
                    value={recSearchQuery}
                    onChange={(e) => setRecSearchQuery(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleRecSearch()}
                    placeholder="Search places…"
                    disabled={recSearchLoading}
                    className="flex-1 px-3 py-1.5 rounded-xl border border-stone-200 bg-stone-50 text-xs text-stone-900 focus:border-ink focus:ring-1 focus:ring-ink transition-all placeholder:text-stone-400"
                  />
                  <button
                    type="button"
                    onClick={handleRecSearch}
                    disabled={recSearchLoading || !recSearchQuery.trim()}
                    className="rounded-xl border border-stone-200 bg-white px-3 py-1.5 text-xs font-bold text-stone-800 hover:bg-stone-50 disabled:opacity-50 disabled:pointer-events-none shadow-2xs transition-colors flex items-center gap-1.5"
                  >
                    {recSearchLoading ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : (
                      <>
                        <span>Search</span>
                        <span className="sr-only">Google Maps</span>
                      </>
                    )}
                  </button>
                </div>

                {recSearchError && (
                  <p className="text-[10px] text-red-600 mt-1">{recSearchError}</p>
                )}
              </div>

              {loadingRecs ? (
                <div className="py-12 text-center text-xs text-stone-400 flex flex-col items-center justify-center">
                  <Loader2 className="w-6 h-6 animate-spin text-amber-600 mb-2" />
                  <span>Curating famous locations in {trip.destination}...</span>
                </div>
              ) : filteredSpots.length === 0 ? (
                <div className="py-8 text-center text-xs text-stone-500">
                  No spots found matching category &quot;{recCategory}&quot;. Try selecting &quot;All&quot;.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {filteredSpots.map((spot) => {
                    const isAdding = addingStopId === spot.id;
                    const isSuccess = addedSuccessId === spot.id;
                    const photo = spot.photos?.[0] || getDestinationPhoto(trip.destination);

                    return (
                      <div
                        key={spot.id}
                        className="group flex flex-col justify-between rounded-2xl border border-stone-200 bg-stone-50/50 hover:bg-white hover:border-stone-400 hover:shadow-md transition-all overflow-hidden"
                      >
                        <div>
                          {/* Spot Photo */}
                          <div className="relative h-40 w-full overflow-hidden bg-stone-200">
                            <img
                              src={photo}
                              alt={spot.name}
                              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                              referrerPolicy="no-referrer"
                            />
                            <div className="absolute top-2.5 left-2.5 flex items-center gap-1.5 flex-wrap">
                              <span className="rounded-full bg-stone-900/80 backdrop-blur px-2 py-0.5 text-[10px] font-bold text-white uppercase tracking-wider">
                                {spot.category || "Attraction"}
                              </span>
                              {spot.price_level && spot.price_level !== "Free" && (
                                <span className="rounded-full bg-white/90 backdrop-blur px-2 py-0.5 text-[10px] font-bold text-stone-800">
                                  {spot.price_level}
                                </span>
                              )}
                            </div>
                            {spot.rating && (
                              <div className="absolute top-2.5 right-2.5 flex items-center gap-1 rounded-full bg-white/95 backdrop-blur px-2 py-0.5 text-[10px] font-black text-stone-900 shadow-2xs">
                                <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                                <span>{typeof spot.rating === "number" ? spot.rating.toFixed(1) : spot.rating}</span>
                              </div>
                            )}
                          </div>

                          {/* Spot Details */}
                          <div className="p-4 space-y-1.5">
                            <h4 className="text-base font-bold text-stone-900 line-clamp-1 group-hover:text-amber-700 transition-colors">
                              {spot.name}
                            </h4>
                            <p className="text-[11px] text-stone-500 flex items-center gap-1 line-clamp-1">
                              <MapPin size={11} className="shrink-0 text-stone-400" />
                              <span>{spot.address || spot.city || trip.destination}</span>
                            </p>
                            <p className="text-xs text-stone-600 line-clamp-2 leading-relaxed pt-1">
                              {spot.description}
                            </p>
                          </div>
                        </div>

                        {/* Actions */}
                        <div className="p-4 pt-0 border-t border-stone-100 flex items-center justify-between gap-2 mt-2">
                          <button
                            type="button"
                            onClick={() => setSelectedPlaceForModal(spot)}
                            className="inline-flex items-center gap-1 text-xs font-semibold text-stone-600 hover:text-stone-900 px-2.5 py-1.5 rounded-xl hover:bg-stone-200/60 transition-colors"
                          >
                            <Eye size={13} />
                            <span>Details</span>
                          </button>

                          <button
                            type="button"
                            onClick={() => handleAddStopToTrip(spot)}
                            disabled={isAdding || isSuccess}
                            className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-xl text-xs font-bold transition-all shadow-2xs ${
                              isSuccess
                                ? "bg-emerald-600 text-white"
                                : "bg-stone-900 text-white hover:bg-amber-700 active:scale-98"
                            }`}
                          >
                            {isAdding ? (
                              <>
                                <Loader2 size={12} className="animate-spin" />
                                <span>Adding...</span>
                              </>
                            ) : isSuccess ? (
                              <>
                                <Check size={12} />
                                <span>Added to Day {activeDay}</span>
                              </>
                            ) : (
                              <>
                                <Plus size={12} />
                                <span>Add to Day {activeDay}</span>
                              </>
                            )}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
              {recSearchResults.length > 0 && (
                <div className="mt-6">
                  <h4 className="text-xs font-bold text-stone-800 uppercase tracking-wider mb-3">
                    Search results for {recSearchQuery}
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {recSearchResults.map((spot) => {
                      const isAdding = addingStopId === spot.id;
                      const isSuccess = addedSuccessId === spot.id;
                      const photo = spot.photos?.[0] || getDestinationPhoto(trip.destination);
                      return (
                        <div
                          key={spot.id}
                          className="group flex flex-col justify-between rounded-2xl border border-stone-200 bg-stone-50/50 hover:bg-white hover:border-stone-400 hover:shadow-md transition-all overflow-hidden"
                        >
                          <div>
                            <div className="relative h-40 w-full overflow-hidden bg-stone-200">
                              <img
                                src={photo}
                                alt={spot.name}
                                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                                referrerPolicy="no-referrer"
                              />
                              <div className="absolute top-2.5 left-2.5 flex items-center gap-1.5 flex-wrap">
                                <span className="rounded-full bg-stone-900/80 backdrop-blur px-2 py-0.5 text-[10px] font-bold text-white uppercase tracking-wider">
                                  {spot.category || "Attraction"}
                                </span>
                              </div>
                              {spot.rating && (
                                <div className="absolute top-2.5 right-2.5 flex items-center gap-1 rounded-full bg-white/95 backdrop-blur px-2 py-0.5 text-[10px] font-black text-stone-900 shadow-2xs">
                                  <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                                  <span>{typeof spot.rating === "number" ? spot.rating.toFixed(1) : spot.rating}</span>
                                </div>
                              )}
                            </div>
                            <div className="p-4 space-y-1.5">
                              <h4 className="text-base font-bold text-stone-900 line-clamp-1 group-hover:text-amber-700 transition-colors">
                                {spot.name}
                              </h4>
                              <p className="text-[11px] text-stone-500 flex items-center gap-1 line-clamp-1">
                                <MapPin size={11} className="shrink-0 text-stone-400" />
                                <span>{spot.address || spot.city || trip.destination}</span>
                              </p>
                              <p className="text-xs text-stone-600 line-clamp-2 leading-relaxed pt-1">
                                {spot.description}
                              </p>
                            </div>
                          </div>
                          <div className="p-4 pt-0 border-t border-stone-100 flex items-center justify-between gap-2 mt-2">
                            <button
                              type="button"
                              onClick={() => setSelectedPlaceForModal(spot)}
                              className="inline-flex items-center gap-1 text-xs font-semibold text-stone-600 hover:text-stone-900 px-2.5 py-1.5 rounded-xl hover:bg-stone-200/60 transition-colors"
                            >
                              <Eye size={13} />
                              <span>Details</span>
                            </button>
                            <button
                              type="button"
                              onClick={() => handleAddStopToTrip(spot)}
                              disabled={isAdding || isSuccess}
                              className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-xl text-xs font-bold transition-all shadow-2xs ${
                                isSuccess
                                  ? "bg-emerald-600 text-white"
                                  : "bg-stone-900 text-white hover:bg-amber-700 active:scale-98"
                              }`}
                            >
                              {isAdding ? (
                                <>
                                  <Loader2 size={12} className="animate-spin" />
                                  <span>Adding...</span>
                                </>
                              ) : isSuccess ? (
                                <>
                                  <Check size={12} />
                                  <span>Added to Day {activeDay}</span>
                                </>
                              ) : (
                                <>
                                  <Plus size={12} />
                                  <span>Add to Day {activeDay}</span>
                                </>
                              )}
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </section>
          </div>

          {/* Right Column: Sleek, Compact OpenStreetMap Sidebar (32% width, placed to the right) */}
          <div className="lg:col-span-4 xl:col-span-4 lg:sticky lg:top-8 hidden lg:block space-y-3">
            <div className="flex items-center justify-between bg-white rounded-2xl border border-stone-200 p-2.5 px-3.5 shadow-2xs">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 flex items-center justify-center font-bold">
                  <MapPin size={14} />
                </div>
                <div>
                  <p className="text-xs font-bold text-stone-900 leading-tight">Itinerary Map</p>
                  <p className="text-[10px] text-stone-500">
                    {trip.destination} · Day {activeDay} ({dayPins.length} stops)
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setMapOpen(!mapOpen)}
                className="text-xs font-bold text-stone-700 hover:text-stone-900 px-3 py-1 rounded-xl bg-stone-100 hover:bg-stone-200 transition-colors"
              >
                {mapOpen ? "Hide" : "Show"}
              </button>
            </div>

            {mapOpen && (
              <div className="h-[460px] rounded-3xl overflow-hidden border border-stone-200 shadow-sm relative">
                <InteractiveMap
                  pins={allPins}
                  activePinId={null}
                  onPinClick={(id) => {
                    const found = recommendedPlaces.find((p) => p.id === id);
                    if (found) setSelectedPlaceForModal(found);
                  }}
                />
              </div>
            )}

            <div className="rounded-2xl border border-stone-200 bg-white p-3 text-[11px] text-stone-500 space-y-1.5 shadow-2xs">
              <p className="font-bold text-stone-800">Map Legend</p>
              <div className="flex items-center gap-4 text-[10px]">
                <span className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-stone-900 inline-block"></span> Day stops
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-600 inline-block"></span> Booked stay
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-sky-600 inline-block"></span> Attractions
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Mobile map toggle */}
        <div className="lg:hidden mt-8">
          <button
            onClick={() => setMapOpen(!mapOpen)}
            className="w-full flex items-center justify-center gap-1.5 rounded-full border border-line bg-white px-4 py-3 text-sm font-bold text-ink shadow-sm hover:bg-ink/5 transition-colors"
          >
            {mapOpen ? <ChevronLeft size={14} /> : <MapPin size={14} />}
            {mapOpen ? "Hide Map" : `Show OpenStreetMap for Day ${activeDay}`}
          </button>
          {mapOpen && (
            <div className="mt-4 h-[380px] rounded-3xl overflow-hidden border border-line shadow-card">
              <InteractiveMap
                pins={allPins}
                activePinId={null}
                onPinClick={(id) => {
                  const found = recommendedPlaces.find((p) => p.id === id);
                  if (found) setSelectedPlaceForModal(found);
                }}
              />
            </div>
          )}
        </div>

        {/* Bottom Navigation */}
        <div className="mt-12 flex items-center justify-between gap-4 border-t border-stone-200 pt-6">
          <Link
            href={`/chat?trip_id=${trip.id}&session_id=${trip.session_id || ""}`}
            className="inline-flex items-center gap-2 rounded-full border border-line bg-white px-5 py-2.5 text-xs font-bold text-ink hover:bg-ink/5 transition-colors"
          >
            <ChevronLeft size={16} /> Back to chat
          </Link>
          <div className="flex gap-3 relative">
            <button
              type="button"
              onClick={async () => {
                try {
                  const shareUrl = typeof window !== "undefined" ? window.location.href : `/trip/${trip.id}`;
                  if (typeof navigator !== "undefined" && navigator.clipboard) {
                    await navigator.clipboard.writeText(shareUrl);
                    setShareCopied(true);
                    setTimeout(() => setShareCopied(false), 2500);
                  }
                } catch {
                  // Ignore clipboard errors
                }
              }}
              className="flex items-center gap-2 rounded-full border border-line bg-white px-4 py-2.5 text-xs font-bold text-ink hover:bg-ink/5 transition-colors"
            >
              {shareCopied ? <Check size={15} className="text-emerald-600" /> : <Share2 size={15} />}
              <span>{shareCopied ? "Link Copied!" : "Share"}</span>
            </button>

            <div className="relative">
              <button
                type="button"
                onClick={() => setShowExportMenu((v) => !v)}
                className="flex items-center gap-2 rounded-full border border-line bg-white px-4 py-2.5 text-xs font-bold text-ink hover:bg-ink/5 transition-colors"
                title="Export itinerary"
              >
                <MoreHorizontal size={15} />
              </button>
              {showExportMenu && (
                <div className="absolute right-0 bottom-full mb-2 w-48 rounded-2xl border border-stone-200 bg-white p-1.5 shadow-xl z-30">
                  <a
                    href={`/api/trips/${trip.id}/export?format=txt`}
                    download={`${(trip.title || "itinerary").replace(/[^a-z0-9]+/gi, "-")}.txt`}
                    onClick={() => setShowExportMenu(false)}
                    className="block rounded-xl px-3 py-2 text-xs font-semibold text-stone-800 hover:bg-stone-100"
                  >
                    Export as Text (.txt)
                  </a>
                  <a
                    href={`/api/trips/${trip.id}/export?format=json`}
                    download={`${(trip.title || "itinerary").replace(/[^a-z0-9]+/gi, "-")}.json`}
                    onClick={() => setShowExportMenu(false)}
                    className="block rounded-xl px-3 py-2 text-xs font-semibold text-stone-800 hover:bg-stone-100"
                  >
                    Export as JSON (.json)
                  </a>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Place Detail Exploration Modal */}
      {selectedPlaceForModal && (
        <PlaceDetailModal
          card={selectedPlaceForModal}
          onClose={() => setSelectedPlaceForModal(null)}
        />
      )}

      {/* Floating Continue Chat Button */}
      <Link
        href={`/chat?trip_id=${trip.id}&session_id=${trip.session_id || ""}`}
        className="fixed bottom-6 right-6 z-40 flex items-center gap-2.5 rounded-full bg-stone-900 text-white px-5 py-3 text-sm font-bold shadow-2xl hover:bg-stone-800 transition-all hover:scale-105 active:scale-95 border border-white/20"
      >
        <MessageSquare size={16} className="text-amber-400" />
        <span>Chat about this Trip</span>
      </Link>
    </div>
  );
}
