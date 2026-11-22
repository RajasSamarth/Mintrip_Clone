"use client";

import { useState, useEffect } from "react";
import NextImage from "next/image";
import {
  X,
  Star,
  MapPin,
  ExternalLink,
  Check,
  Clock,
  Utensils,
  Coffee,
  Bed,
  Users,
  ChevronRight,
  Sparkles,
  DollarSign,
  Plus,
  Phone,
  Globe,
  Info,
  Calendar,
} from "lucide-react";
import { AddToTripModal } from "@/components/common/AddToTripModal";

interface PlaceDetailModalProps {
  card: any | null;
  onClose: () => void;
  onPinClick?: (id: string) => void;
}

export function PlaceDetailModal({ card, onClose, onPinClick }: PlaceDetailModalProps) {
  const [activePhotoIdx, setActivePhotoIdx] = useState(0);
  const [activeTab, setActiveTab] = useState<"overview" | "menu" | "hours" | "reviews">("overview");
  const [addToTripOpen, setAddToTripOpen] = useState(false);

  useEffect(() => {
    setActivePhotoIdx(0);
    setActiveTab("overview");
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (card) {
      document.body.style.overflow = "hidden";
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.body.style.overflow = "auto";
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [card, onClose]);

  if (!card) return null;

  const category = (card.category || card.type || "other").toLowerCase();
  const isHotel = category === "hotel" || card.type === "hotel" || card.price_per_night != null;
  const isRestaurant =
    category === "restaurant" ||
    category === "cafe" ||
    category === "bar" ||
    category === "food" ||
    category === "dining";

  // Photos
  const photos: string[] =
    Array.isArray(card.photos) && card.photos.length > 0
      ? card.photos
      : card.image
      ? [card.image]
      : [
          "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=1200&q=80",
          "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=1200&q=80",
        ];

  // Price level formatting
  const priceLevelStr = card.price_level
    ? "₹".repeat(card.price_level)
    : card.price_range
    ? card.price_range
    : isRestaurant
    ? "₹₹"
    : "";

  // Deep metadata
  const meta = card.metadata || {};
  const menuCategories: any[] = card.menu || meta.menu || [];
  const reviews: any[] = card.reviews || meta.reviews || [];
  const openingHoursWeekly: Record<string, string> =
    card.opening_hours_weekly || meta.opening_hours_weekly || {};
  const diningAmenities: string[] =
    card.dining_amenities || meta.dining_amenities || meta.amenities || [];
  const phone = card.phone || meta.phone || "";
  const website = card.website || meta.website || "";

  // Determine current day for hours highlight
  const dayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  const currentDayName = dayNames[new Date().getDay()];

  return (
    <>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 overflow-y-auto bg-black/60 backdrop-blur-sm animate-fade-in">
        <div
          className="relative w-full max-w-3xl max-h-[90vh] overflow-y-auto rounded-3xl bg-white shadow-2xl border border-stone-200/90 text-stone-900 flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Close Button */}
          <button
            onClick={onClose}
            className="absolute top-4 right-4 z-20 w-9 h-9 rounded-full bg-white/90 backdrop-blur-md border border-stone-200 shadow-sm flex items-center justify-center text-stone-600 hover:text-stone-900 hover:bg-white transition-all"
            aria-label="Close details"
          >
            <X className="w-5 h-5" />
          </button>

          {/* Hero Photo Header */}
          <div className="relative h-64 sm:h-76 w-full overflow-hidden bg-stone-900 shrink-0">
            <img
              src={photos[activePhotoIdx] || photos[0]}
              alt={card.name || card.title || "Detail"}
              className="w-full h-full object-cover"
              referrerPolicy="no-referrer"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/25 to-transparent pointer-events-none" />

            {/* Badges on Hero */}
            <div className="absolute bottom-4 left-4 sm:left-6 right-4 sm:right-6 text-white pointer-events-none">
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <span className="bg-white/90 text-stone-900 px-2.5 py-0.5 rounded-full text-xs font-black uppercase tracking-wider backdrop-blur-md">
                  {category}
                </span>
                {priceLevelStr && (
                  <span className="bg-emerald-600 text-white px-2.5 py-0.5 rounded-full text-xs font-bold">
                    {priceLevelStr}
                  </span>
                )}
                {card.rating != null && (
                  <span className="bg-amber-500 text-white px-2.5 py-0.5 rounded-full text-xs font-black flex items-center gap-1">
                    <span>★</span>
                    <span>{typeof card.rating === "number" ? card.rating.toFixed(1) : card.rating}</span>
                  </span>
                )}
                {card.review_count > 0 && (
                  <span className="bg-black/40 text-stone-200 px-2.5 py-0.5 rounded-full text-[11px] font-medium backdrop-blur-md">
                    {card.review_count.toLocaleString()} verified reviews
                  </span>
                )}
              </div>

              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight drop-shadow-sm">
                {card.name || card.title}
              </h1>

              {card.address && (
                <p className="text-xs sm:text-sm text-stone-200 flex items-center gap-1.5 mt-1">
                  <MapPin className="w-4 h-4 text-amber-400 shrink-0" />
                  <span>{card.address}</span>
                </p>
              )}
            </div>
          </div>

          {/* Thumbnails Gallery */}
          {photos.length > 1 && (
            <div className="flex gap-2 p-2.5 bg-stone-900 overflow-x-auto thin-scrollbar shrink-0">
              {photos.map((p, idx) => (
                <button
                  key={idx}
                  onClick={() => setActivePhotoIdx(idx)}
                  className={`relative w-16 h-12 rounded-xl overflow-hidden shrink-0 border-2 transition-all ${
                    activePhotoIdx === idx
                      ? "border-amber-400 scale-105"
                      : "border-transparent opacity-60 hover:opacity-100"
                  }`}
                >
                  <img
                    src={p}
                    alt=""
                    className="w-full h-full object-cover"
                    referrerPolicy="no-referrer"
                  />
                </button>
              ))}
            </div>
          )}

          {/* Tab Navigation */}
          <div className="flex items-center gap-1 border-b border-stone-200 px-5 pt-3 bg-stone-50/80 sticky top-0 z-10 backdrop-blur-md">
            <button
              onClick={() => setActiveTab("overview")}
              className={`pb-2.5 px-3 text-xs font-bold border-b-2 transition-all ${
                activeTab === "overview"
                  ? "border-stone-900 text-stone-900"
                  : "border-transparent text-stone-500 hover:text-stone-900"
              }`}
            >
              Overview
            </button>

            {isRestaurant && (
              <button
                onClick={() => setActiveTab("menu")}
                className={`pb-2.5 px-3 text-xs font-bold border-b-2 transition-all ${
                  activeTab === "menu"
                    ? "border-stone-900 text-stone-900"
                    : "border-transparent text-stone-500 hover:text-stone-900"
                }`}
              >
                Menu & Dining {menuCategories.length > 0 && `(${menuCategories.reduce((acc, c) => acc + (c.items?.length || 0), 0)})`}
              </button>
            )}

            <button
              onClick={() => setActiveTab("hours")}
              className={`pb-2.5 px-3 text-xs font-bold border-b-2 transition-all ${
                activeTab === "hours"
                  ? "border-stone-900 text-stone-900"
                  : "border-transparent text-stone-500 hover:text-stone-900"
              }`}
            >
              Hours & Amenities
            </button>

            {isRestaurant && (
              <button
                onClick={() => setActiveTab("reviews")}
                className={`pb-2.5 px-3 text-xs font-bold border-b-2 transition-all ${
                  activeTab === "reviews"
                    ? "border-stone-900 text-stone-900"
                    : "border-transparent text-stone-500 hover:text-stone-900"
                }`}
              >
                Diner Reviews {reviews.length > 0 && `(${reviews.length})`}
              </button>
            )}
          </div>

          {/* Tab Contents */}
          <div className="p-5 sm:p-7 space-y-6 flex-1">
            {/* TAB 1: OVERVIEW */}
            {activeTab === "overview" && (
              <div className="space-y-6 animate-fade-in">
                {/* Description */}
                <div>
                  <h2 className="text-xs font-bold uppercase tracking-wider text-stone-500 mb-2">
                    About this venue
                  </h2>
                  <p className="text-sm leading-relaxed text-stone-700">
                    {card.description ||
                      card.summary ||
                      `${card.name || "This venue"} is an exceptional ${category} in ${
                        card.destination || "the city"
                      }, famed for genuine hospitality, flavorful cuisine, and memorable local experiences.`}
                  </p>
                </div>

                {/* Quick Info Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {card.opening_hours && (
                    <div className="rounded-2xl border border-stone-200/80 bg-stone-50 p-3.5 flex items-start gap-3">
                      <Clock className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                      <div>
                        <p className="text-xs font-bold text-stone-900">Today&apos;s Hours</p>
                        <p className="text-xs text-stone-600 mt-0.5">
                          {openingHoursWeekly[currentDayName] || card.opening_hours}
                        </p>
                      </div>
                    </div>
                  )}

                  {card.price_range && (
                    <div className="rounded-2xl border border-stone-200/80 bg-stone-50 p-3.5 flex items-start gap-3">
                      <DollarSign className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                      <div>
                        <p className="text-xs font-bold text-stone-900">Average Cost</p>
                        <p className="text-xs text-stone-600 mt-0.5">{card.price_range}</p>
                      </div>
                    </div>
                  )}

                  {phone && (
                    <div className="rounded-2xl border border-stone-200/80 bg-stone-50 p-3.5 flex items-start gap-3">
                      <Phone className="w-4 h-4 text-sky-600 shrink-0 mt-0.5" />
                      <div>
                        <p className="text-xs font-bold text-stone-900">Reservations & Phone</p>
                        <p className="text-xs text-stone-600 mt-0.5">{phone}</p>
                      </div>
                    </div>
                  )}

                  {website && (
                    <div className="rounded-2xl border border-stone-200/80 bg-stone-50 p-3.5 flex items-start gap-3">
                      <Globe className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
                      <div>
                        <p className="text-xs font-bold text-stone-900">Online Table Booking</p>
                        <a
                          href={website}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-indigo-600 hover:underline font-semibold flex items-center gap-1 mt-0.5"
                        >
                          <span>Visit website</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>
                    </div>
                  )}
                </div>

                {/* Tags */}
                {card.tags && card.tags.length > 0 && (
                  <div>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-stone-500 mb-2">
                      Tags & Features
                    </h3>
                    <div className="flex flex-wrap gap-1.5">
                      {card.tags.map((tag: string) => (
                        <span
                          key={tag}
                          className="rounded-xl bg-stone-100 px-2.5 py-1 text-xs font-semibold text-stone-700"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* TAB 2: MENU & DINING */}
            {activeTab === "menu" && (
              <div className="space-y-6 animate-fade-in">
                {menuCategories.length > 0 ? (
                  <div className="space-y-6">
                    {menuCategories.map((categoryGroup: any, idx: number) => (
                      <div key={idx} className="space-y-3">
                        <div className="flex items-center gap-2 border-b border-stone-100 pb-2">
                          <Utensils className="w-4 h-4 text-amber-600" />
                          <h3 className="text-sm font-bold text-stone-900">
                            {categoryGroup.category}
                          </h3>
                        </div>

                        <div className="grid grid-cols-1 gap-3">
                          {(categoryGroup.items || []).map((item: any, itemIdx: number) => (
                            <div
                              key={itemIdx}
                              className="rounded-2xl border border-stone-200/80 p-3.5 bg-stone-50/40 hover:bg-stone-50 transition-colors flex items-start justify-between gap-3"
                            >
                              <div className="min-w-0">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <h4 className="text-xs font-bold text-stone-900">{item.name}</h4>
                                  {(item.dietary || []).map((d: string) => (
                                    <span
                                      key={d}
                                      className={`rounded-md px-1.5 py-0.5 text-[9px] font-bold ${
                                        d === "Veg"
                                          ? "bg-emerald-50 text-emerald-700 border border-emerald-200/60"
                                          : d === "Spicy"
                                          ? "bg-red-50 text-red-700 border border-red-200/60"
                                          : d === "Chef's Special"
                                          ? "bg-amber-50 text-amber-800 border border-amber-200/60"
                                          : "bg-stone-100 text-stone-700 border border-stone-200"
                                      }`}
                                    >
                                      {d === "Veg" && "🌱 "}
                                      {d === "Spicy" && "🌶️ "}
                                      {d === "Chef's Special" && "⭐ "}
                                      {d}
                                    </span>
                                  ))}
                                </div>
                                <p className="text-xs text-stone-600 mt-1 leading-relaxed">
                                  {item.description}
                                </p>
                              </div>

                              <div className="shrink-0 text-right">
                                <span className="text-xs font-black text-stone-900 bg-white border border-stone-200 px-2.5 py-1 rounded-xl shadow-2xs">
                                  {item.price}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-2xl border border-stone-200 bg-stone-50 p-8 text-center">
                    <Utensils className="w-8 h-8 text-stone-300 mx-auto mb-2" />
                    <p className="text-sm font-bold text-stone-800">Menu Not Listed Online</p>
                    <p className="text-xs text-stone-500 mt-1 max-w-sm mx-auto">
                      This venue does not publish an online a la carte menu. Please consult the staff or call directly for seasonal specials.
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* TAB 3: HOURS & AMENITIES */}
            {activeTab === "hours" && (
              <div className="space-y-6 animate-fade-in">
                {/* Weekly Hours Table */}
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-stone-500 mb-3 flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-stone-700" />
                    <span>Weekly Operating Hours</span>
                  </h3>

                  {Object.keys(openingHoursWeekly).length > 0 ? (
                    <div className="rounded-2xl border border-stone-200 overflow-hidden divide-y divide-stone-100">
                      {Object.entries(openingHoursWeekly).map(([day, hours]) => {
                        const isToday = day === currentDayName;
                        return (
                          <div
                            key={day}
                            className={`flex items-center justify-between p-3 text-xs ${
                              isToday ? "bg-amber-50/60 font-bold text-amber-950" : "bg-white text-stone-700"
                            }`}
                          >
                            <span className="flex items-center gap-2">
                              <span>{day}</span>
                              {isToday && (
                                <span className="rounded-full bg-amber-200/80 px-2 py-0.5 text-[9px] font-black text-amber-900">
                                  Today
                                </span>
                              )}
                            </span>
                            <span className={isToday ? "text-amber-900" : "text-stone-600"}>
                              {hours}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-xs text-stone-600 bg-stone-50 p-4 rounded-2xl border border-stone-200">
                      {card.opening_hours || "Standard operating hours: 11:30 AM – 11:00 PM Daily"}
                    </p>
                  )}
                </div>

                {/* Dining Amenities */}
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-stone-500 mb-3">
                    Dining Features & Amenities
                  </h3>
                  {diningAmenities.length > 0 ? (
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                      {diningAmenities.map((amenity) => (
                        <div
                          key={amenity}
                          className="rounded-xl border border-stone-200 bg-stone-50/60 px-3 py-2 flex items-center gap-2 text-xs font-medium text-stone-800"
                        >
                          <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                          <span className="truncate">{amenity}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex flex-wrap gap-2 text-xs">
                      {["Dine-in", "Takeaway", "Vegetarian Options", "Takes Reservations"].map((am) => (
                        <span
                          key={am}
                          className="rounded-xl border border-stone-200 bg-stone-50 px-3 py-1.5 text-stone-700 flex items-center gap-1.5"
                        >
                          <Check className="w-3 h-3 text-emerald-600" />
                          <span>{am}</span>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* TAB 4: REVIEWS */}
            {activeTab === "reviews" && isRestaurant && (
              <div className="space-y-4 animate-fade-in">
                <div className="flex items-center justify-between pb-2 border-b border-stone-100">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-stone-500">
                    Verified Guest Impressions
                  </h3>
                  {card.rating != null && (
                    <span className="text-xs font-black text-stone-900 flex items-center gap-1">
                      <Star className="w-3.5 h-3.5 fill-amber-500 text-amber-500" />
                      <span>{typeof card.rating === "number" ? card.rating.toFixed(1) : card.rating} / 5.0</span>
                    </span>
                  )}
                </div>

                {reviews.length > 0 ? (
                  <div className="space-y-3">
                    {reviews.map((rev: any, idx: number) => (
                      <div
                        key={idx}
                        className="rounded-2xl border border-stone-200/80 bg-stone-50/50 p-4 space-y-2"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-stone-900">{rev.author || "Verified Diner"}</span>
                          <span className="text-[10px] text-stone-400 font-medium">
                            {rev.relative_time || "Recent"}
                          </span>
                        </div>
                        <div className="flex items-center gap-1 text-amber-500 text-xs">
                          {[...Array(Math.round(rev.rating || 5))].map((_, i) => (
                            <Star key={i} className="w-3 h-3 fill-amber-500" />
                          ))}
                        </div>
                        <p className="text-xs text-stone-700 leading-relaxed italic">
                          “{rev.text}”
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-2xl border border-stone-200 bg-stone-50 p-6 text-center text-xs text-stone-500">
                    No verified reviews published online for this listing yet.
                  </div>
                )}
              </div>
            )}

            {/* Hotel specific: Prices according to rooms if applicable */}
            {isHotel && card.room_types && card.room_types.length > 0 && (
              <div className="pt-4 border-t border-stone-100">
                <h3 className="text-xs font-bold uppercase tracking-wider text-stone-500 mb-3">
                  Available Room Configurations
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {card.room_types.map((rm: any, idx: number) => (
                    <div key={idx} className="rounded-2xl border border-stone-200 p-3.5 bg-stone-50/50">
                      <p className="text-xs font-bold text-stone-900">{rm.name}</p>
                      <p className="text-[10px] text-stone-500">{rm.bed_type}</p>
                      <p className="text-sm font-black text-stone-900 mt-2">
                        {rm.price ? `₹${Math.round(rm.price).toLocaleString()}/nt` : "Price on request"}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Actions Footer */}
            <div className="pt-4 border-t border-stone-100 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setAddToTripOpen(true)}
                  className="rounded-xl bg-stone-900 px-4 py-2 text-xs font-bold text-white hover:bg-stone-800 flex items-center gap-1.5 transition-all shadow-xs"
                >
                  <Plus className="w-3.5 h-3.5 text-amber-400" />
                  <span>Add to Itinerary</span>
                </button>

                {onPinClick && (
                  <button
                    onClick={() => {
                      if (card.id) onPinClick(card.id);
                      onClose();
                    }}
                    className="rounded-xl border border-stone-300 bg-white px-3.5 py-2 text-xs font-bold text-stone-800 hover:bg-stone-50 flex items-center gap-1.5 transition-colors shadow-2xs"
                  >
                    <MapPin className="w-3.5 h-3.5 text-stone-600" />
                    <span>Pin on Map</span>
                  </button>
                )}
              </div>

              {card.address && (
                <a
                  href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
                    (card.name || card.title) + " " + card.address
                  )}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-xl border border-stone-300 bg-white px-3.5 py-2 text-xs font-bold text-stone-700 hover:bg-stone-50 flex items-center gap-1.5 transition-all shadow-2xs"
                >
                  <span>Google Maps</span>
                  <ExternalLink className="w-3 h-3 text-stone-400" />
                </a>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Add To Trip Modal */}
      <AddToTripModal
        isOpen={addToTripOpen}
        onClose={() => setAddToTripOpen(false)}
        itemType="place"
        itemData={card}
      />
    </>
  );
}
