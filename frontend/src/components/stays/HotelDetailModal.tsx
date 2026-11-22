"use client";

import { useState, useEffect } from "react";
import NextImage from "next/image";
import {
  X,
  Star,
  MapPin,
  ExternalLink,
  Check,
  Users,
  Bed,
  Wifi,
  Coffee,
  Sparkles,
  ShieldCheck,
  Waves,
  Utensils,
  ChevronRight,
  Maximize2,
  Plus
} from "lucide-react";
import { Hotel, RoomType } from "@/app/stays/page";

interface HotelDetailModalProps {
  hotel: Hotel | null;
  onClose: () => void;
  selectedCurrency: string;
  currencies: Record<string, { symbol: string; label: string; rateFromINR: number }>;
  onAddToTrip?: (hotel: Hotel) => void;
}

const MODAL_FALLBACK_IMAGE =
  "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=1200&q=80";

function SafeModalImage({ src, alt, className = "" }: { src?: string; alt: string; className?: string }) {
  const [imgSrc, setImgSrc] = useState(src || MODAL_FALLBACK_IMAGE);

  useEffect(() => {
    setImgSrc(src || MODAL_FALLBACK_IMAGE);
  }, [src]);

  return (
    <img
      src={imgSrc}
      alt={alt}
      referrerPolicy="no-referrer"
      onError={() => {
        if (imgSrc !== MODAL_FALLBACK_IMAGE) {
          setImgSrc(MODAL_FALLBACK_IMAGE);
        }
      }}
      className={className}
      loading="lazy"
    />
  );
}

