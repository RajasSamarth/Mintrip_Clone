"use client";

import Image from "next/image";
import Link from "next/link";
import { Calendar, MapPin, ArrowRight, Sparkles } from "lucide-react";

interface TripCardProps {
  card: {
    id?: string;
    trip_id?: string;
    title?: string;
    destination?: string;
    day_count?: number;
    days?: number;
    stop_count?: number;
    stops?: number;
    budget?: number;
    image?: string;
    cover_image?: string;
    summary?: string;
  };
}

export function TripCard({ card }: TripCardProps) {
  const tripId = card.trip_id || card.id || "";
  const title = card.title || "Your Custom Itinerary";
  const days = card.day_count ?? card.days ?? 3;
  const stops = card.stop_count ?? card.stops ?? 9;
  const image = card.image || card.cover_image || "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?auto=format&fit=crop&w=800&q=80";

  return (
    <article className="shrink-0 w-[290px] rounded-3xl border border-line/80 bg-white shadow-card overflow-hidden lift flex flex-col group hover:border-olive/50 hover:shadow-lg transition-all">
      <div className="relative h-[160px] overflow-hidden">
        <Image
          src={image}
          alt={title}
          fill
          className="object-cover group-hover:scale-105 transition-transform duration-500"
          sizes="290px"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/20 to-transparent" />
        <span className="absolute top-3 left-3 rounded-full bg-white/90 backdrop-blur-md px-2.5 py-1 text-[11px] font-semibold text-ink flex items-center gap-1 shadow-sm">
          <Sparkles size={12} className="text-olive" /> Tour Itinerary
        </span>
        <div className="absolute bottom-3 left-3 right-3 text-white">
          <h4 className="font-bold text-sm leading-tight text-white drop-shadow-md line-clamp-1">
            {title}
          </h4>
        </div>
      </div>

      <div className="p-4 flex flex-col gap-3 justify-between flex-1">
        <div className="flex items-center gap-2 text-xs text-muted">
          <span className="inline-flex items-center gap-1 font-semibold text-ink/80 bg-cream px-2 py-0.5 rounded-full">
            <Calendar size={12} /> {days} Days
          </span>
          <span className="inline-flex items-center gap-1 font-semibold text-ink/80 bg-cream px-2 py-0.5 rounded-full">
            <MapPin size={12} /> {stops} Curated Stops
          </span>
        </div>

        {card.summary && (
          <p className="text-xs text-ink/70 line-clamp-2 leading-relaxed">
            {card.summary}
          </p>
        )}

        <div className="pt-2 border-t border-line/50 flex items-center justify-between">
          <span className="text-[11px] text-muted font-medium">Ready to explore</span>
          {tripId ? (
            <Link
              href={`/trip/${tripId}`}
              className="inline-flex items-center gap-1.5 rounded-full bg-ink px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-olive transition-colors"
            >
              View Full Plan <ArrowRight size={12} />
            </Link>
          ) : (
            <span className="text-xs text-olive font-semibold">Saved to Trips</span>
          )}
        </div>
      </div>
    </article>
  );
}
