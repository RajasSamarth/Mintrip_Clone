"use client";

import { useState } from "react";
import { Sparkles, MapPin, Calendar, Users, Compass, ArrowRight } from "lucide-react";

interface TripIntakeCardProps {
  card?: {
    title?: string;
    description?: string;
    destination?: string;
    destinations?: string[];
    default_origin?: string;
    default_adults?: number;
    default_start_date?: string;
    default_end_date?: string;
  };
  onSubmit?: (message: string) => void;
}

const POPULAR_DESTINATIONS = [
  "New York",
  "Dubai",
  "Paris",
  "Kyoto",
  "Rome",
  "Swiss Alps",
];

export function TripIntakeCard({ card, onSubmit }: TripIntakeCardProps) {
  const [destination, setDestination] = useState(card?.destination || "");
  const [origin, setOrigin] = useState(card?.default_origin || "Delhi");
  const [startDate, setStartDate] = useState(card?.default_start_date || "");
  const [endDate, setEndDate] = useState(card?.default_end_date || "");
  const [adults, setAdults] = useState(card?.default_adults || 2);
  const [travelStyle, setTravelStyle] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const dest = destination.trim() || "New York";
    const orig = origin.trim() || "Delhi";

    let datePhrase = "";
    if (startDate && endDate) {
      datePhrase = ` from ${startDate} to ${endDate}`;
    } else if (startDate) {
      datePhrase = ` starting ${startDate}`;
    }

    const paxPhrase = adults === 1 ? "1 adult" : `${adults} adults`;
    const stylePhrase = travelStyle.trim() ? ` with a ${travelStyle.trim()} vibe` : "";
    const prompt = `Plan a complete trip from ${orig} to ${dest}${datePhrase} for ${paxPhrase}${stylePhrase}`;

    if (onSubmit) {
      onSubmit(prompt);
    }
  };

  return (
    <div className="shrink-0 w-full max-w-[540px] rounded-3xl border border-line/80 bg-white shadow-card p-5 my-2">
      <div className="flex items-center gap-2 mb-1">
        <div className="size-8 rounded-full bg-olive/10 text-olive flex items-center justify-center font-bold">
          <Sparkles size={16} />
        </div>
        <div>
          <h3 className="font-bold text-sm text-ink">
            {card?.title || "Design Your Complete Journey"}
          </h3>
          <p className="text-[11px] text-muted">
            {card?.description ||
              "Fill in your travel preferences to generate day-by-day stops, verified flights, and curated boutique hotels."}
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="mt-4 space-y-4">
        {/* Destination */}
        <div>
          <label className="flex items-center gap-1.5 text-xs font-bold text-ink mb-1.5">
            <MapPin size={13} className="text-olive" /> Where do you want to go?
          </label>
          <input
            type="text"
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
            placeholder="e.g. New York, Dubai, Paris, Rome..."
            className="w-full rounded-2xl border border-line bg-cream/30 px-3.5 py-2 text-xs text-ink placeholder:text-muted/60 focus:border-olive focus:bg-white focus:outline-none transition-all"
          />
          {/* Quick chips */}
          <div className="flex flex-wrap gap-1.5 mt-2">
            {(card?.destinations || POPULAR_DESTINATIONS).map((dest, dIdx) => (
              <button
                key={`${dest}-${dIdx}`}
                type="button"
                onClick={() => setDestination(dest)}
                className={`rounded-full px-2.5 py-1 text-[11px] font-medium transition-all ${
                  destination.toLowerCase() === dest.toLowerCase()
                    ? "bg-olive text-white shadow-2xs"
                    : "bg-cream text-ink/80 hover:bg-cream/70"
                }`}
              >
                {dest}
              </button>
            ))}
          </div>
        </div>

        {/* Origin / Departure */}
        <div>
          <label className="flex items-center gap-1.5 text-xs font-bold text-ink mb-1.5">
            <Compass size={13} className="text-olive" /> Departing From
          </label>
          <input
            type="text"
            value={origin}
            onChange={(e) => setOrigin(e.target.value)}
            placeholder="e.g. Delhi, Mumbai, London, New York..."
            className="w-full rounded-2xl border border-line bg-cream/30 px-3.5 py-2 text-xs text-ink placeholder:text-muted/60 focus:border-olive focus:bg-white focus:outline-none transition-all"
          />
        </div>

        {/* Dates & Travelers */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
          <div>
            <label className="flex items-center gap-1.5 text-xs font-bold text-ink mb-1.5">
              <Calendar size={13} className="text-olive" /> Travel Dates
            </label>
            <div className="flex items-center gap-1.5">
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full rounded-xl border border-line bg-cream/30 px-2 py-1.5 text-[11px] text-ink focus:border-olive focus:outline-none"
              />
              <span className="text-muted text-xs">to</span>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full rounded-xl border border-line bg-cream/30 px-2 py-1.5 text-[11px] text-ink focus:border-olive focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="flex items-center gap-1.5 text-xs font-bold text-ink mb-1.5">
              <Users size={13} className="text-olive" /> Travelers
            </label>
            <div className="flex items-center justify-between rounded-2xl border border-line bg-cream/30 px-3 py-1.5">
              <span className="text-xs font-medium text-ink">
                {adults} {adults === 1 ? "Adult" : "Adults"}
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={adults <= 1}
                  onClick={() => setAdults((prev) => Math.max(1, prev - 1))}
                  className="size-6 rounded-full bg-white border border-line flex items-center justify-center text-xs font-bold text-ink disabled:opacity-40 hover:bg-cream transition-colors"
                >
                  -
                </button>
                <button
                  type="button"
                  disabled={adults >= 10}
                  onClick={() => setAdults((prev) => Math.min(10, prev + 1))}
                  className="size-6 rounded-full bg-white border border-line flex items-center justify-center text-xs font-bold text-ink disabled:opacity-40 hover:bg-cream transition-colors"
                >
                  +
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Travel Style / Vibe */}
        <div>
          <label className="flex items-center gap-1.5 text-xs font-bold text-ink mb-1.5">
            <Compass size={13} className="text-olive" /> Travel Style &amp; Pace
          </label>
          <input
            type="text"
            value={travelStyle}
            onChange={(e) => setTravelStyle(e.target.value)}
            placeholder="e.g. slow travel, luxury, foodie, adventurous, relaxed..."
            className="w-full rounded-2xl border border-line bg-cream/30 px-3.5 py-2 text-xs text-ink placeholder:text-muted/60 focus:border-olive focus:bg-white focus:outline-none transition-all"
          />
          <p className="text-[10px] text-muted mt-1">
            Tell me your travel style — slow, adventurous, romantic, family-friendly, etc.
          </p>
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          className="w-full mt-2 inline-flex items-center justify-center gap-2 rounded-2xl bg-olive px-4 py-3 text-xs font-bold text-white shadow-md hover:bg-ink transition-all cursor-pointer group"
        >
          <span>✨ Build My Complete Itinerary</span>
          <ArrowRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
        </button>
      </form>
    </div>
  );
}