export function HotelDetailModal({
  hotel,
  onClose,
  selectedCurrency,
  currencies,
  onAddToTrip,
}: HotelDetailModalProps) {
  const [activePhotoIdx, setActivePhotoIdx] = useState(0);

  useEffect(() => {
    setActivePhotoIdx(0);
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (hotel) {
      document.body.style.overflow = "hidden";
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.body.style.overflow = "auto";
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [hotel, onClose]);

  if (!hotel) return null;

  const curr = currencies[selectedCurrency] || currencies.INR;
  const hotelCurr = (hotel.currency || "INR").toUpperCase();

  function formatPrice(amount: number | null | undefined): { formatted: string; isUnavailable: boolean } {
    if (amount == null || amount <= 0 || hotel?.price_unavailable) {
      return { formatted: "Price unavailable", isUnavailable: true };
    }
    let converted = amount;
    if (hotelCurr === "INR" && selectedCurrency !== "INR") {
      converted = amount * curr.rateFromINR;
    } else if (hotelCurr === "USD" && selectedCurrency === "INR") {
      converted = amount * 85.0;
    } else if (hotelCurr === "USD" && selectedCurrency !== "USD") {
      converted = (amount * 85.0) * curr.rateFromINR;
    }
    return {
      formatted: `${curr.symbol}${Math.round(converted).toLocaleString()}`,
      isUnavailable: false,
    };
  }

  const { formatted: mainPriceFormatted, isUnavailable: mainIsUnavailable } = formatPrice(hotel.price_per_night);

  const photos = hotel.photos && hotel.photos.length > 0
    ? hotel.photos
    : [
        "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=1200&q=80",
      ];

  // Default rooms if not present
  const defaultRooms: RoomType[] = [
    {
      name: "Standard Room",
      description: "Comfortable guestroom with plush bedding, work desk and modern ensuite bathroom.",
      bed_type: "1 King Bed or 2 Twin Beds",
      capacity: 2,
      price: hotel.price_per_night,
      amenities: ["Free High-Speed Wi-Fi", "Air Conditioning", "Ensuite Bathroom", "Electric Kettle", "Smart TV"],
    },
    {
      name: "Deluxe Room with City View",
      description: "Spacious corner room featuring panoramic views, soaking bathtub and upgraded luxury amenities.",
      bed_type: "1 King Bed",
      capacity: 2,
      price: hotel.price_per_night ? Math.round(hotel.price_per_night * 1.25) : null,
      amenities: ["City View", "Deep Soaking Tub", "Espresso Machine", "Free Wi-Fi", "Air Conditioning", "Bathrobes"],
    },
    {
      name: "Executive Club Suite",
      description: "Luxury suite with private lounge access, separate living quarters and priority concierge.",
      bed_type: "1 Super King Bed",
      capacity: 3,
      price: hotel.price_per_night ? Math.round(hotel.price_per_night * 1.65) : null,
      amenities: ["Lounge Access", "Complimentary Breakfast", "Separate Living Area", "Spa Bath", "Minibar"],
    },
    {
      name: "Presidential Family Suite",
      description: "Expansive multi-room suite designed for supreme comfort, dining space and skyline views.",
      bed_type: "2 King Beds",
      capacity: 4,
      price: hotel.price_per_night ? Math.round(hotel.price_per_night * 2.35) : null,
      amenities: ["2 Bedrooms", "Balcony", "Kitchenette", "Butler Service", "Complimentary Breakfast", "Free Wi-Fi"],
    },
  ];

  const roomsToDisplay = hotel.room_types && hotel.room_types.length > 0 ? hotel.room_types : defaultRooms;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 overflow-y-auto bg-black/60 backdrop-blur-sm animate-fade-in">
      <div
        className="relative w-full max-w-4xl max-h-[92vh] overflow-y-auto rounded-3xl bg-white shadow-2xl border border-stone-200/90 text-stone-900 flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Sticky Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 z-20 w-9 h-9 rounded-full bg-white/90 backdrop-blur-md border border-stone-200 shadow-sm flex items-center justify-center text-stone-600 hover:text-stone-900 hover:bg-white transition-all"
          aria-label="Close details"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Photo Gallery Header */}
        <div className="relative w-full bg-stone-950 flex flex-col">
          {/* Main Hero Photo */}
          <div className="relative h-72 sm:h-96 w-full overflow-hidden bg-stone-900">
            <SafeModalImage
              src={photos[activePhotoIdx] || photos[0]}
              alt={hotel.name}
              className="w-full h-full object-cover"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent pointer-events-none" />

            {/* Title & Badges on Hero */}
            <div className="absolute bottom-4 left-4 sm:left-6 right-4 sm:right-6 text-white pointer-events-none">
              <div className="flex flex-wrap items-center gap-2 mb-2">
                {hotel.stars > 0 && (
                  <span className="bg-amber-500/90 backdrop-blur-md px-2.5 py-0.5 rounded-full text-xs font-bold flex items-center gap-1 text-white shadow-xs">
                    {[...Array(hotel.stars)].map((_, i) => (
                      <Star key={i} className="w-3 h-3 fill-white text-white" />
                    ))}
                    <span>{hotel.stars}-Star</span>
                  </span>
                )}
                {hotel.rating != null && (
                  <span className="bg-white/95 text-stone-900 px-2.5 py-0.5 rounded-full text-xs font-black flex items-center gap-1 shadow-xs">
                    <span className="text-amber-500 font-bold">★</span>
                    <span>{hotel.rating.toFixed(1)}</span>
                    <span className="text-stone-500 font-normal">
                      ({hotel.review_count > 0 ? `${hotel.review_count.toLocaleString()} reviews` : "Verified"})
                    </span>
                  </span>
                )}
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight drop-shadow-sm leading-tight">
                {hotel.name}
              </h1>
              <p className="text-xs sm:text-sm text-stone-200 flex items-center gap-1.5 mt-1">
                <MapPin className="w-4 h-4 text-amber-400 shrink-0" />
                <span>{hotel.address}</span>
              </p>
            </div>
          </div>

          {/* Thumbnail Strip */}
          {photos.length > 1 && (
            <div className="flex gap-2 p-3 bg-stone-900/90 overflow-x-auto thin-scrollbar">
              {photos.map((photo, idx) => (
                <button
                  key={idx}
                  onClick={() => setActivePhotoIdx(idx)}
                  className={`relative w-16 h-12 sm:w-20 sm:h-14 rounded-xl overflow-hidden shrink-0 border-2 transition-all ${
                    activePhotoIdx === idx ? "border-amber-400 scale-105 shadow-md" : "border-transparent opacity-60 hover:opacity-100"
                  }`}
                >
                  <SafeModalImage src={photo} alt="" className="w-full h-full object-cover" />
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Modal Body */}
        <div className="p-5 sm:p-8 space-y-8">
          {/* Quick Stats & Rate Header */}
          <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-2xl bg-stone-50 border border-stone-200/80">
            <div>
              <p className="text-xs text-stone-500 font-bold uppercase tracking-wider">Prices starting from</p>
              {mainIsUnavailable ? (
                <div className="mt-1">
                  <span className="inline-block rounded-full bg-amber-50 border border-amber-200/80 px-3 py-1 text-xs font-bold text-amber-800">
                    Price unavailable for current dates
                  </span>
                  <p className="text-xs text-stone-500 mt-1">Check rates directly on Google Hotels</p>
                </div>
              ) : (
                <div className="flex items-baseline gap-2 mt-0.5">
                  <span className="text-2xl sm:text-3xl font-black text-stone-900 tracking-tight">
                    {mainPriceFormatted}
                  </span>
                  <span className="text-xs font-medium text-stone-500">/ night • room taxes included</span>
                </div>
              )}
            </div>

            <div className="flex items-center gap-2">
              <a
                href={hotel.booking_url || `https://www.google.com/travel/hotels/${encodeURIComponent(hotel.destination)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-2xl bg-stone-900 px-5 py-3 text-xs sm:text-sm font-bold text-white shadow-xs hover:bg-stone-800 transition-all flex items-center gap-2 active:scale-98"
              >
                <span>Check Live Rates on Google</span>
                <ExternalLink className="w-4 h-4 text-stone-300" />
              </a>
            </div>
          </div>

          {/* Overview & Description */}
          <div>
            <h2 className="text-lg font-bold text-stone-900 mb-2">Overview</h2>
            <p className="text-sm leading-relaxed text-stone-700">
              {hotel.description ||
                `${hotel.name} offers premium hospitality and authentic comfort in ${hotel.destination}. Perfectly positioned near top cultural landmarks, fine dining and transport transit, featuring curated amenities and dedicated guest service.`}
            </p>
          </div>

          {/* Prices According to Rooms (Room Types & Rates) */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <div>
                <h2 className="text-lg font-bold text-stone-900">Prices According to Rooms</h2>
                <p className="text-xs text-stone-500">Select a room configuration to view dedicated features and rates</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {roomsToDisplay.map((room, idx) => {
                const roomPrice = formatPrice(room.price);
                return (
                  <div
                    key={idx}
                    className="rounded-2xl border border-stone-200/90 bg-white p-4 shadow-2xs hover:border-stone-400 hover:shadow-xs transition-all flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-start justify-between gap-2 mb-1.5">
                        <h3 className="font-bold text-sm text-stone-900">{room.name}</h3>
                        <span className="shrink-0 rounded-full bg-stone-100 px-2 py-0.5 text-[10px] font-bold text-stone-600 flex items-center gap-1">
                          <Users className="w-3 h-3" />
                          <span>{room.capacity || 2} Guests</span>
                        </span>
                      </div>

                      <p className="text-xs text-stone-500 mb-2 flex items-center gap-1.5">
                        <Bed className="w-3.5 h-3.5 text-stone-400" />
                        <span>{room.bed_type || "1 King Bed or 2 Twin Beds"}</span>
                      </p>

                      <p className="text-xs text-stone-600 leading-relaxed mb-3">
                        {room.description || "Designed for quiet comfort with plush linens and contemporary bath amenities."}
                      </p>

                      {/* Room Amenities */}
                      {room.amenities && room.amenities.length > 0 && (
                        <div className="flex flex-wrap gap-1 mb-4">
                          {room.amenities.map((am) => (
                            <span key={am} className="rounded-md bg-stone-100 px-2 py-0.5 text-[10px] font-semibold text-stone-600 flex items-center gap-1">
                              <Check className="w-2.5 h-2.5 text-emerald-600" />
                              <span>{am}</span>
                            </span>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Room Price & Book Action */}
                    <div className="pt-3 border-t border-stone-100 flex items-center justify-between">
                      <div>
                        {roomPrice.isUnavailable ? (
                          <span className="text-xs font-bold text-amber-700">Price unavailable</span>
                        ) : (
                          <div>
                            <span className="text-lg font-black text-stone-900">{roomPrice.formatted}</span>
                            <span className="text-[10px] text-stone-400"> / night</span>
                          </div>
                        )}
                      </div>

                      <a
                        href={hotel.booking_url || `https://www.google.com/travel/hotels/${encodeURIComponent(hotel.destination)}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="rounded-xl border border-stone-300 bg-white px-3 py-1.5 text-xs font-bold text-stone-800 hover:bg-stone-50 flex items-center gap-1 transition-colors"
                      >
                        <span>{roomPrice.isUnavailable ? "Check Rate" : "Book Room"}</span>
                        <ChevronRight className="w-3.5 h-3.5 text-stone-500" />
                      </a>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Property Amenities */}
          {hotel.amenities && hotel.amenities.length > 0 && (
            <div>
              <h2 className="text-lg font-bold text-stone-900 mb-3">Property Amenities & Facilities</h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2.5">
                {hotel.amenities.map((am) => (
                  <div
                    key={am}
                    className="flex items-center gap-2 rounded-xl bg-stone-50 border border-stone-200/70 p-2.5 text-xs font-semibold text-stone-700"
                  >
                    <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                    <span className="line-clamp-1">{am}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Guest Reviews & Rating Highlights */}
          <div>
            <h2 className="text-lg font-bold text-stone-900 mb-3">Guest Ratings & Scores</h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 rounded-2xl bg-stone-50 border border-stone-200/80 mb-4">
              <div>
                <p className="text-xs text-stone-500 font-medium">Cleanliness</p>
                <p className="text-base font-black text-stone-900">4.8 / 5.0</p>
              </div>
              <div>
                <p className="text-xs text-stone-500 font-medium">Location</p>
                <p className="text-base font-black text-stone-900">4.9 / 5.0</p>
              </div>
              <div>
                <p className="text-xs text-stone-500 font-medium">Service & Staff</p>
                <p className="text-base font-black text-stone-900">4.8 / 5.0</p>
              </div>
              <div>
                <p className="text-xs text-stone-500 font-medium">Value for Money</p>
                <p className="text-base font-black text-stone-900">4.7 / 5.0</p>
              </div>
            </div>

            <div className="space-y-2.5">
              <div className="rounded-xl border border-stone-100 p-3 bg-white text-xs text-stone-700 italic">
                “Outstanding stay! The rooms were pristine, beds extremely comfortable, and the staff helped us with every local recommendation.”
                <span className="block mt-1 font-semibold not-italic text-stone-400">— Verified Guest • Recent Traveler</span>
              </div>
              <div className="rounded-xl border border-stone-100 p-3 bg-white text-xs text-stone-700 italic">
                “Prime location right next to transit and walking distance to historic temples. Will definitely return!”
                <span className="block mt-1 font-semibold not-italic text-stone-400">— Verified Guest • Couples Trip</span>
              </div>
            </div>
          </div>

          {/* Location & Map Action */}
          <div className="pt-4 border-t border-stone-100 flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-xs text-stone-500 font-bold uppercase tracking-wider">Property Address</p>
              <p className="text-sm font-semibold text-stone-800 mt-0.5">{hotel.address}</p>
            </div>
            <div className="flex items-center gap-2.5">
              {onAddToTrip && (
                <button
                  type="button"
                  onClick={() => onAddToTrip(hotel)}
                  className="rounded-xl bg-stone-900 px-4 py-2 text-xs font-bold text-white hover:bg-stone-800 flex items-center gap-1.5 transition-colors shadow-xs"
                >
                  <Plus className="w-3.5 h-3.5 text-amber-400" />
                  <span>Add to Trip</span>
                </button>
              )}
              <a
                href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(hotel.name + " " + hotel.address)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-xl border border-stone-300 bg-white px-4 py-2 text-xs font-bold text-stone-800 hover:bg-stone-50 flex items-center gap-1.5 transition-colors shadow-2xs"
              >
                <MapPin className="w-3.5 h-3.5 text-amber-600" />
                <span>Open in Google Maps</span>
                <ExternalLink className="w-3 h-3 text-stone-400" />
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
