"use client";

import { useState } from "react";
import { Plane, Clock, ExternalLink, Plus } from "lucide-react";
import { formatFlightPriceDisplay } from "@/lib/currencies";
import { AddToTripModal } from "@/components/common/AddToTripModal";

interface FlightLegInfo {
  id?: string;
  airline?: string;
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
  price_per_person_usd?: number;
  metadata?: any;
}

interface FlightCardProps {
  card: FlightLegInfo & {
    id?: string;
    airline?: string;
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
    booking_url?: string;
    cabin?: string;
    passengers?: number;
    price_per_person_usd?: number;
    return_flight?: {
      airline?: string;
      flight_number?: string;
      origin?: string;
      destination?: string;
      departure_time?: string;
      arrival_time?: string;
      duration_minutes?: number;
      stops?: number;
      date?: string;
    };
    metadata?: any;
  };
}

export function FlightCard({ card }: FlightCardProps) {
  const [addToTripOpen, setAddToTripOpen] = useState(false);
  const airline = card.airline || "Airline";
  const flightNum = card.flight_number || "";
  const origin = card.origin || "ORG";
  const destination = card.destination || "DST";
  const dep = card.departure_time || "09:00";
  const arr = card.arrival_time || "12:30";
  const stops = card.stops === 0 ? "Non-stop" : `${card.stops ?? 1} stop`;
  const duration = card.duration || (card.duration_minutes ? `${Math.floor(card.duration_minutes / 60)}h ${card.duration_minutes % 60}m` : "3h 30m");
  const priceDisplay = formatFlightPriceDisplay(card, "INR");
  const googleFlightsUrl = card.booking_url || `https://www.google.com/travel/flights?q=Flights%20to%20${destination}%20from%20${origin}`;
  const ret = card.return_flight;
  const pax = card.passengers || 1;

  // Detect multi-city trip from metadata
  const metadata = card.metadata || {};
  const legIndex = metadata.leg_index;
  const legRoute = metadata.leg_route;
  const isMultiCity = legRoute !== undefined;
  const totalPriceUsd = card.price_per_person_usd !== undefined ? card.price_per_person_usd * pax : card.price_usd || 0;
  const totalDurationMinutes = card.duration_minutes || 0;

  // Helper to format duration
  const formatDuration = (minutes?: number) => {
    if (!minutes) return "--";
    return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
  };

  return (
    <article className="shrink-0 w-[290px] rounded-3xl border border-line/80 bg-white shadow-card p-4 flex flex-col justify-between hover:border-olive/50 hover:shadow-lg transition-all group">
      <div>
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-2">
            <div className="size-8 rounded-full bg-olive/10 text-olive flex items-center justify-center font-bold text-xs">
              <Plane size={15} />
            </div>
            <div>
              <h4 className="font-bold text-xs text-ink">{airline}</h4>
              <p className="text-[10px] text-muted">{flightNum || card.cabin || "Economy"}</p>
            </div>
          </div>
          <span className="rounded-full bg-cream px-2 py-0.5 text-[10px] font-semibold text-ink/80">
            {stops}
          </span>
        </div>

        {/* Multi-city route indicator */}
        {isMultiCity && (
          <div className="flex items-center gap-1 mb-2">
            <span className="text-[9px] font-bold text-olive">Multi-city</span>
            <span className="text-[9px] text-muted flex items-center gap-1 text-truncate">
              {legRoute}
            </span>
          </div>
        )}

        <div className="flex items-center justify-between my-2 px-1">
          <div>
            <div className="text-base font-bold text-ink">{dep}</div>
            <div className="text-[11px] font-semibold text-muted">{origin}</div>
          </div>

          <div className="flex-1 flex flex-col items-center px-3">
            <span className="text-[10px] text-muted flex items-center gap-1 mb-1">
              <Clock size={10} /> {duration}
            </span>
            <div className="w-full flex items-center gap-1 text-muted/40">
              <div className="h-px flex-1 bg-line" />
              <Plane size={12} className="rotate-90 text-olive" />
              <div className="h-px flex-1 bg-line" />
            </div>
          </div>

          <div className="text-right">
            <div className="text-base font-bold text-ink">{arr}</div>
            <div className="text-[11px] font-semibold text-muted">{destination}</div>
          </div>
        </div>

        {ret && (
          <div className="mt-2.5 pt-2 border-t border-line/50 flex items-center justify-between text-[10px] text-muted">
            <span className="font-medium text-ink flex items-center gap-1 truncate max-w-[170px]">
              <span className="text-olive font-bold">⇄</span> Return: {ret.airline}
            </span>
            <span className="shrink-0 font-medium">
              {ret.duration_minutes
                ? `${Math.floor(ret.duration_minutes / 60)}h ${ret.duration_minutes % 60}m`
                : ""} • {ret.stops === 0 ? "Non-stop" : `${ret.stops ?? 1} stop`}
            </span>
          </div>
        )}
      </div>

      <div className="pt-3 border-t border-line/50 flex items-center justify-between gap-2 mt-2.5">
        <div>
          <span className="text-[10px] text-muted block leading-none">
            {pax > 1 ? `Total (${pax} pax)` : "Starting from"}
          </span>
          <span className="text-sm font-bold text-ink">{priceDisplay}</span>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setAddToTripOpen(true)}
            className="inline-flex items-center gap-1 rounded-full border border-line bg-white px-2.5 py-1.5 text-xs font-semibold text-ink hover:bg-cream transition-colors"
            title="Add flight to trip"
          >
            <Plus size={11} className="text-olive" /> Trip
          </button>
          <a
            href={googleFlightsUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 rounded-full bg-ink px-3 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-olive transition-colors"
          >
            Book <ExternalLink size={11} />
          </a>
        </div>
      </div>

      <AddToTripModal
        isOpen={addToTripOpen}
        onClose={() => setAddToTripOpen(false)}
        itemType="flight"
        itemData={card}
      />
    </article>
  );
}