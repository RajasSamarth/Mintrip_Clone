"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { Compass, MapPin, Calendar, Clock, Plus, Sparkles, ArrowRight, MessageSquare } from "lucide-react";
import { api } from "@/lib/api";
import Footer from "@/components/navigation/Footer";

export default function TripsPage() {
  const [trips, setTrips] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const res = await api("/trips");
        const json = await res.json();
        setTrips(json.trips || []);
      } catch (e) {
        console.warn("Failed to load trips:", e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const destinations = Array.from(new Set(trips.map((t) => t.destination).filter(Boolean)));
  const filtered = filter === "all" ? trips : trips.filter((t) => t.destination.toLowerCase() === filter.toLowerCase());

  return (
    <div className="min-h-screen bg-paper flex flex-col justify-between">
      <div>
        <header className="border-b border-line bg-white/70 backdrop-blur-md sticky top-0 z-20">
          <div className="mx-auto max-w-[1440px] px-5 py-5 sm:px-8">
            <div className="flex items-center justify-between gap-4">
              <div>
                <span className="text-xs font-semibold uppercase tracking-widest text-muted">Journeys</span>
                <h1 className="text-2xl font-serif-italic text-ink sm:text-3xl">Curated & Saved Trips</h1>
              </div>
              <Link
                href="/chat"
                className="inline-flex items-center gap-2 rounded-full bg-ink px-4 py-2 text-sm font-medium text-white hover:bg-ink-soft transition-colors shadow-sm"
              >
                <Plus size={16} /> Plan a Trip
              </Link>
            </div>

            {/* Filter pills */}
            {destinations.length > 0 && (
              <div className="mt-4 flex items-center gap-2 overflow-x-auto no-scrollbar pb-1">
                <button
                  onClick={() => setFilter("all")}
                  className={`rounded-full px-4 py-1.5 text-xs font-medium transition-colors ${
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
                    className={`rounded-full px-4 py-1.5 text-xs font-medium capitalize transition-colors ${
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
              <h2 className="text-2xl font-serif-italic text-ink mb-2">No journeys yet</h2>
              <p className="text-sm text-muted max-w-sm mb-6">
                Tell our travel concierge what you love and we will craft a personalized day-by-day itinerary with hotels and maps.
              </p>
              <Link
                href="/chat"
                className="inline-flex items-center gap-2 rounded-full bg-ink px-6 py-3 text-sm font-medium text-white hover:bg-ink-soft transition-colors"
              >
                <Sparkles size={16} className="text-lime" /> Start Planning
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filtered.map((trip) => (
                <div
                  key={trip.id}
                  className="group rounded-3xl border border-line bg-white overflow-hidden hover:shadow-card hover:border-ink/20 transition-all flex flex-col"
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
                      <span>{trip.stop_count || 6} curated stops</span>
                    </div>
                  </Link>

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
      <Footer />
    </div>
  );
}
