"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { Star, MapPin, Clock, ChevronRight, Eye } from "lucide-react";
import { PlaceDetailModal } from "@/components/chat/PlaceDetailModal";

const CATEGORY_COLOR: Record<string, string> = {
  hotel: "#434717",
  restaurant: "#e86a4a",
  cafe: "#9a5f2c",
  attraction: "#2f4a63",
  activity: "#6b4f8a",
  bar: "#b85c38",
  shopping: "#a8d8ea",
  other: "#434717",
};

interface PlaceCardProps {
  card: any;
}

export function PlaceCard({ card }: PlaceCardProps) {
  const [showModal, setShowModal] = useState(false);
  const categoryColor = CATEGORY_COLOR[card.category || "other"] || CATEGORY_COLOR.other;
  const isTrip = card.type === "trip";
  const isHotel = card.type === "hotel";
  const isFlight = card.type === "flight";

  return (
    <>
      <article
        onClick={() => setShowModal(true)}
        className="shrink-0 w-[260px] rounded-3xl border border-line bg-white shadow-card overflow-hidden lift flex flex-col media-zoom group cursor-pointer hover:border-stone-400 hover:shadow-md transition-all"
      >
        {card.image && (
          <div className="relative h-[170px] overflow-hidden">
            <Image src={card.image} alt={card.name} className="object-cover group-hover:scale-105 transition-transform duration-300" sizes="(max-width: 768px) 100vw, 260px" fill onError={(e) => { const target = e.target as HTMLImageElement; if (target) { target.src = "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?auto=format&fit=crop&w=800&q=80"; } } } />
            {card.category && (
              <span className="absolute top-3 left-3 rounded-full border border-white/50 bg-white/80 px-2 py-0.5 text-[10px] font-semibold text-ink/80 backdrop-blur">
                {card.category.charAt(0).toUpperCase() + card.category.slice(1)}
              </span>
            )}
            {isTrip && (
              <div className="absolute bottom-3 right-3 flex gap-2">
                <span className="rounded-full bg-ink/80 px-2 py-1 text-[10px] font-medium text-white">{card.day_count} days</span>
                <span className="rounded-full bg-ink/80 px-2 py-1 text-[10px] font-medium text-white">{card.stop_count} stops</span>
              </div>
            )}
          </div>
        )}
        <div className="p-4 flex flex-col gap-3 flex-1 justify-between">
          <div>
            <div className="flex items-start justify-between gap-2 mb-1">
              <h3 className="font-semibold text-ink leading-tight group-hover:text-amber-800 transition-colors">{card.name || card.title}</h3>
              {card.rating != null && (
                <span className="flex items-center gap-1 rounded-full border border-line bg-white px-2 py-0.5 text-[11px] font-medium text-ink shrink-0">
                  <Star size={12} className="text-amber-400 fill-amber-400" />
                  {typeof card.rating === "number" ? card.rating.toFixed(1) : card.rating}
                </span>
              )}
            </div>
            <p className="text-xs text-muted leading-relaxed line-clamp-2">{card.description || card.summary || ""}</p>
          </div>

          <div>
            <div className="flex items-center gap-3 text-xs text-muted mb-2">
              {card.address && (
                <span className="flex items-center gap-1 line-clamp-1">
                  <MapPin size={12} className="shrink-0" /> {card.address}
                </span>
              )}
              {card.price_per_night != null && (
                <span className="text-ink font-semibold shrink-0">
                  ₹{Math.round(card.price_per_night).toLocaleString()}/night
                </span>
              )}
              {card.price_usd != null && (
                <span className="text-ink font-semibold shrink-0">${card.price_usd}</span>
              )}
            </div>
            <div className="flex items-center justify-between pt-2 border-t border-line/40">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setShowModal(true);
                }}
                className="inline-flex items-center gap-1 text-[11px] font-bold text-amber-800 hover:text-amber-950"
              >
                <Eye size={12} />
                View details
              </button>
              <Link
                href="/chat"
                onClick={(e) => {
                  e.stopPropagation();
                  e.preventDefault();
                  window.dispatchEvent(
                    new CustomEvent("mt-highlight-card", { detail: { id: card.id } })
                  );
                }}
                className="inline-flex items-center gap-1 rounded-full border border-line bg-white px-2.5 py-0.5 text-[10px] font-medium text-ink hover:bg-ink hover:text-white transition-colors"
              >
                Pin
                <ChevronRight size={10} />
              </Link>
            </div>
          </div>
        </div>
      </article>

      {/* Place / Restaurant Detail Modal */}
      {showModal && (
        <PlaceDetailModal
          card={card}
          onClose={() => setShowModal(false)}
          onPinClick={(id) => {
            window.dispatchEvent(
              new CustomEvent("mt-highlight-card", { detail: { id } })
            );
          }}
        />
      )}
    </>
  );
}
