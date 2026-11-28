"use client";

import { useState } from "react";
import Image from "next/image";
import { Star, MapPin, ExternalLink, Bed, Plus } from "lucide-react";
import { AddToTripModal } from "@/components/common/AddToTripModal";

interface HotelCardProps {
  card: {
    id?: string;
    name?: string;
    stars?: number;
    rating?: number;
    review_count?: number;
    reviews_count?: number;
    address?: string;
    price_inr?: number;
    price_usd?: number;
    price_per_night?: number;
    photos?: string[];
    image?: string;
    amenities?: string[];
    description?: string;
    booking_url?: string;
    destination?: string;
  };
}

export function HotelCard({ card }: HotelCardProps) {
  const [addToTripOpen, setAddToTripOpen] = useState(false);
  const name = card.name || "Boutique Hotel";
  const stars = card.stars || 4;
  const rating = card.rating || 4.6;
  const reviews = card.review_count || card.reviews_count || 500;
  const address = card.address || "";
  const photo = card.image || (card.photos && card.photos[0]) || "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=800&q=80";
  
  let priceDisplay = "Check rates";
  if (card.price_inr) {
    priceDisplay = `₹${Math.round(card.price_inr).toLocaleString("en-IN")}/night`;
  } else if (card.price_per_night) {
    priceDisplay = `$${Math.round(card.price_per_night)}/night`;
  } else if (card.price_usd) {
    priceDisplay = `$${Math.round(card.price_usd)}/night`;
  }

  const googleHotelsUrl = card.booking_url || `https://www.google.com/travel/hotels?q=${encodeURIComponent(name + " " + (card.destination || ""))}`;

  return (
    <article className="shrink-0 w-[270px] rounded-3xl border border-line/80 bg-white shadow-card overflow-hidden lift flex flex-col justify-between group hover:border-olive/50 hover:shadow-lg transition-all">
      <div className="relative h-[150px] overflow-hidden">
        <Image
          src={photo}
          alt={name}
          fill
          className="object-cover group-hover:scale-105 transition-transform duration-500"
          sizes="270px"
          onError={(e) => {
            const target = e.target as HTMLImageElement;
            if (target) {
              target.src = "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=800&q=80";
            }
          }}
        />
        <div className="absolute top-3 left-3 flex gap-1">
          <span className="rounded-full bg-white/90 backdrop-blur-md px-2 py-0.5 text-[10px] font-semibold text-ink flex items-center gap-1 shadow-sm">
            <Bed size={11} className="text-olive" /> Stay
          </span>
          {stars > 0 && (
            <span className="rounded-full bg-black/60 backdrop-blur-md px-2 py-0.5 text-[10px] font-semibold text-white">
              {stars}★
            </span>
          )}
        </div>
      </div>

      <div className="p-4 flex flex-col gap-2 justify-between flex-1">
        <div>
          <div className="flex items-start justify-between gap-1 mb-1">
            <h4 className="font-bold text-sm text-ink leading-tight line-clamp-1 group-hover:text-olive transition-colors">
              {name}
            </h4>
            <span className="flex items-center gap-0.5 rounded-full border border-line bg-paper px-1.5 py-0.5 text-[10px] font-bold text-ink shrink-0">
              <Star size={10} className="text-amber-500 fill-amber-500" />
              {typeof rating === "number" ? rating.toFixed(1) : rating}
            </span>
          </div>

          {address && (
            <p className="text-[11px] text-muted flex items-center gap-1 line-clamp-1">
              <MapPin size={11} className="shrink-0" /> {address}
            </p>
          )}

          {card.description && (
            <p className="text-xs text-ink/75 line-clamp-2 mt-1 leading-relaxed">
              {card.description}
            </p>
          )}
        </div>

        <div className="pt-2 border-t border-line/50 flex items-center justify-between gap-2 mt-1">
          <div>
            <span className="text-xs font-bold text-ink">{priceDisplay}</span>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => setAddToTripOpen(true)}
              className="inline-flex items-center gap-1 rounded-full border border-line bg-white px-2.5 py-1.5 text-xs font-semibold text-ink hover:bg-cream transition-colors"
              title="Add stay to trip"
            >
              <Plus size={11} className="text-olive" /> Trip
            </button>
            <a
              href={googleHotelsUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 rounded-full bg-ink px-3 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-olive transition-colors"
            >
              Stay <ExternalLink size={11} />
            </a>
          </div>
        </div>
      </div>

      <AddToTripModal
        isOpen={addToTripOpen}
        onClose={() => setAddToTripOpen(false)}
        itemType="hotel"
        itemData={card}
      />
    </article>
  );
}
