"use client";

import { Plane, Sparkles, ExternalLink, Plus } from "lucide-react";

interface FlightLegInfo {
  id?: string;
  airline?: string;
  airline_code?: string;
  flight_number?: string;
  origin?: string;
  destination?: string;
  departure_time?: string;
  arrival_time?: string;
  duration?: string;
  duration_minutes?: number;
  stops?: number;
  price_inr?: number;
  price_usd?: number;
  cabin?: string;
  booking_url?: string;
  source?: string;
  is_top_pick?: boolean;
  passengers?: number;
  price_per_person_usd?: number;
  metadata?: any;
}

interface MultiLegFlightCardProps {
  flights: FlightLegInfo[];
  formatPrice: (flight: any, currency: string) => string;
  formatFlightTime: (iso: string) => string;
  formatDuration: (minutes: number) => string;
  passengersCount?: number;
  isRoundTrip?: boolean;
  isTopPick?: boolean;
  onAddToTrip?: (f: any) => void;
}

export function MultiLegFlightCard({
  flights,
  formatPrice,
  formatFlightTime,
  formatDuration,
  passengersCount = 1,
  isTopPick = false,
  onAddToTrip,
}: MultiLegFlightCardProps) {
  if (!flights || flights.length === 0) {
    return null;
  }

  // Keep legs in journey order
  const sortedFlights = [...flights].sort((a, b) => {
    const aLeg = a.metadata?.leg_index ?? 0;
    const bLeg = b.metadata?.leg_index ?? 0;
    return aLeg - bLeg;
  });

  const firstFlight = sortedFlights[0];
  const lastFlight = sortedFlights[sortedFlights.length - 1];

  const totalInr = sortedFlights.reduce((sum, f) => {
    if (f.price_inr && f.price_inr > 0) return sum + f.price_inr;
    if (f.price_usd && f.price_usd > 0) return sum + f.price_usd * 85;
    return sum;
  }, 0);

  const totalUsd = sortedFlights.reduce((sum, f) => {
    if (f.price_usd && f.price_usd > 0) return sum + f.price_usd;
    if (f.price_inr && f.price_inr > 0) return sum + f.price_inr / 85;
    return sum;
  }, 0);

  const totalStops = sortedFlights.reduce((sum, f) => sum + (f.stops || 0), 0);
  const totalDuration = sortedFlights.reduce(
    (sum, f) => sum + (f.duration_minutes || 0),
    0
  );

  const safeTime = (value?: string) => {
    if (!value) return "--:--";
    try {
      return formatFlightTime(value);
    } catch {
      return value;
    }
  };

  const safeDuration = (value?: number) => {
    if (!value) return "—";
    try {
      return formatDuration(value);
    } catch {
      return `${Math.floor(value / 60)}h ${value % 60}m`;
    }
  };

  const totalPriceLabel = formatPrice(
    { ...firstFlight, price_inr: totalInr, price_usd: totalUsd },
    "INR"
  );

  const bookUrl =
    firstFlight.booking_url ||
    `https://www.google.com/travel/flights?q=${sortedFlights
      .map((f) => `flights+from+${f.origin}+to+${f.destination}`)
      .join("+")}&hl=en&gl=in&curr=INR`;

  return (
    <article
      className={`group rounded-3xl border bg-white p-5 transition-all shadow-xs hover:shadow-md ${
        isTopPick
          ? "border-amber-200/80 ring-1 ring-amber-100/60 hover:border-amber-300"
          : "border-stone-200/90 hover:border-stone-300"
      }`}
    >
      {/* Header */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-stone-100 border border-stone-200 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-stone-700">
          <Plane className="w-3 h-3" />
          Multi-city · {sortedFlights.length} leg
          {sortedFlights.length === 1 ? "" : "s"}
        </span>
        <span className="rounded-full bg-stone-50 border border-stone-200 px-2.5 py-1 text-[10px] font-semibold text-stone-600">
          {totalStops === 0
            ? "All non-stop"
            : `${totalStops} total stop${totalStops > 1 ? "s" : ""}`}
        </span>
        <span className="rounded-full bg-stone-50 border border-stone-200 px-2.5 py-1 text-[10px] font-semibold text-stone-600">
          {safeDuration(totalDuration)} in the air
        </span>
        {isTopPick && (
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 border border-amber-200/60 px-2 py-1 text-[10px] font-bold text-amber-800 ml-auto">
            <Sparkles className="w-2.5 h-2.5 text-amber-600" />
            Top pick
          </span>
        )}
      </div>

      {/* Every leg of the journey in one card */}
      <div className="divide-y divide-stone-100">
        {sortedFlights.map((flight, idx) => {
          const legNum = (flight.metadata?.leg_index ?? idx) + 1;
          const pax = flight.passengers || passengersCount || 1;

          return (
            <div
              key={flight.id || `leg-${idx}`}
              className="flex flex-col md:flex-row md:items-center justify-between gap-4 py-4 first:pt-0 last:pb-0"
            >
              {/* Leg identity */}
              <div className="flex items-center gap-3.5 min-w-[190px]">
                <div className="w-11 h-11 rounded-2xl bg-stone-100 border border-stone-200 flex items-center justify-center text-xs font-black text-stone-800 shrink-0">
                  {(flight.airline_code || flight.airline || "FL")
                    .slice(0, 2)
                    .toUpperCase()}
                </div>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h4 className="text-sm font-bold text-stone-900 leading-tight">
                      {flight.airline || "Flight"}
                    </h4>
                    <span className="inline-flex items-center rounded-full bg-sky-50 border border-sky-200 px-2 py-0.5 text-[9px] font-bold text-sky-800 uppercase tracking-wider">
                      Leg {legNum}
                    </span>
                  </div>
                  <p className="text-[11px] text-stone-500 mt-0.5 flex items-center gap-1.5 flex-wrap">
                    <span>{flight.flight_number || "Flight"}</span>
                    <span>·</span>
                    <span className="text-stone-700 font-medium">
                      {flight.cabin || "Economy"}
                    </span>
                  </p>
                </div>
              </div>

              {/* Route timeline */}
              <div className="flex-1 grid grid-cols-[auto_1fr_auto] items-center gap-3 px-2 max-w-sm">
                <div className="text-left">
                  <p className="text-base font-black text-stone-900 tracking-tight">
                    {safeTime(flight.departure_time)}
                  </p>
                  <p className="text-xs font-semibold text-stone-500">
                    {flight.origin || "—"}
                  </p>
                </div>

                <div className="flex flex-col items-center">
                  <span className="text-[10px] text-stone-400 font-medium mb-1">
                    {safeDuration(flight.duration_minutes)}
                  </span>
                  <div className="w-full flex items-center gap-1">
                    <div className="w-2 h-2 rounded-full border-2 border-stone-400 bg-white" />
                    <div className="flex-1 h-0.5 bg-stone-200 relative">
                      {(flight.stops || 0) > 0 && (
                        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-amber-500" />
                      )}
                    </div>
                    <div className="w-2 h-2 rounded-full bg-stone-900" />
                  </div>
                  <span
                    className={`text-[10px] font-semibold mt-1 ${
                      (flight.stops || 0) === 0
                        ? "text-emerald-600"
                        : "text-amber-600"
                    }`}
                  >
                    {(flight.stops || 0) === 0
                      ? "Nonstop"
                      : `${flight.stops} stop${(flight.stops || 0) > 1 ? "s" : ""}`}
                  </span>
                </div>

                <div className="text-right">
                  <p className="text-base font-black text-stone-900 tracking-tight">
                    {safeTime(flight.arrival_time)}
                  </p>
                  <p className="text-xs font-semibold text-stone-500">
                    {flight.destination || "—"}
                  </p>
                </div>
              </div>

              {/* Leg price */}
              <div className="text-right min-w-[92px]">
                <p className="text-sm font-bold text-stone-900">
                  {formatPrice(flight, "INR")}
                </p>
                <p className="text-[10px] text-stone-400">
                  {pax > 1 ? `for ${pax} travelers` : "per person"}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer / totals */}
      <div className="mt-4 pt-4 border-t border-stone-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <p className="text-[10px] uppercase tracking-wider text-stone-400 font-semibold">
            {passengersCount > 1
              ? `Total · ${passengersCount} travelers`
              : "Total trip price"}
          </p>
          <p className="text-xl font-black text-stone-900 leading-tight">
            {totalPriceLabel}
          </p>
          <p className="text-[10px] text-stone-400">
            {firstFlight.origin} → {lastFlight.destination} ·{" "}
            {sortedFlights.length} leg{sortedFlights.length === 1 ? "" : "s"}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {onAddToTrip && (
            <button
              type="button"
              onClick={() => onAddToTrip(firstFlight)}
              className="inline-flex items-center gap-1 rounded-full border border-stone-200 bg-white px-3 py-1.5 text-xs font-semibold text-stone-700 hover:border-stone-300 hover:bg-stone-50 transition-colors"
            >
              <Plus size={11} /> Add to trip
            </button>
          )}
          <a
            href={bookUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 rounded-full bg-stone-900 px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-stone-800 transition-colors"
          >
            Book multi-city <ExternalLink size={11} />
          </a>
        </div>
      </div>
    </article>
  );
}
