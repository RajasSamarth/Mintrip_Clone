"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  X,
  Plus,
  Check,
  Calendar,
  MapPin,
  Bed,
  Plane,
  Utensils,
  ChevronRight,
  Sparkles,
  ExternalLink,
} from "lucide-react";
import { api } from "@/lib/api";
import { formatFlightPriceDisplay, formatPriceInCurrency } from "@/lib/currencies";
import { getDestinationPhoto } from "@/lib/destinations";

export interface AddToTripModalProps {
  isOpen: boolean;
  onClose: () => void;
  itemType: "hotel" | "flight" | "place";
  itemData: any;
  currency?: string;
  onSuccess?: (tripId: string) => void;
}

export function AddToTripModal({
  isOpen,
  onClose,
  itemType,
  itemData,
  currency = "INR",
  onSuccess,
}: AddToTripModalProps) {
  const [trips, setTrips] = useState<any[]>([]);
  const [loadingTrips, setLoadingTrips] = useState(false);
  const [selectedTripId, setSelectedTripId] = useState<string>("");
  const [mode, setMode] = useState<"existing" | "new">("existing");

  // New trip form state
  const [newTitle, setNewTitle] = useState("");
  const [newDestination, setNewDestination] = useState("");
  const [newStartDate, setNewStartDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 14);
    return d.toISOString().split("T")[0];
  });
  const [newDurationDays, setNewDurationDays] = useState(3);
  const [travelerType, setTravelerType] = useState("Solo Traveler");

  // Place/restaurant specific state
  const [selectedDayIndex, setSelectedDayIndex] = useState(1);
  const [timeSlot, setTimeSlot] = useState("evening");

  // Submission state
  const [submitting, setSubmitting] = useState(false);
  const [savedTrip, setSavedTrip] = useState<any | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  // Load trips when modal opens
  useEffect(() => {
    if (!isOpen) {
      setSavedTrip(null);
      setErrorMsg("");
      return;
    }

    async function fetchTrips() {
      setLoadingTrips(true);
      try {
        const res = await api("/trips?limit=50");
        const json = await res.json();
        const list = json?.trips || [];
        setTrips(list);
        if (list.length > 0) {
          setSelectedTripId(list[0].id);
        } else {
          setMode("new");
        }
      } catch (err) {
        console.error("Failed to load user trips:", err);
      } finally {
        setLoadingTrips(false);
      }
    }

    fetchTrips();

    // Pre-populate destination for new trip if available
    const dest =
      itemData?.destination ||
      itemData?.city ||
      (itemType === "flight" ? itemData?.destination : "");
    if (dest) {
      setNewDestination(dest);
      setNewTitle(`Trip to ${dest}`);
    } else {
      setNewTitle("My Next Adventure");
    }
  }, [isOpen, itemData, itemType]);

  if (!isOpen) return null;

  async function handleAttachToTrip(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setErrorMsg("");

    try {
      let targetTripId = selectedTripId;

      // 1. If user chooses to create a new trip on the fly
      if (mode === "new") {
        if (!newTitle.trim() || !newDestination.trim()) {
          setErrorMsg("Please provide a title and destination for your new trip.");
          setSubmitting(false);
          return;
        }

        const days = Array.from({ length: newDurationDays }, (_, i) => ({
          day_index: i + 1,
          title: `Day ${i + 1}`,
          summary: `Exploring ${newDestination}`,
          stops: [],
        }));

        const createRes = await api("/trips", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title: newTitle.trim(),
            destination: newDestination.trim(),
            start_date: newStartDate,
            traveler_type: travelerType,
            cover_photo: getDestinationPhoto(newDestination.trim()),
            days: days,
          }),
        });

        if (!createRes.ok) {
          throw new Error("Failed to create new trip");
        }
        const createdJson = await createRes.json();
        targetTripId = createdJson.id;
      }

      if (!targetTripId) {
        setErrorMsg("Please select or create a trip.");
        setSubmitting(false);
        return;
      }

      // 2. Attach item according to type
      if (itemType === "hotel") {
        const res = await api(`/trips/${targetTripId}/hotel`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            hotel_id: itemData.id,
            hotel_data: itemData,
          }),
        });
        if (!res.ok) throw new Error("Could not attach hotel to trip");
        const updated = await res.json();
        setSavedTrip(updated);
      } else if (itemType === "flight") {
        const activeCurr = currency || itemData?.selected_currency || itemData?.currency || "INR";
        const flightDataWithCurrency = {
          ...itemData,
          selected_currency: activeCurr,
          currency: activeCurr,
        };
        const res = await api(`/trips/${targetTripId}/flight`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            flight_id: itemData.id,
            flight_data: flightDataWithCurrency,
          }),
        });
        if (!res.ok) throw new Error("Could not attach flight to trip");
        const updated = await res.json();
        setSavedTrip(updated);
      } else if (itemType === "place") {
        const res = await api(`/trips/${targetTripId}/stops`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            day_index: selectedDayIndex,
            place_id: itemData.id,
            time_slot: timeSlot,
            notes: `Dining at ${itemData.name}`,
          }),
        });
        if (!res.ok) throw new Error("Could not add restaurant to trip stops");
        const updated = await res.json();
        setSavedTrip(updated);
      }

      if (onSuccess) {
        onSuccess(targetTripId);
      }
    } catch (err: any) {
      console.error("Error attaching to trip:", err);
      setErrorMsg(err.message || "Failed to add to trip. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div
        className="relative w-full max-w-lg rounded-3xl bg-white shadow-2xl border border-stone-200 overflow-hidden text-stone-900"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-stone-100 bg-stone-50/70">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-2xl bg-stone-900 text-white flex items-center justify-center shadow-xs">
              {itemType === "hotel" && <Bed className="w-4 h-4" />}
              {itemType === "flight" && <Plane className="w-4 h-4" />}
              {itemType === "place" && <Utensils className="w-4 h-4" />}
            </div>
            <div>
              <h3 className="text-base font-bold text-stone-900">
                {savedTrip ? "Added to Trip!" : `Add ${itemType.charAt(0).toUpperCase() + itemType.slice(1)} to Trip`}
              </h3>
              <p className="text-xs text-stone-500 line-clamp-1">
                {itemData?.name || itemData?.airline || "Selected item"}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-white border border-stone-200 text-stone-500 hover:text-stone-900 flex items-center justify-center transition-colors shadow-2xs"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        {savedTrip ? (
          <div className="p-6 text-center space-y-4">
            <div className="w-14 h-14 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center mx-auto mb-2 animate-bounce">
              <Check className="w-7 h-7" />
            </div>
            <h4 className="text-lg font-bold text-stone-900">Successfully Added!</h4>
            <p className="text-xs text-stone-600 max-w-sm mx-auto">
              <strong>{itemData?.name || itemData?.airline}</strong> is now linked to your itinerary for{" "}
              <strong>{savedTrip.title}</strong>.
            </p>
            <div className="pt-4 flex items-center justify-center gap-3">
              <Link
                href={`/trip/${savedTrip.id}`}
                className="rounded-2xl bg-stone-900 px-5 py-2.5 text-xs font-bold text-white hover:bg-stone-800 transition-all flex items-center gap-2 shadow-xs"
              >
                <span>View Itinerary</span>
                <ChevronRight className="w-4 h-4" />
              </Link>
              <button
                type="button"
                onClick={onClose}
                className="rounded-2xl border border-stone-200 bg-white px-5 py-2.5 text-xs font-bold text-stone-700 hover:bg-stone-50"
              >
                Done
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleAttachToTrip} className="p-6 space-y-5">
            {/* Item Preview Card */}
            <div className="rounded-2xl border border-stone-200 bg-stone-50/60 p-3.5 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs font-bold text-stone-900 truncate">
                  {itemData?.name || `${itemData?.airline} (${itemData?.flight_number || "Flight"})`}
                </p>
                <p className="text-[11px] text-stone-500 truncate">
                  {itemData?.address || (itemData?.origin && itemData?.destination ? `${itemData.origin} → ${itemData.destination}` : "")}
                </p>
              </div>
              <div className="text-right shrink-0">
                {itemType === "hotel" && itemData?.price_per_night && (
                  <span className="text-xs font-black text-stone-900">
                    {formatPriceInCurrency(itemData.price_per_night, currency || "INR")}/nt
                  </span>
                )}
                {itemType === "flight" && (
                  <span className="text-xs font-black text-stone-900">
                    {formatFlightPriceDisplay(itemData, currency || itemData?.selected_currency || "INR")}
                  </span>
                )}
                {itemData?.rating != null && (
                  <span className="block text-[10px] text-amber-600 font-bold">
                    ★ {typeof itemData.rating === "number" ? itemData.rating.toFixed(1) : itemData.rating}
                  </span>
                )}
              </div>
            </div>

            {/* Mode Tabs */}
            <div className="grid grid-cols-2 gap-1 rounded-2xl bg-stone-100 p-1 text-xs font-bold">
              <button
                type="button"
                onClick={() => setMode("existing")}
                disabled={trips.length === 0}
                className={`py-2 rounded-xl transition-all ${
                  mode === "existing"
                    ? "bg-white text-stone-900 shadow-xs"
                    : "text-stone-500 hover:text-stone-900 disabled:opacity-40"
                }`}
              >
                Existing Trip ({trips.length})
              </button>
              <button
                type="button"
                onClick={() => setMode("new")}
                className={`py-2 rounded-xl transition-all ${
                  mode === "new"
                    ? "bg-white text-stone-900 shadow-xs"
                    : "text-stone-500 hover:text-stone-900"
                }`}
              >
                + New Trip
              </button>
            </div>

            {/* Error banner */}
            {errorMsg && (
              <div className="rounded-xl bg-red-50 border border-red-200 p-2.5 text-xs text-red-700">
                {errorMsg}
              </div>
            )}

            {/* Option A: Select Existing Trip */}
            {mode === "existing" && (
              <div className="space-y-3">
                <label className="block text-xs font-bold text-stone-700">Choose destination itinerary</label>
                {loadingTrips ? (
                  <div className="py-8 text-center text-xs text-stone-400">Loading trips...</div>
                ) : (
                  <div className="space-y-2 max-h-52 overflow-y-auto pr-1">
                    {trips.map((t) => (
                      <label
                        key={t.id}
                        className={`flex items-center justify-between p-3 rounded-2xl border cursor-pointer transition-all ${
                          selectedTripId === t.id
                            ? "border-stone-900 bg-stone-900/5 ring-1 ring-stone-900"
                            : "border-stone-200 bg-white hover:border-stone-300"
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <input
                            type="radio"
                            name="selectedTrip"
                            checked={selectedTripId === t.id}
                            onChange={() => setSelectedTripId(t.id)}
                            className="accent-stone-900 w-4 h-4"
                          />
                          <div>
                            <p className="text-xs font-bold text-stone-900">{t.title}</p>
                            <p className="text-[10px] text-stone-500 flex items-center gap-1.5 mt-0.5">
                              <MapPin className="w-3 h-3" />
                              <span>{t.destination}</span>
                              <span>·</span>
                              <span>{t.day_count || 1} days</span>
                            </p>
                          </div>
                        </div>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Option B: Create New Trip on the fly */}
            {mode === "new" && (
              <div className="space-y-3 text-xs">
                <div>
                  <label className="block font-bold text-stone-700 mb-1">Trip Name</label>
                  <input
                    type="text"
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    required
                    placeholder="e.g. Pune Weekend Culinary Tour"
                    className="w-full rounded-xl border border-stone-200 px-3 py-2 font-medium focus:border-stone-900 focus:outline-hidden"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block font-bold text-stone-700 mb-1">Destination City</label>
                    <input
                      type="text"
                      value={newDestination}
                      onChange={(e) => setNewDestination(e.target.value)}
                      required
                      placeholder="e.g. Pune"
                      className="w-full rounded-xl border border-stone-200 px-3 py-2 font-medium focus:border-stone-900 focus:outline-hidden"
                    />
                  </div>
                  <div>
                    <label className="block font-bold text-stone-700 mb-1">Duration (Days)</label>
                    <input
                      type="number"
                      min={1}
                      max={14}
                      value={newDurationDays}
                      onChange={(e) => setNewDurationDays(Number(e.target.value))}
                      className="w-full rounded-xl border border-stone-200 px-3 py-2 font-medium focus:border-stone-900 focus:outline-hidden"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block font-bold text-stone-700 mb-1">Start Date</label>
                    <input
                      type="date"
                      value={newStartDate}
                      onChange={(e) => setNewStartDate(e.target.value)}
                      className="w-full rounded-xl border border-stone-200 px-3 py-2 font-medium focus:border-stone-900 focus:outline-hidden"
                    />
                  </div>
                  <div>
                    <label className="block font-bold text-stone-700 mb-1">Traveler Type</label>
                    <select
                      value={travelerType}
                      onChange={(e) => setTravelerType(e.target.value)}
                      className="w-full rounded-xl border border-stone-200 px-3 py-2 font-medium focus:border-stone-900 focus:outline-hidden"
                    >
                      <option>Solo Traveler</option>
                      <option>Couple / Romantic</option>
                      <option>Family with Kids</option>
                      <option>Friends Getaway</option>
                    </select>
                  </div>
                </div>
              </div>
            )}

            {/* Restaurant / Place specific Day & Meal selector */}
            {itemType === "place" && (
              <div className="pt-2 border-t border-stone-100 grid grid-cols-2 gap-3 text-xs">
                <div>
                  <label className="block font-bold text-stone-700 mb-1">Itinerary Day</label>
                  <select
                    value={selectedDayIndex}
                    onChange={(e) => setSelectedDayIndex(Number(e.target.value))}
                    className="w-full rounded-xl border border-stone-200 px-3 py-2 font-medium focus:border-stone-900 focus:outline-hidden"
                  >
                    {[1, 2, 3, 4, 5].map((d) => (
                      <option key={d} value={d}>
                        Day {d}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block font-bold text-stone-700 mb-1">Meal / Time Slot</label>
                  <select
                    value={timeSlot}
                    onChange={(e) => setTimeSlot(e.target.value)}
                    className="w-full rounded-xl border border-stone-200 px-3 py-2 font-medium focus:border-stone-900 focus:outline-hidden"
                  >
                    <option value="morning">Breakfast / Morning</option>
                    <option value="afternoon">Lunch / Afternoon</option>
                    <option value="evening">Dinner / Evening</option>
                  </select>
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="pt-3 border-t border-stone-100 flex items-center justify-end gap-2.5">
              <button
                type="button"
                onClick={onClose}
                className="rounded-2xl border border-stone-200 px-4 py-2 text-xs font-bold text-stone-700 hover:bg-stone-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="rounded-2xl bg-stone-900 px-5 py-2 text-xs font-bold text-white hover:bg-stone-800 disabled:opacity-50 transition-all flex items-center gap-1.5 shadow-xs"
              >
                {submitting ? (
                  <span>Saving...</span>
                ) : (
                  <>
                    <Plus className="w-3.5 h-3.5" />
                    <span>Confirm & Add</span>
                  </>
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
