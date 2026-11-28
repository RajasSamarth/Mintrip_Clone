"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import {
  Compass,
  MapPin,
  Calendar,
  Plus,
  Sparkles,
  ArrowRight,
  MessageSquare,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import { getDestinationPhoto } from "@/lib/destinations";
import Footer from "@/components/navigation/Footer";

export default function TripsPage() {
  const router = useRouter();
  const [trips, setTrips] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Create Trip modal state
  const [createOpen, setCreateOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDestination, setNewDestination] = useState("");
  const [newStartDate, setNewStartDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 14);
    return d.toISOString().split("T")[0];
  });
  const [newDurationDays, setNewDurationDays] = useState(3);
  const [newTravelerType, setNewTravelerType] = useState("Explorer");
  const [newBudget, setNewBudget] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  async function loadTrips() {
    setLoading(true);
    try {
      const res = await api("/trips?limit=100");
      const json = await res.json();
      setTrips(json.trips || []);
    } catch (e) {
      console.warn("Failed to load trips:", e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadTrips();
  }, []);

  async function handleCreateTrip(e: React.FormEvent) {
    e.preventDefault();
    if (!newTitle.trim() || !newDestination.trim()) {
      setCreateError("Please enter both a trip title and destination.");
      return;
    }
    setCreating(true);
    setCreateError("");
    try {
      const days = Array.from({ length: Math.max(1, Math.min(14, newDurationDays)) }, (_, i) => ({
        day_index: i + 1,
        title: `Day ${i + 1}`,
        summary: `Exploring ${newDestination.trim()}`,
        stops: [],
      }));
      const res = await api("/trips", {
        method: "POST",
        body: JSON.stringify({
          title: newTitle.trim(),
          destination: newDestination.trim(),
          start_date: newStartDate,
          traveler_type: newTravelerType,
          budget: newBudget ? Number(newBudget) : 0,
          cover_photo: getDestinationPhoto(newDestination.trim()),
          days,
        }),
      });
      const created = await res.json();
      setCreateOpen(false);
      setNewTitle("");
      setNewDestination("");
      setNewBudget("");
      if (created?.id) {
        router.push(`/trip/${created.id}`);
      } else {
        await loadTrips();
      }
    } catch (err: any) {
      setCreateError(err?.message || "Could not create trip. Please try again.");
    } finally {
      setCreating(false);
    }
  }

  async function handleDeleteTrip(tripId: string) {
    setDeletingId(tripId);
    try {
      await api(`/trips/${tripId}`, { method: "DELETE" });
      setTrips((prev) => prev.filter((t) => t.id !== tripId));
      setConfirmDeleteId(null);
    } catch (e) {
      console.warn("Failed to delete trip:", e);
    } finally {
      setDeletingId(null);
    }
  }

  const destinations = useMemo(
    () => Array.from(new Set(trips.map((t) => t.destination).filter(Boolean))),
    [trips]
  );

  const filtered = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return trips.filter((t) => {
      const matchDest =
        filter === "all" || (t.destination || "").toLowerCase() === filter.toLowerCase();
      const matchSearch =
        !q ||
        (t.title || "").toLowerCase().includes(q) ||
        (t.destination || "").toLowerCase().includes(q) ||
        (t.summary || "").toLowerCase().includes(q);
      return matchDest && matchSearch;
    });
  }, [trips, filter, searchQuery]);

  return (
    <div className="min-h-screen bg-paper flex flex-col justify-between">
      <div>
        <header className="border-b border-line bg-white/70 backdrop-blur-md sticky top-0 z-20">
          <div className="mx-auto max-w-[1440px] px-5 py-5 sm:px-8">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <span className="text-xs font-semibold uppercase tracking-widest text-muted">Journeys</span>
                <h1 className="text-2xl font-serif-italic text-ink sm:text-3xl">Curated & Saved Trips</h1>
              </div>
              <div className="flex flex-wrap items-center gap-2.5">
                <div className="relative">
                  <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Filter trips..."
                    className="rounded-full border border-line bg-white pl-8 pr-3.5 py-2 text-xs font-medium text-ink placeholder:text-muted focus:border-ink focus:outline-none w-44 sm:w-56"
                  />
                </div>
                <button
                  type="button"
                  onClick={() => setCreateOpen(true)}
                  className="inline-flex items-center gap-1.5 rounded-full border border-ink bg-white px-4 py-2 text-sm font-medium text-ink hover:bg-ink/5 transition-colors shadow-2xs"
                >
                  <Plus size={16} /> New Trip
                </button>
                <Link
                  href="/chat"
                  className="inline-flex items-center gap-2 rounded-full bg-ink px-4 py-2 text-sm font-medium text-white hover:bg-ink-soft transition-colors shadow-sm"
                >
                  <Sparkles size={15} className="text-lime" /> Plan with AI
                </Link>
              </div>
            </div>

            {/* Filter pills */}
            {destinations.length > 0 && (
              <div className="mt-4 flex items-center gap-2 overflow-x-auto no-scrollbar pb-1">
                <button
                  onClick={() => setFilter("all")}
                  className={`rounded-full px-4 py-1.5 text-xs font-medium transition-colors shrink-0 ${
                    filter === "all"
                      ? "bg-ink text-white"
                      : "bg-white border border-line text-ink/70 hover:bg-ink/5"
                  }`}
                >
                  All Trips ({trips.length})
                </button>
                {destinations.map((d) => (
                  <button
                    key={d}
                    onClick={() => setFilter(d)}
                    className={`rounded-full px-4 py-1.5 text-xs font-medium capitalize transition-colors shrink-0 ${
                      filter.toLowerCase() === d.toLowerCase()
                        ? "bg-ink text-white"
                        : "bg-white border border-line text-ink/70 hover:bg-ink/5"
                    }`}
                  >
                    {d}
                  </button>
                ))}
              </div>
            )}
          </div>
        </header>

        <main className="mx-auto max-w-[1440px] px-5 py-8 sm:px-8">
          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[1, 2, 3, 4, 5, 6].map((n) => (
                <div key={n} className="rounded-3xl border border-line bg-white p-4 overflow-hidden">
                  <div className="shimmer h-48 w-full rounded-2xl mb-4" />
                  <div className="shimmer h-6 w-3/4 rounded-full mb-2" />
                  <div className="shimmer h-4 w-1/2 rounded-full" />
                </div>
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <Compass className="size-16 text-muted mb-4 stroke-[1.2]" />
              <h2 className="text-2xl font-serif-italic text-ink mb-2">
                {trips.length === 0 ? "No journeys yet" : "No matching trips"}
              </h2>
              <p className="text-sm text-muted max-w-sm mb-6">
                {trips.length === 0
                  ? "Tell our travel concierge what you love or create a custom itinerary with hotels, flights, and maps."
                  : "Try clearing your search filter or create a new trip."}
              </p>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setCreateOpen(true)}
                  className="inline-flex items-center gap-2 rounded-full border border-line bg-white px-5 py-3 text-sm font-medium text-ink hover:bg-ink/5 transition-colors"
                >
                  <Plus size={16} /> Create Trip
                </button>
                <Link
                  href="/chat"
                  className="inline-flex items-center gap-2 rounded-full bg-ink px-6 py-3 text-sm font-medium text-white hover:bg-ink-soft transition-colors"
                >
                  <Sparkles size={16} className="text-lime" /> Start Planning
                </Link>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filtered.map((trip) => (
                <div
                  key={trip.id}
                  className="group rounded-3xl border border-line bg-white overflow-hidden hover:shadow-card hover:border-ink/20 transition-all flex flex-col relative"
                >
                  <Link href={`/trip/${trip.id}`} className="block relative h-56 w-full overflow-hidden bg-cream">
                    {trip.cover_photo ? (
                      <Image
                        src={trip.cover_photo}
                        alt={trip.title}
                        fill
                        className="object-cover group-hover:scale-105 transition-transform duration-500"
                        sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
                      />
                    ) : (
                      <div className="size-full flex items-center justify-center text-muted">
                        <MapPin size={32} />
                      </div>
                    )}
                    <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
                    <div className="absolute top-4 left-4 flex gap-1.5">
                      <span className="rounded-full bg-white/90 backdrop-blur px-3 py-1 text-xs font-semibold text-ink capitalize">
                        {trip.destination}
                      </span>
                    </div>
                    <div className="absolute bottom-3 left-4 right-4 flex items-center justify-between text-xs text-white/90 font-medium">
                      <span>{trip.day_count || trip.days?.length || 3} days</span>
                      <span>{trip.stop_count || 0} curated stops</span>
                    </div>
                  </Link>

                  {/* Delete trip control */}
                  <div className="absolute top-4 right-4 z-10">
                    {confirmDeleteId === trip.id ? (
                      <div className="flex items-center gap-1 rounded-full bg-white/95 backdrop-blur px-2 py-1 shadow-md border border-stone-200">
                        <button
                          type="button"
                          onClick={() => handleDeleteTrip(trip.id)}
                          disabled={deletingId === trip.id}
                          className="rounded-full bg-rose-600 px-2.5 py-0.5 text-[10px] font-bold text-white hover:bg-rose-700"
                        >
                          {deletingId === trip.id ? "..." : "Delete"}
                        </button>
                        <button
                          type="button"
                          onClick={() => setConfirmDeleteId(null)}
                          className="rounded-full px-2 py-0.5 text-[10px] font-semibold text-stone-600 hover:bg-stone-100"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.preventDefault();
                          setConfirmDeleteId(trip.id);
                        }}
                        className="size-8 rounded-full bg-black/45 hover:bg-rose-600 text-white backdrop-blur-md flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all"
                        title="Delete trip"
                      >
                        <Trash2 size={13} />
                      </button>
                    )}
                  </div>

                  <div className="p-5 flex-1 flex flex-col justify-between">
                    <div>
                      <Link href={`/trip/${trip.id}`} className="block">
                        <h3 className="text-xl font-semibold text-ink group-hover:text-ink/80 leading-snug line-clamp-1 mb-2">
                          {trip.title}
                        </h3>
                      </Link>
                      <p className="text-sm text-ink/70 line-clamp-2 leading-relaxed mb-4">
                        {trip.summary || "Explore carefully curated sights, boutique stays, and unforgettable culinary destinations."}
                      </p>
                    </div>

                    <div className="pt-3 border-t border-line flex items-center justify-between text-xs font-medium text-ink/80">
                      <span className="flex items-center gap-1.5 text-muted">
                        <Calendar size={13} /> {trip.traveler_type || "Explorer"}
                      </span>
                      <div className="flex items-center gap-2">
                        <Link
                          href={`/chat?trip_id=${trip.id}&session_id=${trip.session_id || ""}`}
                          className="inline-flex items-center gap-1 rounded-full bg-cream border border-line px-2.5 py-1 text-[11px] font-semibold text-ink hover:bg-olive hover:text-white transition-colors"
                          title="Continue conversation with AI Concierge"
                        >
                          <MessageSquare size={11} /> Chat
                        </Link>
                        <Link
                          href={`/trip/${trip.id}`}
                          className="inline-flex items-center gap-1 group-hover:translate-x-0.5 transition-transform font-semibold text-ink"
                        >
                          View <ArrowRight size={13} />
                        </Link>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </main>
      </div>

      {/* Create Trip Modal */}
      {createOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setCreateOpen(false)}
        >
          <div
            className="w-full max-w-md rounded-3xl bg-white border border-line shadow-2xl overflow-hidden text-ink"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-line bg-cream/40">
              <div>
                <h2 className="text-lg font-bold text-ink">Create New Trip</h2>
                <p className="text-xs text-muted">Start building a custom day-by-day itinerary</p>
              </div>
              <button
                type="button"
                onClick={() => setCreateOpen(false)}
                className="size-8 rounded-full border border-line bg-white flex items-center justify-center text-muted hover:text-ink"
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleCreateTrip} className="p-6 space-y-4 text-xs">
              {createError && (
                <div className="rounded-xl bg-rose-50 border border-rose-200 p-3 text-rose-700 font-medium">
                  {createError}
                </div>
              )}

              <div>
                <label className="block font-bold text-ink mb-1">Trip Name</label>
                <input
                  type="text"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="e.g. Autumn Temples in Kyoto"
                  required
                  className="w-full rounded-xl border border-line px-3.5 py-2.5 text-sm font-medium focus:border-ink focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold text-ink mb-1">Destination City</label>
                  <input
                    type="text"
                    value={newDestination}
                    onChange={(e) => setNewDestination(e.target.value)}
                    placeholder="e.g. Kyoto"
                    required
                    className="w-full rounded-xl border border-line px-3.5 py-2.5 text-sm font-medium focus:border-ink focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block font-bold text-ink mb-1">Days</label>
                  <input
                    type="number"
                    min={1}
                    max={14}
                    value={newDurationDays}
                    onChange={(e) => setNewDurationDays(Number(e.target.value))}
                    className="w-full rounded-xl border border-line px-3.5 py-2.5 text-sm font-medium focus:border-ink focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold text-ink mb-1">Start Date</label>
                  <input
                    type="date"
                    value={newStartDate}
                    onChange={(e) => setNewStartDate(e.target.value)}
                    className="w-full rounded-xl border border-line px-3 py-2.5 text-xs font-medium focus:border-ink focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block font-bold text-ink mb-1">Traveler Style</label>
                  <select
                    value={newTravelerType}
                    onChange={(e) => setNewTravelerType(e.target.value)}
                    className="w-full rounded-xl border border-line px-3 py-2.5 text-xs font-medium focus:border-ink focus:outline-none bg-white"
                  >
                    <option value="Explorer">Explorer</option>
                    <option value="Solo Traveler">Solo Traveler</option>
                    <option value="Couple / Romantic">Couple / Romantic</option>
                    <option value="Family with Kids">Family with Kids</option>
                    <option value="Foodie">Foodie</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block font-bold text-ink mb-1">Target Budget (USD, optional)</label>
                <input
                  type="number"
                  min={0}
                  value={newBudget}
                  onChange={(e) => setNewBudget(e.target.value)}
                  placeholder="e.g. 2500"
                  className="w-full rounded-xl border border-line px-3.5 py-2.5 text-sm font-medium focus:border-ink focus:outline-none"
                />
              </div>

              <div className="pt-2 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setCreateOpen(false)}
                  className="rounded-full border border-line px-4 py-2 font-semibold text-ink/70 hover:bg-ink/5"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="rounded-full bg-ink px-5 py-2 font-semibold text-white hover:bg-ink-soft disabled:opacity-50"
                >
                  {creating ? "Creating..." : "Create Trip"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <Footer />
    </div>
  );
}
