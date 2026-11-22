"use client";

import { useState, useEffect, useMemo, useRef } from "react";
import {
  Search,
  MapPin,
  Clock,
  Plane,
  ArrowLeftRight,
  Calendar,
  Users,
  ExternalLink,
  SlidersHorizontal,
  ChevronDown,
  RotateCcw,
  Plus,
  Trash2,
  Check,
  Leaf,
  AlertCircle,
  X,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import { AddToTripModal } from "@/components/common/AddToTripModal";
import { MultiLegFlightCard } from "@/components/chat/MultiLegFlightCard";

interface Airport {
  code: string;
  city: string;
  name: string;
  country: string;
}

interface ReturnFlight {
  airline: string;
  airline_code?: string;
  flight_number?: string;
  origin: string;
  destination: string;
  departure_time: string;
  arrival_time: string;
  duration_minutes: number;
  stops: number;
  date?: string;
}

interface Flight {
  id: string;
  airline: string;
  airline_code: string;
  flight_number: string;
  origin: string;
  destination: string;
  departure_time: string;
  arrival_time: string;
  duration_minutes: number;
  stops: number;
  price_usd: number;
  price_inr?: number;
  price_per_person_usd?: number;
  price_per_person_inr?: number;
  passengers?: number;
  trip_type?: string;
  return_flight?: ReturnFlight | null;
  cabin: string;
  baggage?: string;
  booking_url?: string;
  source?: string;
  is_top_pick?: boolean;
  emissions?: string;
  emissions_diff_pct?: number;
  self_transfer?: boolean;
  metadata?: Record<string, any>;
}

interface MultiCityLeg {
  id: string;
  origin: string;
  destination: string;
  date: string;
}

interface Currency {
  code: string;
  symbol: string;
  label: string;
  rateFromUSD: number;
}

// Comprehensive currency list with search support
const CURRENCIES: Record<string, Currency> = {
  INR: { code: "INR", symbol: "₹", label: "Indian Rupee", rateFromUSD: 85.0 },
  USD: { code: "USD", symbol: "$", label: "US Dollar", rateFromUSD: 1.0 },
  EUR: { code: "EUR", symbol: "€", label: "Euro", rateFromUSD: 0.92 },
  GBP: { code: "GBP", symbol: "£", label: "British Pound", rateFromUSD: 0.78 },
  AED: { code: "AED", symbol: "AED", label: "United Arab Emirates Dirham", rateFromUSD: 3.67 },
  JPY: { code: "JPY", symbol: "¥", label: "Japanese Yen", rateFromUSD: 152.0 },
  CAD: { code: "CAD", symbol: "CA$", label: "Canadian Dollar", rateFromUSD: 1.39 },
  AUD: { code: "AUD", symbol: "AU$", label: "Australian Dollar", rateFromUSD: 1.52 },
  SGD: { code: "SGD", symbol: "S$", label: "Singapore Dollar", rateFromUSD: 1.33 },
  CHF: { code: "CHF", symbol: "CHF", label: "Swiss Franc", rateFromUSD: 0.88 },
  CNY: { code: "CNY", symbol: "¥", label: "Chinese Yuan", rateFromUSD: 7.23 },
  THB: { code: "THB", symbol: "฿", label: "Thai Baht", rateFromUSD: 34.6 },
  MYR: { code: "MYR", symbol: "RM", label: "Malaysian Ringgit", rateFromUSD: 4.45 },
  IDR: { code: "IDR", symbol: "Rp", label: "Indonesian Rupiah", rateFromUSD: 15850.0 },
  SAR: { code: "SAR", symbol: "SAR", label: "Saudi Riyal", rateFromUSD: 3.75 },
  QAR: { code: "QAR", symbol: "QAR", label: "Qatari Riyal", rateFromUSD: 3.64 },
  KWD: { code: "KWD", symbol: "KD", label: "Kuwaiti Dinar", rateFromUSD: 0.31 },
  BHD: { code: "BHD", symbol: "BD", label: "Bahraini Dinar", rateFromUSD: 0.38 },
  OMR: { code: "OMR", symbol: "OMR", label: "Omani Rial", rateFromUSD: 0.385 },
  NZD: { code: "NZD", symbol: "NZ$", label: "New Zealand Dollar", rateFromUSD: 1.68 },
  ZAR: { code: "ZAR", symbol: "R", label: "South African Rand", rateFromUSD: 17.6 },
  BRL: { code: "BRL", symbol: "R$", label: "Brazilian Real", rateFromUSD: 5.78 },
  MXN: { code: "MXN", symbol: "Mex$", label: "Mexican Peso", rateFromUSD: 20.2 },
  TRY: { code: "TRY", symbol: "₺", label: "Turkish Lira", rateFromUSD: 34.3 },
  KRW: { code: "KRW", symbol: "₩", label: "South Korean Won", rateFromUSD: 1380.0 },
  HKD: { code: "HKD", symbol: "HK$", label: "Hong Kong Dollar", rateFromUSD: 7.78 },
  SEK: { code: "SEK", symbol: "kr", label: "Swedish Krona", rateFromUSD: 10.7 },
  NOK: { code: "NOK", symbol: "kr", label: "Norwegian Krone", rateFromUSD: 10.9 },
  DKK: { code: "DKK", symbol: "kr", label: "Danish Krone", rateFromUSD: 6.87 },
  PLN: { code: "PLN", symbol: "zł", label: "Polish Zloty", rateFromUSD: 4.02 },
  PHP: { code: "PHP", symbol: "₱", label: "Philippine Peso", rateFromUSD: 58.4 },
  VND: { code: "VND", symbol: "₫", label: "Vietnamese Dong", rateFromUSD: 25300.0 },
  EGP: { code: "EGP", symbol: "E£", label: "Egyptian Pound", rateFromUSD: 49.1 },
  ILS: { code: "ILS", symbol: "₪", label: "Israeli New Shekel", rateFromUSD: 3.73 },
  LKR: { code: "LKR", symbol: "Rs", label: "Sri Lankan Rupee", rateFromUSD: 293.0 },
  PKR: { code: "PKR", symbol: "Rs", label: "Pakistani Rupee", rateFromUSD: 278.0 },
  BDT: { code: "BDT", symbol: "৳", label: "Bangladeshi Taka", rateFromUSD: 119.5 },
  NPR: { code: "NPR", symbol: "Rs", label: "Nepalese Rupee", rateFromUSD: 136.0 },
};

const QUICK_ROUTES = [
  { from: "DEL", to: "BOM", label: "Delhi to Mumbai" },
  { from: "BLR", to: "DEL", label: "Bengaluru to Delhi" },
  { from: "SFO", to: "JFK", label: "San Francisco to New York" },
  { from: "LHR", to: "CDG", label: "London to Paris" },
  { from: "LAX", to: "HND", label: "Los Angeles to Tokyo" },
  { from: "DXB", to: "DEL", label: "Dubai to Delhi" },
];

export default function FlightsPage() {
  const [flights, setFlights] = useState<Flight[]>([]);
  const [airports, setAirports] = useState<Airport[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [hasSearched, setHasSearched] = useState(false);
  const [isMounted, setIsMounted] = useState(false);
  const [addToTripFlight, setAddToTripFlight] = useState<Flight | null>(null);

  // Abort in-flight fetch on unmount / new search, and dedupe concurrent searches.
  const abortControllerRef = useRef<AbortController | null>(null);
  const searchInFlightRef = useRef(false);

  useEffect(() => {
    setIsMounted(true);
    return () => {
      // Cancel any in-flight search when the page unmounts so the Next.js dev
      // proxy doesn't hang on a socket the client no longer cares about.
      abortControllerRef.current?.abort();
    };
  }, []);

  function formatNumberWithLocale(num: number, currencyCode: string = selectedCurrency): string {
    if (currencyCode === "INR") {
      return Math.round(num).toLocaleString("en-IN");
    }
    return Math.round(num).toLocaleString("en-US");
  }

  // Currency selection (Default INR ₹ as per requirement) with search
  const [selectedCurrency, setSelectedCurrency] = useState<string>("INR");
  const [showCurrencyMenu, setShowCurrencyMenu] = useState(false);
  const [currencySearch, setCurrencySearch] = useState("");
  const currencyMenuRef = useRef<HTMLDivElement>(null);

  // Search form state - No autofill by default!
  const [tripType, setTripType] = useState<"one-way" | "round-trip" | "multi-city">("one-way");
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [outboundDate, setOutboundDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 14);
    return d.toISOString().split("T")[0];
  });
  const [returnDate, setReturnDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 21);
    return d.toISOString().split("T")[0];
  });

  // Multi-city legs - No autofill
  const [multiCityLegs, setMultiCityLegs] = useState<MultiCityLeg[]>([
    { id: "1", origin: "", destination: "", date: outboundDate },
    { id: "2", origin: "", destination: "", date: returnDate },
  ]);

  // Cabin Class
  const [cabin, setCabin] = useState("Economy");
  const [showCabinMenu, setShowCabinMenu] = useState(false);
  const cabinMenuRef = useRef<HTMLDivElement>(null);

  // Passenger state (Max 9 per PNR rule)
  const [adults, setAdults] = useState(1);
  const [children, setChildren] = useState(0);
  const [infantsSeat, setInfantsSeat] = useState(0);
  const [infantsLap, setInfantsLap] = useState(0);
  const [showPaxMenu, setShowPaxMenu] = useState(false);
  const paxMenuRef = useRef<HTMLDivElement>(null);

  const totalPax = adults + children + infantsSeat + infantsLap;
  const canAddPax = totalPax < 9;

  // Filters state
  const [maxStops, setMaxStops] = useState<string>("all");
  const [selectedAirlines, setSelectedAirlines] = useState<string[]>([]);
  const [carryOnOnly, setCarryOnOnly] = useState(false);
  const [checkedBagOnly, setCheckedBagOnly] = useState(false);
  const [depTimeOfDay, setDepTimeOfDay] = useState<string>("all");
  const [arrTimeOfDay, setArrTimeOfDay] = useState<string>("all");
  const [lowerEmissionsOnly, setLowerEmissionsOnly] = useState(false);
  const [hideSelfTransfer, setHideSelfTransfer] = useState(false);
  const [sortBy, setSortBy] = useState<"price" | "duration" | "departure">("price");

  // Click outside listener for all popovers
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (paxMenuRef.current && !paxMenuRef.current.contains(e.target as Node)) {
        setShowPaxMenu(false);
      }
      if (currencyMenuRef.current && !currencyMenuRef.current.contains(e.target as Node)) {
        setShowCurrencyMenu(false);
      }
      if (cabinMenuRef.current && !cabinMenuRef.current.contains(e.target as Node)) {
        setShowCabinMenu(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Load airports on mount WITHOUT automatically triggering search
  useEffect(() => {
    async function init() {
      try {
        const res = await api("/flights/airports");
        if (res.ok) {
          const json = await res.json();
          setAirports(json.airports || []);
        }
      } catch (e) {
        console.warn("Failed to load airports:", e);
      }
    }
    init();
  }, []);

  // Filtered currencies for dropdown search
  const filteredCurrencies = useMemo(() => {
    const q = currencySearch.trim().toLowerCase();
    if (!q) return Object.values(CURRENCIES);
    return Object.values(CURRENCIES).filter(
      (c) =>
        c.code.toLowerCase().includes(q) ||
        c.label.toLowerCase().includes(q) ||
        c.symbol.toLowerCase().includes(q)
    );
  }, [currencySearch]);

  // Price conversion helper
  function formatPrice(fl: Flight): string {
    const curr = CURRENCIES[selectedCurrency] || CURRENCIES.INR;
    let inr = fl.price_inr;
    let usd = fl.price_usd;

    // Guard against scrape artifacts (e.g. 1 Rs matching '1 stop')
    if ((inr != null && inr > 0 && inr < 500) || (usd != null && usd > 0 && usd < 15)) {
      usd = (fl.stops || 0) === 0 ? 75 : 98;
      inr = usd * 85;
    }

    if (selectedCurrency === "INR" && inr != null && inr > 0) {
      return `${curr.symbol} ${Math.round(inr).toLocaleString("en-IN")}`;
    }
    if (usd != null && usd > 0) {
      if (selectedCurrency === "USD") {
        return `${curr.symbol}${Math.round(usd).toLocaleString("en-US")}`;
      }
      const converted = usd * curr.rateFromUSD;
      return `${curr.symbol} ${Math.round(converted).toLocaleString("en-US")}`;
    }
    if (inr != null && inr > 0) {
      const u = inr / 85.0;
      const converted = u * curr.rateFromUSD;
      return `${curr.symbol} ${Math.round(converted).toLocaleString("en-US")}`;
    }
    return `${curr.symbol} ${Math.round(8500 * (curr.rateFromUSD / 85.0)).toLocaleString("en-US")}`;
  }

  function formatPerPersonPrice(fl: Flight): string {
    const curr = CURRENCIES[selectedCurrency] || CURRENCIES.INR;
    const pax = fl.passengers || totalPax || 1;
    let inr = fl.price_per_person_inr || (fl.price_inr ? fl.price_inr / pax : 0);
    let usd = fl.price_per_person_usd || (fl.price_usd ? fl.price_usd / pax : 0);

    if (selectedCurrency === "INR" && inr > 0) {
      return `${curr.symbol} ${Math.round(inr).toLocaleString("en-IN")}`;
    }
    if (usd > 0) {
      if (selectedCurrency === "USD") {
        return `${curr.symbol}${Math.round(usd).toLocaleString("en-US")}`;
      }
      return `${curr.symbol} ${Math.round(usd * curr.rateFromUSD).toLocaleString("en-US")}`;
    }
    return `${curr.symbol} ${Math.round((8500 / pax) * (curr.rateFromUSD / 85.0)).toLocaleString("en-US")}`;
  }

  function getNumericPriceInSelectedCurrency(fl: Flight): number {
    const rate = CURRENCIES[selectedCurrency]?.rateFromUSD || 85.0;
    if (selectedCurrency === "INR" && fl.price_inr != null && fl.price_inr > 0) {
      return fl.price_inr;
    }
    if (fl.price_usd != null && fl.price_usd > 0) {
      return fl.price_usd * rate;
    }
    if (fl.price_inr != null && fl.price_inr > 0) {
      return (fl.price_inr / 85.0) * rate;
    }
    return 0;
  }

  // Execute Search (Requires explicit user input)
  async function executeSearch(customOrigin?: string, customDest?: string) {
    const o = (customOrigin !== undefined ? customOrigin : origin).trim().toUpperCase();
    const d = (customDest !== undefined ? customDest : destination).trim().toUpperCase();

    if (tripType !== "multi-city" && (!o || !d)) {
      setErrorMsg("Please enter both departure and destination airport codes (e.g. DEL to BOM) to search flights.");
      return;
    }

    if (tripType === "multi-city") {
      const invalid = multiCityLegs.some((l) => !l.origin.trim() || !l.destination.trim());
      if (invalid) {
        setErrorMsg("Please enter origin and destination for all multi-city flight legs.");
        return;
      }
    }

    // Dedupe: ignore if a search is already in flight.
    if (searchInFlightRef.current) {
      return;
    }

    // Abort any previous in-flight request before starting a new one.
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;

    searchInFlightRef.current = true;
    setLoading(true);
    setHasSearched(true);
    setLoadingStatus("Live scraping Google Flights...");
    setErrorMsg("");

    let succeeded = false;
    let lastErr: unknown = null;

    try {
      // Step 1: POST /api/flights/search → get job_id immediately
      const payload: any = {
        cabin,
        adults,
        children,
        infants_seat: infantsSeat,
        infants_lap: infantsLap,
        currency: selectedCurrency,
        live: true,
        trip_type: tripType,
        max_results: 30,
      };

      console.log("[flights] search payload:", {
        origin: o,
        destination: d,
        adults,
        children,
        tripType,
        outboundDate,
        returnDate,
      });

      if (tripType === "multi-city") {
        payload.legs = multiCityLegs.map((l) => ({
          origin: l.origin.trim().toUpperCase(),
          destination: l.destination.trim().toUpperCase(),
          date: l.date,
        }));
        payload.origin = multiCityLegs[0]?.origin || "DEL";
        payload.destination = multiCityLegs[multiCityLegs.length - 1]?.destination || "BOM";
      } else {
        payload.origin = o;
        payload.destination = d;
        payload.outbound_date = outboundDate;
        payload.return_date = tripType === "round-trip" ? returnDate : undefined;
      }

      const resp = await api("/flights/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      if (controller.signal.aborted) {
        setErrorMsg("Search cancelled.");
        searchInFlightRef.current = false;
        abortControllerRef.current = null;
        setLoading(false);
        setLoadingStatus("");
        return;
      }

      const json = await resp.json();
      const jobId = json.job_id;
      if (!jobId) {
        throw new Error("No job_id returned from search API");
      }

      // Step 2: Poll GET /api/flights/search/{job_id} until done
      const POLL_INTERVAL = 3000; // 3 seconds
      // Multi-city searches scrape up to 5 legs sequentially, and a single leg
      // can take ~90s (two 45s attempts when Google shows a recaptcha page).
      // Allow up to ~20 minutes so the UI never gives up before the backend job.
      const MAX_POLLS = 400;
      let pollCount = 0;
      const startedAt = Date.now();

      while (pollCount < MAX_POLLS) {
        if (controller.signal.aborted) {
          setErrorMsg("Search cancelled.");
          searchInFlightRef.current = false;
          abortControllerRef.current = null;
          setLoading(false);
          setLoadingStatus("");
          return;
        }

        await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL));
        pollCount++;

        const statusResp = await api(`/flights/search/${jobId}`, {
          method: "GET",
          signal: controller.signal,
        });

        if (controller.signal.aborted) {
          setErrorMsg("Search cancelled.");
          searchInFlightRef.current = false;
          abortControllerRef.current = null;
          setLoading(false);
          setLoadingStatus("");
          return;
        }

        const statusJson = await statusResp.json();

        if (statusJson.status === "done") {
          const failedLegs: any[] = Array.isArray(statusJson.failed_legs)
            ? statusJson.failed_legs
            : [];

          if (failedLegs.length > 0) {
            // Never show a partial multi-city journey: if any leg has no live
            // results, a complete itinerary cannot be built.
            setFlights([]);
            setErrorMsg(
              `Live Google Flights returned no results for ${failedLegs
                .map((l: any) => `${l.origin} → ${l.destination}`)
                .join(", ")}. A multi-city itinerary needs every leg — retry, or adjust the date/route for that leg.`
            );
          } else if (statusJson.flights && statusJson.flights.length > 0) {
            setFlights(statusJson.flights);
          } else {
            setFlights([]);
            setErrorMsg(
              statusJson.message ||
                `No live flights found for ${payload.origin} → ${payload.destination}. Try another date or route.`
            );
          }
          succeeded = true;
          break;
        }

        if (statusJson.status === "error") {
          setFlights([]);
          setErrorMsg(statusJson.message || "Flight search failed. Please try again.");
          succeeded = true;
          break;
        }

        // status === "pending" - keep polling
        const elapsedSec = Math.round((Date.now() - startedAt) / 1000);
        setLoadingStatus(
          `Live scraping Google Flights... ${elapsedSec}s elapsed`
        );
      }

      if (!succeeded && !controller.signal.aborted) {
        setFlights([]);
        setErrorMsg(
          "Flight search is taking too long. The scrape may still be running — please try again in a moment."
        );
      }
    } catch (err: any) {
      lastErr = err;

      if (controller.signal.aborted) {
        setErrorMsg("Search cancelled.");
        searchInFlightRef.current = false;
        abortControllerRef.current = null;
        setLoading(false);
        setLoadingStatus("");
        return;
      }

      const msg = err?.message ?? "";
      const isConnectionReset =
        msg.includes("ECONNRESET") ||
        msg.includes("socket hang up") ||
        msg.includes("Failed to proxy");

      if (isConnectionReset) {
        setFlights([]);
        setErrorMsg(
          "Connection interrupted. The scrape may still be running. Please try again."
        );
      } else {
        console.warn("Live flight search failed:", err);
        setFlights([]);
        setErrorMsg(
          "Live Google Flights search failed. Please verify the airport codes and try again."
        );
      }
    }

    searchInFlightRef.current = false;
    abortControllerRef.current = null;
    setLoading(false);
    setLoadingStatus("");
  }

  function swapAirports() {
    const temp = origin;
    setOrigin(destination);
    setDestination(temp);
  }

  function selectQuickRoute(from: string, to: string) {
    setOrigin(from);
    setDestination(to);
    executeSearch(from, to);
  }

  // Multi-city leg helpers
  function addMultiCityLeg() {
    if (multiCityLegs.length >= 5) return;
    const lastLeg = multiCityLegs[multiCityLegs.length - 1];
    const d = new Date(lastLeg?.date || new Date());
    d.setDate(d.getDate() + 4);
    setMultiCityLegs([
      ...multiCityLegs,
      {
        id: String(Date.now()),
        origin: lastLeg?.destination || "",
        destination: "",
        date: d.toISOString().split("T")[0],
      },
    ]);
  }

  function removeMultiCityLeg(id: string) {
    if (multiCityLegs.length <= 2) return;
    setMultiCityLegs(multiCityLegs.filter((l) => l.id !== id));
  }

  function updateMultiCityLeg(id: string, field: keyof MultiCityLeg, value: string) {
    setMultiCityLegs(
      multiCityLegs.map((l) => (l.id === id ? { ...l, [field]: value } : l))
    );
  }

  // Distinct airlines in results
  const airlinesList = useMemo(() => {
    const set = new Set<string>();
    flights.forEach((f) => {
      if (f.airline) set.add(f.airline);
    });
    return Array.from(set).sort();
  }, [flights]);

  // Passenger summary text
  const passengerSummary = useMemo(() => {
    const parts = [];
    if (adults > 0) parts.push(`${adults} ${adults === 1 ? "Adult" : "Adults"}`);
    if (children > 0) parts.push(`${children} ${children === 1 ? "Child" : "Children"}`);
    const infantsTotal = infantsSeat + infantsLap;
    if (infantsTotal > 0) parts.push(`${infantsTotal} ${infantsTotal === 1 ? "Infant" : "Infants"}`);
    return parts.join(", ") || "1 Adult";
  }, [adults, children, infantsSeat, infantsLap]);

  // Filter and sort flights
  const filteredFlights = useMemo(() => {
    return flights
      .filter((fl) => {
        if (maxStops === "nonstop" && fl.stops !== 0) return false;
        if (maxStops === "1-stop" && fl.stops > 1) return false;
        if (maxStops === "2-plus" && fl.stops < 2) return false;

        if (selectedAirlines.length > 0 && !selectedAirlines.includes(fl.airline)) {
          return false;
        }

        const bagText = (fl.baggage || "").toLowerCase();
        if (carryOnOnly && !bagText.includes("carry-on")) return false;
        if (checkedBagOnly && !bagText.includes("checked")) return false;

        if (depTimeOfDay !== "all" && fl.departure_time) {
          try {
            const h = new Date(fl.departure_time).getHours();
            if (depTimeOfDay === "morning" && (h < 5 || h >= 12)) return false;
            if (depTimeOfDay === "afternoon" && (h < 12 || h >= 18)) return false;
            if (depTimeOfDay === "evening" && (h < 18 && h >= 5)) return false;
          } catch {}
        }

        if (arrTimeOfDay !== "all" && fl.arrival_time) {
          try {
            const h = new Date(fl.arrival_time).getHours();
            if (arrTimeOfDay === "morning" && (h < 5 || h >= 12)) return false;
            if (arrTimeOfDay === "afternoon" && (h < 12 || h >= 18)) return false;
            if (arrTimeOfDay === "evening" && (h < 18 && h >= 5)) return false;
          } catch {}
        }

        if (lowerEmissionsOnly) {
          const diff = fl.emissions_diff_pct;
          if (diff != null && diff > 0) return false;
          if (!fl.emissions && diff == null) return false;
        }

        if (hideSelfTransfer && fl.self_transfer) return false;

        return true;
      })
      .sort((a, b) => {
        if (sortBy === "price") {
          const priceA = getNumericPriceInSelectedCurrency(a);
          const priceB = getNumericPriceInSelectedCurrency(b);
          if (priceA > 0 && priceB > 0) return priceA - priceB;
          if (priceA > 0) return -1;
          if (priceB > 0) return 1;
          return 0;
        }
        if (sortBy === "duration") return a.duration_minutes - b.duration_minutes;
        if (sortBy === "departure") {
          const timeA = a.departure_time ? new Date(a.departure_time).getTime() : 0;
          const timeB = b.departure_time ? new Date(b.departure_time).getTime() : 0;
          return timeA - timeB;
        }
        return 0;
      });
  }, [
    flights,
    selectedCurrency,
    maxStops,
    selectedAirlines,
    carryOnOnly,
    checkedBagOnly,
    depTimeOfDay,
    arrTimeOfDay,
    lowerEmissionsOnly,
    hideSelfTransfer,
    sortBy,
  ]);

  // Separate Top Picks vs Other Flights
  const topPickFlights = useMemo(() => {
    const explicitlyTagged = filteredFlights.filter((f) => f.is_top_pick);
    if (explicitlyTagged.length > 0) return explicitlyTagged;
    return filteredFlights.slice(0, 4);
  }, [filteredFlights]);

  const otherFlights = useMemo(() => {
    const topIds = new Set(topPickFlights.map((f) => f.id));
    return filteredFlights.filter((f) => !topIds.has(f.id));
  }, [filteredFlights, topPickFlights]);

  function formatFlightTime(isoStr: string) {
    try {
      const d = new Date(isoStr);
      if (isNaN(d.getTime())) return isoStr;
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return isoStr;
    }
  }

  function formatDuration(minutes: number) {
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
  }

  function toggleAirline(airline: string) {
    if (selectedAirlines.includes(airline)) {
      setSelectedAirlines(selectedAirlines.filter((a) => a !== airline));
    } else {
      setSelectedAirlines([...selectedAirlines, airline]);
    }
  }

  return (
    <div className="min-h-screen bg-[#fcfbf9] text-stone-900 pb-24">
      {/* Top Header Bar */}
      <header className="border-b border-stone-200/80 bg-white/90 backdrop-blur-md sticky top-0 z-30 shadow-xs">
        <div className="mx-auto max-w-[1400px] px-4 py-3.5 sm:px-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-stone-900 text-white flex items-center justify-center font-bold shadow-xs">
              <Plane className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-stone-900">Google Flights Search</h1>
              <p className="text-xs text-stone-500">Live prices from Google Flights with real-time scraping</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Currency Selector (Default: INR ₹) with Search Option */}
            <div className="relative" ref={currencyMenuRef}>
              <button
                type="button"
                onClick={() => {
                  setShowCurrencyMenu(!showCurrencyMenu);
                  setCurrencySearch("");
                }}
                className="inline-flex items-center gap-1.5 rounded-full border border-stone-300 bg-white px-3.5 py-1.5 text-xs font-semibold text-stone-800 hover:bg-stone-50 shadow-xs transition-colors"
                title="Select display currency (Default: INR)"
              >
                <span className="w-4 h-4 rounded-full bg-stone-100 flex items-center justify-center text-[10px] font-bold text-stone-800">
                  {CURRENCIES[selectedCurrency]?.symbol || "₹"}
                </span>
                <span>{selectedCurrency}</span>
                <ChevronDown className="w-3 h-3 text-stone-400" />
              </button>

              {showCurrencyMenu && (
                <div className="absolute right-0 mt-2 w-72 rounded-3xl border border-stone-200 bg-white p-3 shadow-2xl z-50">
                  <div className="flex items-center justify-between pb-2 mb-2 border-b border-stone-100">
                    <span className="text-xs font-bold text-stone-900">Select Currency</span>
                    <span className="text-[10px] font-medium text-stone-400">
                      {filteredCurrencies.length} currencies
                    </span>
                  </div>

                  {/* Currency Search Input */}
                  <div className="relative mb-2">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-stone-400 pointer-events-none" />
                    <input
                      type="text"
                      value={currencySearch}
                      onChange={(e) => setCurrencySearch(e.target.value)}
                      placeholder="Search currency (code, name, symbol)..."
                      className="w-full rounded-xl border border-stone-200 bg-stone-50/80 pl-8 pr-7 py-1.5 text-xs text-stone-900 focus:bg-white focus:border-stone-900 focus:outline-none"
                      autoFocus
                    />
                    {currencySearch && (
                      <button
                        type="button"
                        onClick={() => setCurrencySearch("")}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-700"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>

                  <div className="max-h-64 overflow-y-auto space-y-0.5 pr-1">
                    {filteredCurrencies.length === 0 ? (
                      <p className="text-xs text-stone-400 text-center py-4">No matching currencies</p>
                    ) : (
                      filteredCurrencies.map((c) => (
                        <button
                          key={c.code}
                          type="button"
                          onClick={() => {
                            setSelectedCurrency(c.code);
                            setShowCurrencyMenu(false);
                            setCurrencySearch("");
                          }}
                          className={`w-full flex items-center justify-between px-3 py-2 text-xs rounded-xl transition-colors ${
                            selectedCurrency === c.code
                              ? "bg-stone-900 text-white font-semibold"
                              : "text-stone-700 hover:bg-stone-100"
                          }`}
                        >
                          <div className="flex items-center gap-2.5 truncate">
                            <span className="font-bold w-8 text-left shrink-0">{c.symbol}</span>
                            <span className="font-bold text-stone-900 shrink-0">{c.code}</span>
                            <span className={`text-[11px] truncate ${selectedCurrency === c.code ? "text-stone-300" : "text-stone-400"}`}>
                              · {c.label}
                            </span>
                          </div>
                          {selectedCurrency === c.code && <Check className="w-3.5 h-3.5 shrink-0" />}
                        </button>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Reset Button */}
            <button
              onClick={() => {
                setOrigin("");
                setDestination("");
                setFlights([]);
                setHasSearched(false);
                setErrorMsg("");
                setCabin("Economy");
                setMaxStops("all");
                setSelectedAirlines([]);
                setCarryOnOnly(false);
                setCheckedBagOnly(false);
                setDepTimeOfDay("all");
                setArrTimeOfDay("all");
                setLowerEmissionsOnly(false);
                setHideSelfTransfer(false);
              }}
              className="inline-flex items-center gap-1.5 rounded-full border border-stone-200 bg-white px-3 py-1.5 text-xs font-medium text-stone-600 hover:bg-stone-100 transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reset</span>
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-[1400px] px-4 sm:px-6 py-6">
        {/* Main Search Controls Box */}
        <div className="rounded-3xl border border-stone-200/90 bg-white p-5 sm:p-6 shadow-sm mb-6">
          {/* Top Row: Trip Type Pills, Cabin Dropdown, Passenger Popover */}
          <div className="flex flex-wrap items-center justify-between gap-3 pb-4 mb-4 border-b border-stone-100">
            {/* Trip Type Selector */}
            <div className="flex items-center gap-1.5 bg-stone-100 p-1 rounded-full">
              <button
                type="button"
                onClick={() => setTripType("one-way")}
                className={`rounded-full px-3.5 py-1 text-xs font-semibold transition-all ${
                  tripType === "one-way"
                    ? "bg-white text-stone-900 shadow-xs"
                    : "text-stone-600 hover:text-stone-900"
                }`}
              >
                One way
              </button>
              <button
                type="button"
                onClick={() => setTripType("round-trip")}
                className={`rounded-full px-3.5 py-1 text-xs font-semibold transition-all ${
                  tripType === "round-trip"
                    ? "bg-white text-stone-900 shadow-xs"
                    : "text-stone-600 hover:text-stone-900"
                }`}
              >
                Round trip
              </button>
              <button
                type="button"
                onClick={() => setTripType("multi-city")}
                className={`rounded-full px-3.5 py-1 text-xs font-semibold transition-all ${
                  tripType === "multi-city"
                    ? "bg-white text-stone-900 shadow-xs"
                    : "text-stone-600 hover:text-stone-900"
                }`}
              >
                Multi-city
              </button>
            </div>

            <div className="flex items-center gap-3">
              {/* Cabin Class Dropdown */}
              <div className="relative" ref={cabinMenuRef}>
                <button
                  type="button"
                  onClick={() => setShowCabinMenu(!showCabinMenu)}
                  className="inline-flex items-center gap-1.5 rounded-full border border-stone-200 bg-stone-50 px-3.5 py-1.5 text-xs font-medium text-stone-800 hover:bg-stone-100 transition-colors"
                >
                  <span>{cabin}</span>
                  <ChevronDown className="w-3 h-3 text-stone-400" />
                </button>

                {showCabinMenu && (
                  <div className="absolute right-0 mt-2 w-44 rounded-2xl border border-stone-200 bg-white p-1.5 shadow-xl z-50">
                    {["Economy", "Premium", "Business", "First"].map((cls) => (
                      <button
                        key={cls}
                        type="button"
                        onClick={() => {
                          setCabin(cls);
                          setShowCabinMenu(false);
                        }}
                        className={`w-full text-left px-3 py-2 text-xs rounded-xl font-medium transition-colors ${
                          cabin === cls
                            ? "bg-stone-900 text-white font-semibold"
                            : "text-stone-700 hover:bg-stone-100"
                        }`}
                      >
                        {cls === "Premium" ? "Premium economy" : cls}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Passengers Popover (Exact 4 Google Flights categories + 9 PAX PNR LIMIT) */}
              <div className="relative" ref={paxMenuRef}>
                <button
                  type="button"
                  onClick={() => setShowPaxMenu(!showPaxMenu)}
                  className="inline-flex items-center gap-2 rounded-full border border-stone-200 bg-stone-50 px-3.5 py-1.5 text-xs font-medium text-stone-800 hover:bg-stone-100 transition-colors"
                >
                  <Users className="w-3.5 h-3.5 text-stone-500" />
                  <span>{passengerSummary}</span>
                  <ChevronDown className="w-3 h-3 text-stone-400" />
                </button>

                {showPaxMenu && (
                  <div className="absolute right-0 mt-2 w-80 rounded-3xl border border-stone-200 bg-white p-4 shadow-2xl z-50">
                    <div className="flex items-center justify-between pb-2 mb-3 border-b border-stone-100">
                      <div>
                        <span className="text-xs font-bold text-stone-900">Passengers</span>
                        <p className="text-[10px] text-stone-400">Max 9 passengers per PNR booking</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                            totalPax >= 9
                              ? "bg-amber-100 text-amber-800"
                              : "bg-stone-100 text-stone-700"
                          }`}
                        >
                          {totalPax}/9
                        </span>
                        <button
                          type="button"
                          onClick={() => setShowPaxMenu(false)}
                          className="text-stone-400 hover:text-stone-700"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    </div>

                    <div className="space-y-3.5">
                      {/* Adults */}
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-xs font-bold text-stone-900">Adults</p>
                          <p className="text-[11px] text-stone-400">Age 12+</p>
                        </div>
                        <div className="flex items-center gap-2.5">
                          <button
                            type="button"
                            onClick={() => setAdults(Math.max(1, adults - 1))}
                            disabled={adults <= 1 || adults <= infantsLap}
                            className="w-7 h-7 rounded-full border border-stone-200 flex items-center justify-center text-xs font-bold hover:bg-stone-100 disabled:opacity-40 disabled:hover:bg-transparent"
                          >
                            -
                          </button>
                          <span className="text-xs font-bold w-4 text-center">{adults}</span>
                          <button
                            type="button"
                            onClick={() => setAdults(Math.min(9, adults + 1))}
                            disabled={!canAddPax || adults >= 9}
                            className="w-7 h-7 rounded-full border border-stone-200 flex items-center justify-center text-xs font-bold hover:bg-stone-100 disabled:opacity-40"
                          >
                            +
                          </button>
                        </div>
                      </div>

                      {/* Children */}
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-xs font-bold text-stone-900">Children</p>
                          <p className="text-[11px] text-stone-400">Aged 2–11</p>
                        </div>
                        <div className="flex items-center gap-2.5">
                          <button
                            type="button"
                            onClick={() => setChildren(Math.max(0, children - 1))}
                            disabled={children <= 0}
                            className="w-7 h-7 rounded-full border border-stone-200 flex items-center justify-center text-xs font-bold hover:bg-stone-100 disabled:opacity-40 disabled:hover:bg-transparent"
                          >
                            -
                          </button>
                          <span className="text-xs font-bold w-4 text-center">{children}</span>
                          <button
                            type="button"
                            onClick={() => setChildren(Math.min(8, children + 1))}
                            disabled={!canAddPax || children >= 8}
                            className="w-7 h-7 rounded-full border border-stone-200 flex items-center justify-center text-xs font-bold hover:bg-stone-100 disabled:opacity-40"
                          >
                            +
                          </button>
                        </div>
                      </div>

                      {/* Infants in seat */}
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-xs font-bold text-stone-900">Infants</p>
                          <p className="text-[11px] text-stone-400">In seat</p>
                        </div>
                        <div className="flex items-center gap-2.5">
                          <button
                            type="button"
                            onClick={() => setInfantsSeat(Math.max(0, infantsSeat - 1))}
                            disabled={infantsSeat <= 0}
                            className="w-7 h-7 rounded-full border border-stone-200 flex items-center justify-center text-xs font-bold hover:bg-stone-100 disabled:opacity-40 disabled:hover:bg-transparent"
                          >
                            -
                          </button>
                          <span className="text-xs font-bold w-4 text-center">{infantsSeat}</span>
                          <button
                            type="button"
                            onClick={() => setInfantsSeat(Math.min(4, infantsSeat + 1))}
                            disabled={!canAddPax || infantsSeat >= 4}
                            className="w-7 h-7 rounded-full border border-stone-200 flex items-center justify-center text-xs font-bold hover:bg-stone-100 disabled:opacity-40"
                          >
                            +
                          </button>
                        </div>
                      </div>

                      {/* Infants on lap */}
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-xs font-bold text-stone-900">Infants</p>
                          <p className="text-[11px] text-stone-400">On lap</p>
                        </div>
                        <div className="flex items-center gap-2.5">
                          <button
                            type="button"
                            onClick={() => setInfantsLap(Math.max(0, infantsLap - 1))}
                            disabled={infantsLap <= 0}
                            className="w-7 h-7 rounded-full border border-stone-200 flex items-center justify-center text-xs font-bold hover:bg-stone-100 disabled:opacity-40 disabled:hover:bg-transparent"
                          >
                            -
                          </button>
                          <span className="text-xs font-bold w-4 text-center">{infantsLap}</span>
                          <button
                            type="button"
                            onClick={() => setInfantsLap(Math.min(adults, infantsLap + 1))}
                            disabled={!canAddPax || infantsLap >= adults}
                            className="w-7 h-7 rounded-full border border-stone-200 flex items-center justify-center text-xs font-bold hover:bg-stone-100 disabled:opacity-40"
                          >
                            +
                          </button>
                        </div>
                      </div>
                    </div>

                    {totalPax >= 9 && (
                      <div className="mt-3 p-2 rounded-xl bg-amber-50 border border-amber-200/60 text-[11px] text-amber-800 flex items-center gap-1.5">
                        <AlertCircle className="w-3.5 h-3.5 shrink-0 text-amber-600" />
                        <span>Maximum PNR limit reached: Airlines allow max 9 passengers per booking.</span>
                      </div>
                    )}

                    <div className="mt-4 pt-3 border-t border-stone-100 flex justify-end">
                      <button
                        type="button"
                        onClick={() => setShowPaxMenu(false)}
                        className="rounded-xl bg-stone-900 px-4 py-1.5 text-xs font-semibold text-white hover:bg-stone-800"
                      >
                        Done
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Search Inputs: Single Leg / Round Trip VS Multi-City Builder */}
          {tripType !== "multi-city" ? (
            <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr_auto_auto_auto] gap-3 items-end">
              {/* Origin - No autofill */}
              <div className="relative">
                <label className="block text-[11px] font-semibold uppercase tracking-wider text-stone-500 mb-1">
                  Where from?
                </label>
                <div className="relative flex items-center">
                  <MapPin className="absolute left-3 w-4 h-4 text-stone-400 pointer-events-none" />
                  <input
                    list="airports-origin"
                    value={origin}
                    onChange={(e) => setOrigin(e.target.value.toUpperCase())}
                    placeholder="Enter city or airport (e.g. DEL, SFO)"
                    className="w-full rounded-2xl border border-stone-200 bg-stone-50/50 pl-9 pr-3 py-2.5 text-sm font-semibold text-stone-900 uppercase focus:bg-white focus:border-stone-900 focus:outline-none"
                  />
                  <datalist id="airports-origin">
                    {airports.map((a) => (
                      <option key={`orig-${a.code}`} value={a.code}>
                        {a.city} ({a.name})
                      </option>
                    ))}
                  </datalist>
                </div>
              </div>

              {/* Swap Button */}
              <div className="flex items-center justify-center pb-1">
                <button
                  type="button"
                  onClick={swapAirports}
                  className="w-10 h-10 rounded-full border border-stone-200 bg-stone-50 flex items-center justify-center text-stone-600 hover:bg-stone-100 hover:text-stone-900 transition-colors"
                  title="Swap departure and arrival airports"
                >
                  <ArrowLeftRight className="w-4 h-4" />
                </button>
              </div>

              {/* Destination - No autofill */}
              <div className="relative">
                <label className="block text-[11px] font-semibold uppercase tracking-wider text-stone-500 mb-1">
                  Where to?
                </label>
                <div className="relative flex items-center">
                  <MapPin className="absolute left-3 w-4 h-4 text-stone-400 pointer-events-none" />
                  <input
                    list="airports-dest"
                    value={destination}
                    onChange={(e) => setDestination(e.target.value.toUpperCase())}
                    placeholder="Enter city or airport (e.g. BOM, JFK)"
                    className="w-full rounded-2xl border border-stone-200 bg-stone-50/50 pl-9 pr-3 py-2.5 text-sm font-semibold text-stone-900 uppercase focus:bg-white focus:border-stone-900 focus:outline-none"
                  />
                  <datalist id="airports-dest">
                    {airports.map((a) => (
                      <option key={`dest-${a.code}`} value={a.code}>
                        {a.city} ({a.name})
                      </option>
                    ))}
                  </datalist>
                </div>
              </div>

              {/* Departure Date */}
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wider text-stone-500 mb-1">
                  Departure Date
                </label>
                <div className="relative flex items-center">
                  <Calendar className="absolute left-3 w-4 h-4 text-stone-400 pointer-events-none" />
                  <input
                    type="date"
                    value={outboundDate}
                    onChange={(e) => setOutboundDate(e.target.value)}
                    className="w-full rounded-2xl border border-stone-200 bg-stone-50/50 pl-9 pr-3 py-2.5 text-xs font-semibold text-stone-800 focus:bg-white focus:border-stone-900 focus:outline-none"
                  />
                </div>
              </div>

              {/* Return Date (if round-trip) */}
              {tripType === "round-trip" && (
                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-wider text-stone-500 mb-1">
                    Return Date
                  </label>
                  <div className="relative flex items-center">
                    <Calendar className="absolute left-3 w-4 h-4 text-stone-400 pointer-events-none" />
                    <input
                      type="date"
                      value={returnDate}
                      onChange={(e) => setReturnDate(e.target.value)}
                      className="w-full rounded-2xl border border-stone-200 bg-stone-50/50 pl-9 pr-3 py-2.5 text-xs font-semibold text-stone-800 focus:bg-white focus:border-stone-900 focus:outline-none"
                    />
                  </div>
                </div>
              )}

              {/* Explicit Search Flights Button */}
              <div>
                <button
                  type="button"
                  onClick={() => executeSearch()}
                  disabled={loading}
                  className="w-full md:w-auto h-11 px-6 rounded-2xl bg-stone-900 text-white font-semibold text-sm hover:bg-stone-800 active:scale-98 transition-all flex items-center justify-center gap-2 shadow-sm disabled:opacity-50"
                >
                  {loading ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      <span>Searching...</span>
                    </>
                  ) : (
                    <>
                      <Search className="w-4 h-4" />
                      <span>Search Flights</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          ) : (
            /* Multi-city Trip Builder */
            <div className="space-y-3">
              {multiCityLegs.map((leg, index) => (
                <div
                  key={leg.id}
                  className="grid grid-cols-1 md:grid-cols-[auto_1fr_1fr_1fr_auto] gap-3 items-center p-3 rounded-2xl border border-stone-100 bg-stone-50/60"
                >
                  <span className="w-6 h-6 rounded-full bg-stone-200 text-stone-800 text-[11px] font-bold flex items-center justify-center">
                    {index + 1}
                  </span>

                  {/* Leg Origin */}
                  <div className="relative">
                    <label className="block text-[10px] font-semibold uppercase tracking-wider text-stone-400 mb-0.5">
                      From
                    </label>
                    <input
                      value={leg.origin}
                      onChange={(e) => updateMultiCityLeg(leg.id, "origin", e.target.value.toUpperCase())}
                      placeholder="Origin (e.g. DEL)"
                      className="w-full rounded-xl border border-stone-200 bg-white px-3 py-2 text-xs font-semibold uppercase focus:border-stone-900 focus:outline-none"
                    />
                  </div>

                  {/* Leg Destination */}
                  <div className="relative">
                    <label className="block text-[10px] font-semibold uppercase tracking-wider text-stone-400 mb-0.5">
                      To
                    </label>
                    <input
                      value={leg.destination}
                      onChange={(e) => updateMultiCityLeg(leg.id, "destination", e.target.value.toUpperCase())}
                      placeholder="Destination (e.g. BOM)"
                      className="w-full rounded-xl border border-stone-200 bg-white px-3 py-2 text-xs font-semibold uppercase focus:border-stone-900 focus:outline-none"
                    />
                  </div>

                  {/* Leg Date */}
                  <div>
                    <label className="block text-[10px] font-semibold uppercase tracking-wider text-stone-400 mb-0.5">
                      Date
                    </label>
                    <input
                      type="date"
                      value={leg.date}
                      onChange={(e) => updateMultiCityLeg(leg.id, "date", e.target.value)}
                      className="w-full rounded-xl border border-stone-200 bg-white px-3 py-2 text-xs font-semibold focus:border-stone-900 focus:outline-none"
                    />
                  </div>

                  {/* Remove Leg button */}
                  <div className="flex items-center justify-center pt-3">
                    <button
                      type="button"
                      onClick={() => removeMultiCityLeg(leg.id)}
                      disabled={multiCityLegs.length <= 2}
                      className="w-8 h-8 rounded-full border border-stone-200 bg-white text-stone-400 hover:text-rose-600 hover:border-rose-300 flex items-center justify-center disabled:opacity-30 disabled:hover:text-stone-400 transition-colors"
                      title="Remove this flight leg"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}

              <div className="flex items-center justify-between pt-2">
                <button
                  type="button"
                  onClick={addMultiCityLeg}
                  disabled={multiCityLegs.length >= 5}
                  className="inline-flex items-center gap-1.5 rounded-2xl border border-stone-300 bg-white px-4 py-2 text-xs font-semibold text-stone-800 hover:bg-stone-50 disabled:opacity-40 transition-colors shadow-xs"
                >
                  <Plus className="w-4 h-4 text-stone-600" />
                  <span>Add Flight Leg</span>
                </button>

                <button
                  type="button"
                  onClick={() => executeSearch()}
                  disabled={loading}
                  className="h-11 px-6 rounded-2xl bg-stone-900 text-white font-semibold text-sm hover:bg-stone-800 active:scale-98 transition-all flex items-center justify-center gap-2 shadow-sm disabled:opacity-50"
                >
                  {loading ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      <span>Searching...</span>
                    </>
                  ) : (
                    <>
                      <Search className="w-4 h-4" />
                      <span>Search Multi-City</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* Popular Route Shortcuts */}
          {tripType !== "multi-city" && (
            <div className="mt-4 pt-3 border-t border-stone-100 flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-stone-400 mr-1">
                Popular Routes:
              </span>
              {QUICK_ROUTES.map((qr) => (
                <button
                  key={`${qr.from}-${qr.to}`}
                  type="button"
                  onClick={() => selectQuickRoute(qr.from, qr.to)}
                  className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                    origin === qr.from && destination === qr.to
                      ? "border-stone-900 bg-stone-900 text-white"
                      : "border-stone-200 bg-white text-stone-600 hover:border-stone-300 hover:bg-stone-50"
                  }`}
                >
                  {qr.from} → {qr.to}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Results Section: Flights Left + Filters Sidebar Right */}
        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          {/* Main Flight Cards Column */}
          <main>
            {/* Header / Summary Bar */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
              <div>
                <h2 className="text-xl font-bold text-stone-900">
                  {loading
                    ? (loadingStatus || "Searching for flights...")
                    : hasSearched
                    ? `${filteredFlights.length} Flights Available`
                    : "Find Flights Worldwide"}
                </h2>
                <p className="text-xs text-stone-500 mt-0.5">
                  {hasSearched
                    ? tripType === "multi-city"
                      ? "Multi-city journey"
                      : `${origin} to ${destination} · ${cabin} class · ${passengerSummary}`
                    : "Enter departure & destination airports above to search live flights"}
                </p>
              </div>

              {/* Sort Pills (Visible once searched) */}
              {hasSearched && (
                <div className="flex items-center gap-1.5 bg-stone-100 p-1 rounded-2xl self-start sm:self-auto">
                  <button
                    type="button"
                    onClick={() => setSortBy("price")}
                    className={`px-3 py-1 rounded-xl text-xs font-semibold transition-colors ${
                      sortBy === "price"
                        ? "bg-white text-stone-900 shadow-xs"
                        : "text-stone-600 hover:text-stone-900"
                    }`}
                  >
                    Cheapest
                  </button>
                  <button
                    type="button"
                    onClick={() => setSortBy("duration")}
                    className={`px-3 py-1 rounded-xl text-xs font-semibold transition-colors ${
                      sortBy === "duration"
                        ? "bg-white text-stone-900 shadow-xs"
                        : "text-stone-600 hover:text-stone-900"
                    }`}
                  >
                    Fastest
                  </button>
                  <button
                    type="button"
                    onClick={() => setSortBy("departure")}
                    className={`px-3 py-1 rounded-xl text-xs font-semibold transition-colors ${
                      sortBy === "departure"
                        ? "bg-white text-stone-900 shadow-xs"
                        : "text-stone-600 hover:text-stone-900"
                    }`}
                  >
                    Departure
                  </button>
                </div>
              )}
            </div>

            {errorMsg && (
              <div className="mb-4 rounded-2xl bg-amber-50 border border-amber-200 p-4 text-xs text-amber-800 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            {loading ? (
              <div className="space-y-4">
                {[1, 2, 3, 4, 5].map((n) => (
                  <div
                    key={n}
                    className="h-36 rounded-3xl border border-stone-200 bg-white p-5 animate-pulse flex flex-col justify-between"
                  >
                    <div className="h-4 bg-stone-200 rounded w-1/4" />
                    <div className="h-8 bg-stone-100 rounded w-full" />
                    <div className="h-4 bg-stone-200 rounded w-1/3" />
                  </div>
                ))}
              </div>
            ) : !hasSearched ? (
              /* Initial Clean Landing State (No automatic search) */
              <div className="rounded-3xl border border-stone-200 bg-white py-14 px-6 text-center shadow-xs">
                <div className="w-16 h-16 rounded-3xl bg-lime-400/20 text-stone-900 mx-auto flex items-center justify-center mb-4">
                  <Plane className="w-8 h-8 text-stone-900" />
                </div>
                <h3 className="text-xl font-bold text-stone-900">Find and compare cheap flights</h3>
                <p className="text-xs text-stone-500 mt-1.5 max-w-md mx-auto">
                  Enter your origin and destination airports above, or click any popular route below to freshly scrape real-time prices from Google Flights.
                </p>

                <div className="mt-6 flex flex-wrap justify-center gap-2 max-w-xl mx-auto">
                  {QUICK_ROUTES.map((qr) => (
                    <button
                      key={`landing-${qr.from}-${qr.to}`}
                      type="button"
                      onClick={() => selectQuickRoute(qr.from, qr.to)}
                      className="rounded-2xl border border-stone-200 bg-stone-50 hover:bg-stone-900 hover:text-white hover:border-stone-900 px-3.5 py-2 text-xs font-semibold text-stone-700 transition-all flex items-center gap-1.5 shadow-2xs"
                    >
                      <span>{qr.from} → {qr.to}</span>
                      <span className="text-[10px] text-stone-400 group-hover:text-white/70">· {qr.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            ) : filteredFlights.length === 0 ? (
              <div className="rounded-3xl border border-stone-200 bg-white py-16 px-6 text-center shadow-xs">
                <div className="w-14 h-14 rounded-full bg-stone-100 text-stone-400 mx-auto flex items-center justify-center mb-3">
                  <Plane className="w-6 h-6" />
                </div>
                <h3 className="text-base font-bold text-stone-900">
                  {errorMsg ? "No complete live itinerary found" : "No flights match your filters"}
                </h3>
                <p className="text-xs text-stone-500 mt-1 max-w-sm mx-auto">
                  {errorMsg
                    ? "See the message above for which leg or route returned no live results."
                    : "Try adjusting your stops, airline, or price ceiling filter."}
                </p>
                <button
                  onClick={() => executeSearch()}
                  className="mt-4 inline-flex items-center gap-2 rounded-2xl bg-stone-900 px-4 py-2 text-xs font-semibold text-white hover:bg-stone-800"
                >
                  <Search className="w-3.5 h-3.5" /> Re-run Search
                </button>
              </div>
            ) : (
              <div className="space-y-8">
                {(() => {
                  const isMultiCity =
                    tripType === "multi-city" ||
                    new Set(
                      flights.map((f) => Number(f.metadata?.leg_index ?? 0))
                    ).size > 1;

                  // ---------- Standard one-way / round-trip layout ----------
                  if (!isMultiCity) {
                    return (
                      <>
                        {topPickFlights.length > 0 && (
                          <div>
                            <div className="flex items-center gap-2 mb-3">
                              <Sparkles className="w-4 h-4 text-amber-500" />
                              <h3 className="text-sm font-bold uppercase tracking-wider text-stone-900">
                                Top picks · Best departing flights
                              </h3>
                              <span className="text-[11px] text-stone-400 font-normal">
                                (Ranked based on price, comfort, and duration)
                              </span>
                            </div>
                            <div className="space-y-3">
                              {topPickFlights.map((flight, idx) => (
                                <FlightCard
                                  key={`top-${flight.id || idx}`}
                                  flight={flight}
                                  formatPrice={formatPrice}
                                  formatPerPersonPrice={formatPerPersonPrice}
                                  formatFlightTime={formatFlightTime}
                                  formatDuration={formatDuration}
                                  isTopPickSection
                                  passengersCount={totalPax}
                                  isRoundTrip={tripType === "round-trip"}
                                  onAddToTrip={(f) => setAddToTripFlight(f)}
                                />
                              ))}
                            </div>
                          </div>
                        )}

                        {otherFlights.length > 0 && (
                          <div>
                            <div className="flex items-center gap-2 mb-3 pt-2">
                              <h3 className="text-sm font-bold uppercase tracking-wider text-stone-700">
                                Other departing flights ({otherFlights.length})
                              </h3>
                            </div>
                            <div className="space-y-3">
                              {otherFlights.map((flight, idx) => (
                                <FlightCard
                                  key={`other-${flight.id || idx}`}
                                  flight={flight}
                                  formatPrice={formatPrice}
                                  formatPerPersonPrice={formatPerPersonPrice}
                                  formatFlightTime={formatFlightTime}
                                  formatDuration={formatDuration}
                                  isTopPickSection={false}
                                  passengersCount={totalPax}
                                  isRoundTrip={tripType === "round-trip"}
                                  onAddToTrip={(f) => setAddToTripFlight(f)}
                                />
                              ))}
                            </div>
                          </div>
                        )}
                      </>
                    );
                  }

                  // ---------- Multi-city: bundle one flight per leg ----------
                  const groupByLeg = (list: Flight[]) => {
                    const groups: Record<number, Flight[]> = {};
                    list.forEach((f) => {
                      const idx = Number(f.metadata?.leg_index ?? 0);
                      if (!groups[idx]) groups[idx] = [];
                      groups[idx].push(f);
                    });
                    return Object.keys(groups)
                      .map(Number)
                      .sort((a, b) => a - b)
                      .map((k) => groups[k]);
                  };

                  const itineraryPrice = (itinerary: Flight[]) =>
                    itinerary.reduce(
                      (sum, f) => sum + getNumericPriceInSelectedCurrency(f),
                      0
                    );

                  const buildItineraries = (list: Flight[]) => {
                    const legs = groupByLeg(list);
                    if (legs.length === 0) return [] as Flight[][];
                    const count = Math.max(...legs.map((l) => l.length));
                    const out: Flight[][] = [];
                    for (let i = 0; i < count; i++) {
                      out.push(legs.map((l) => l[i % l.length]));
                    }
                    out.sort((a, b) => itineraryPrice(a) - itineraryPrice(b));
                    return out;
                  };

                  const expectedLegCount = new Set(
                    flights.map((f) => Number(f.metadata?.leg_index ?? 0))
                  ).size;
                  const filteredLegCount = groupByLeg(filteredFlights).length;
                  const incompleteLegs =
                    expectedLegCount > 1 && filteredLegCount < expectedLegCount;

                  const allItineraries = incompleteLegs
                    ? []
                    : buildItineraries(filteredFlights);
                  const topItineraries = allItineraries.slice(0, 3);
                  const restItineraries = allItineraries.slice(3);

                  return (
                    <>
                      {incompleteLegs && (
                        <div className="rounded-2xl bg-amber-50 border border-amber-200 p-4 text-xs text-amber-800 flex items-start gap-2">
                          <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                          <span>
                            Your filters removed every flight for one or more
                            legs, so no complete multi-city itinerary can be
                            shown. Clear a filter to see full journeys.
                          </span>
                        </div>
                      )}
                      {topItineraries.length > 0 && (
                        <div>
                          <div className="flex items-center gap-2 mb-3">
                            <Sparkles className="w-4 h-4 text-amber-500" />
                            <h3 className="text-sm font-bold uppercase tracking-wider text-stone-900">
                              Top picks · Best multi-city itineraries
                            </h3>
                            <span className="text-[11px] text-stone-400 font-normal">
                              (Complete journeys ranked by total price)
                            </span>
                          </div>
                          <div className="space-y-3">
                            {topItineraries.map((itinerary, idx) => (
                              <MultiLegFlightCard
                                key={`top-multi-${idx}`}
                                flights={itinerary}
                                formatPrice={formatPrice}
                                formatFlightTime={formatFlightTime}
                                formatDuration={formatDuration}
                                passengersCount={totalPax}
                                isRoundTrip={tripType === "round-trip"}
                                isTopPick
                                onAddToTrip={(f) => setAddToTripFlight(f)}
                              />
                            ))}
                          </div>
                        </div>
                      )}

                      {restItineraries.length > 0 && (
                        <div>
                          <div className="flex items-center gap-2 mb-3 pt-2">
                            <h3 className="text-sm font-bold uppercase tracking-wider text-stone-700">
                              Other multi-city itineraries ({restItineraries.length})
                            </h3>
                          </div>
                          <div className="space-y-3">
                            {restItineraries.map((itinerary, idx) => (
                              <MultiLegFlightCard
                                key={`other-multi-${idx}`}
                                flights={itinerary}
                                formatPrice={formatPrice}
                                formatFlightTime={formatFlightTime}
                                formatDuration={formatDuration}
                                passengersCount={totalPax}
                                isRoundTrip={tripType === "round-trip"}
                                onAddToTrip={(f) => setAddToTripFlight(f)}
                              />
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  );
                })()}
              </div>
            )}
          </main>

          {/* Right Filters Sidebar */}
          <aside className="space-y-5">
            <div className="rounded-3xl border border-stone-200 bg-white p-5 shadow-xs sticky top-20 max-h-[calc(100vh-6rem)] overflow-y-auto">
              <div className="flex items-center justify-between pb-3 mb-4 border-b border-stone-100">
                <div className="flex items-center gap-2">
                  <SlidersHorizontal className="w-4 h-4 text-stone-700" />
                  <h3 className="text-xs font-bold uppercase tracking-wider text-stone-900">Filters</h3>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setMaxStops("all");
                    setSelectedAirlines([]);
                    setCarryOnOnly(false);
                    setCheckedBagOnly(false);
                    setDepTimeOfDay("all");
                    setArrTimeOfDay("all");
                    setLowerEmissionsOnly(false);
                    setHideSelfTransfer(false);
                  }}
                  className="text-[11px] font-semibold text-stone-500 hover:text-stone-900"
                >
                  Clear all
                </button>
              </div>

              {/* 1. Stops Filter */}
              <div className="mb-5 pb-4 border-b border-stone-100">
                <label className="block text-xs font-bold text-stone-900 mb-2.5">Stops</label>
                <div className="space-y-2">
                  {[
                    { id: "all", label: "Any number of stops" },
                    { id: "nonstop", label: "Nonstop only" },
                    { id: "1-stop", label: "1 stop or fewer" },
                    { id: "2-plus", label: "2+ stops" },
                  ].map((opt) => (
                    <label key={opt.id} className="flex items-center gap-2.5 text-xs text-stone-700 cursor-pointer">
                      <input
                        type="radio"
                        name="stops"
                        checked={maxStops === opt.id}
                        onChange={() => setMaxStops(opt.id)}
                        className="accent-stone-900"
                      />
                      <span>{opt.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* 2. Airlines Multi-Select */}
              {airlinesList.length > 0 && (
                <div className="mb-5 pb-4 border-b border-stone-100">
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-xs font-bold text-stone-900">Airlines</label>
                    {selectedAirlines.length > 0 && (
                      <button
                        type="button"
                        onClick={() => setSelectedAirlines([])}
                        className="text-[10px] text-stone-400 hover:text-stone-700 font-semibold"
                      >
                        Reset
                      </button>
                    )}
                  </div>
                  <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
                    {airlinesList.map((airline) => (
                      <label key={airline} className="flex items-center gap-2.5 text-xs text-stone-700 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={selectedAirlines.includes(airline)}
                          onChange={() => toggleAirline(airline)}
                          className="rounded border-stone-300 accent-stone-900"
                        />
                        <span className="truncate">{airline}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {/* 3. Bags Included */}
              <div className="mb-5 pb-4 border-b border-stone-100">
                <label className="block text-xs font-bold text-stone-900 mb-2">Baggage</label>
                <div className="space-y-2 text-xs text-stone-700">
                  <label className="flex items-center gap-2.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={carryOnOnly}
                      onChange={(e) => setCarryOnOnly(e.target.checked)}
                      className="rounded accent-stone-900"
                    />
                    <span>Carry-on bag included</span>
                  </label>
                  <label className="flex items-center gap-2.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={checkedBagOnly}
                      onChange={(e) => setCheckedBagOnly(e.target.checked)}
                      className="rounded accent-stone-900"
                    />
                    <span>Checked bag included</span>
                  </label>
                </div>
              </div>

              {/* 5. Times (Departure Time of Day) */}
              <div className="mb-5 pb-4 border-b border-stone-100">
                <label className="block text-xs font-bold text-stone-900 mb-2">Departure Times</label>
                <div className="grid grid-cols-2 gap-1.5">
                  {[
                    { id: "all", label: "Any time" },
                    { id: "morning", label: "Morning (5a–12p)" },
                    { id: "afternoon", label: "Afternoon (12p–6p)" },
                    { id: "evening", label: "Evening (6p–12a)" },
                  ].map((t) => (
                    <button
                      key={t.id}
                      type="button"
                      onClick={() => setDepTimeOfDay(t.id)}
                      className={`px-2.5 py-1.5 rounded-xl text-[11px] font-semibold border transition-all ${
                        depTimeOfDay === t.id
                          ? "bg-stone-900 text-white border-stone-900 shadow-xs"
                          : "bg-stone-50 text-stone-700 border-stone-200 hover:bg-stone-100"
                      }`}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* 6. Emissions */}
              <div className="mb-5 pb-4 border-b border-stone-100">
                <label className="block text-xs font-bold text-stone-900 mb-2">Emissions</label>
                <label className="flex items-center gap-2.5 text-xs text-stone-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={lowerEmissionsOnly}
                    onChange={(e) => setLowerEmissionsOnly(e.target.checked)}
                    className="rounded accent-stone-900"
                  />
                  <div className="flex items-center gap-1.5">
                    <Leaf className="w-3.5 h-3.5 text-emerald-600" />
                    <span>Only lower emissions flights</span>
                  </div>
                </label>
              </div>

              {/* 8. Separate & Self-Transfer Tickets */}
              <div>
                <label className="block text-xs font-bold text-stone-900 mb-2">Connecting Tickets</label>
                <label className="flex items-center gap-2.5 text-xs text-stone-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={hideSelfTransfer}
                    onChange={(e) => setHideSelfTransfer(e.target.checked)}
                    className="rounded accent-stone-900"
                  />
                  <span>Hide separate & self-transfer tickets</span>
                </label>
              </div>
            </div>
          </aside>
        </div>
      </div>

      {/* Add To Trip Modal */}
      <AddToTripModal
        isOpen={Boolean(addToTripFlight)}
        onClose={() => setAddToTripFlight(null)}
        itemType="flight"
        itemData={addToTripFlight}
        currency={selectedCurrency}
      />
    </div>
  );
}

// Subcomponent: Flight Card
function FlightCard({
  flight,
  formatPrice,
  formatPerPersonPrice,
  formatFlightTime,
  formatDuration,
  isTopPickSection,
  passengersCount = 1,
  isRoundTrip = false,
  onAddToTrip,
}: {
  flight: Flight;
  formatPrice: (f: Flight) => string;
  formatPerPersonPrice: (f: Flight) => string;
  formatFlightTime: (s: string) => string;
  formatDuration: (m: number) => string;
  isTopPickSection: boolean;
  passengersCount?: number;
  isRoundTrip?: boolean;
  onAddToTrip?: (f: Flight) => void;
}) {
  const isLowerEmissions =
    (flight.emissions_diff_pct != null && flight.emissions_diff_pct < 0) ||
    (flight.emissions || "").includes("-");

  const returnLeg = flight.return_flight || flight.metadata?.return_flight;
  const showReturn = Boolean(isRoundTrip || returnLeg);
  const pax = flight.passengers || passengersCount || 1;

  return (
    <article
      className={`group rounded-3xl border bg-white p-5 transition-all shadow-xs hover:shadow-md ${
        isTopPickSection
          ? "border-amber-200/80 ring-1 ring-amber-100/60 hover:border-amber-300"
          : "border-stone-200/90 hover:border-stone-300"
      }`}
    >
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        {/* Left & Center: Flight Schedules (Stacked for round-trip) */}
        <div className="flex-1 space-y-4">
          {/* Outbound Leg */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center gap-3.5 min-w-[190px]">
              <div className="w-11 h-11 rounded-2xl bg-stone-100 border border-stone-200 flex items-center justify-center text-xs font-black text-stone-800 shrink-0">
                {flight.airline_code || flight.airline.slice(0, 2).toUpperCase()}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-bold text-stone-900 leading-tight">
                    {flight.airline}
                  </h4>
                  {showReturn ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-sky-50 border border-sky-200 px-2 py-0.5 text-[9px] font-bold text-sky-800 uppercase tracking-wider">
                      Outbound
                    </span>
                  ) : isTopPickSection ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 border border-amber-200/60 px-2 py-0.5 text-[10px] font-bold text-amber-800">
                      <Sparkles className="w-2.5 h-2.5 text-amber-600" />
                      Top pick
                    </span>
                  ) : null}
                </div>
                <p className="text-[11px] text-stone-500 mt-0.5 flex items-center gap-1.5 flex-wrap">
                  <span>{flight.flight_number || "Flight"}</span>
                  <span>·</span>
                  <span className="text-stone-700 font-medium">{flight.cabin}</span>
                  {flight.self_transfer && (
                    <>
                      <span>·</span>
                      <span className="text-amber-700 font-semibold bg-amber-50 px-1.5 py-0.5 rounded text-[10px]">
                        Self-transfer
                      </span>
                    </>
                  )}
                </p>
              </div>
            </div>

            {/* Timeline Graphic */}
            <div className="flex-1 grid grid-cols-[auto_1fr_auto] items-center gap-3 px-2 max-w-sm">
              <div className="text-left">
                <p className="text-base font-black text-stone-900 tracking-tight">
                  {formatFlightTime(flight.departure_time)}
                </p>
                <p className="text-xs font-semibold text-stone-500">{flight.origin}</p>
              </div>

              <div className="flex flex-col items-center">
                <span className="text-[10px] text-stone-400 font-medium mb-1">
                  {formatDuration(flight.duration_minutes)}
                </span>
                <div className="w-full flex items-center gap-1">
                  <div className="w-2 h-2 rounded-full border-2 border-stone-400 bg-white" />
                  <div className="flex-1 h-0.5 bg-stone-200 relative">
                    {flight.stops > 0 && (
                      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-amber-500" />
                    )}
                  </div>
                  <div className="w-2 h-2 rounded-full bg-stone-900" />
                </div>
                <span
                  className={`text-[10px] font-semibold mt-1 ${
                    flight.stops === 0 ? "text-emerald-600" : "text-amber-600"
                  }`}
                >
                  {flight.stops === 0 ? "Nonstop" : `${flight.stops} stop${flight.stops > 1 ? "s" : ""}`}
                </span>
              </div>

              <div className="text-right">
                <p className="text-base font-black text-stone-900 tracking-tight">
                  {formatFlightTime(flight.arrival_time)}
                </p>
                <p className="text-xs font-semibold text-stone-500">{flight.destination}</p>
              </div>
            </div>
          </div>

          {/* Return Leg if Round-Trip */}
          {returnLeg && (
            <div className="pt-3 border-t border-stone-100 flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex items-center gap-3.5 min-w-[190px]">
                <div className="w-11 h-11 rounded-2xl bg-amber-50 border border-amber-200/80 flex items-center justify-center text-xs font-black text-amber-900 shrink-0">
                  {returnLeg.airline_code || returnLeg.airline.slice(0, 2).toUpperCase()}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="text-sm font-bold text-stone-900 leading-tight">
                      {returnLeg.airline}
                    </h4>
                    <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[9px] font-bold text-amber-900 uppercase tracking-wider">
                      Return
                    </span>
                  </div>
                  <p className="text-[11px] text-stone-500 mt-0.5 flex items-center gap-1.5 flex-wrap">
                    <span>{returnLeg.flight_number || "Return Flight"}</span>
                    <span>·</span>
                    <span className="text-stone-700 font-medium">{returnLeg.date || "Scheduled return"}</span>
                  </p>
                </div>
              </div>

              {/* Return Timeline Graphic */}
              <div className="flex-1 grid grid-cols-[auto_1fr_auto] items-center gap-3 px-2 max-w-sm">
                <div className="text-left">
                  <p className="text-base font-black text-stone-900 tracking-tight">
                    {formatFlightTime(returnLeg.departure_time)}
                  </p>
                  <p className="text-xs font-semibold text-stone-500">{returnLeg.origin}</p>
                </div>

                <div className="flex flex-col items-center">
                  <span className="text-[10px] text-stone-400 font-medium mb-1">
                    {formatDuration(returnLeg.duration_minutes)}
                  </span>
                  <div className="w-full flex items-center gap-1">
                    <div className="w-2 h-2 rounded-full border-2 border-amber-400 bg-white" />
                    <div className="flex-1 h-0.5 bg-amber-200 relative">
                      {returnLeg.stops > 0 && (
                        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-amber-500" />
                      )}
                    </div>
                    <div className="w-2 h-2 rounded-full bg-amber-800" />
                  </div>
                  <span
                    className={`text-[10px] font-semibold mt-1 ${
                      returnLeg.stops === 0 ? "text-emerald-600" : "text-amber-600"
                    }`}
                  >
                    {returnLeg.stops === 0 ? "Nonstop" : `${returnLeg.stops} stop${returnLeg.stops > 1 ? "s" : ""}`}
                  </span>
                </div>

                <div className="text-right">
                  <p className="text-base font-black text-stone-900 tracking-tight">
                    {formatFlightTime(returnLeg.arrival_time)}
                  </p>
                  <p className="text-xs font-semibold text-stone-500">{returnLeg.destination}</p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Price & Book Link */}
        <div className="flex lg:flex-col items-center lg:items-end justify-between border-t lg:border-t-0 pt-3 lg:pt-0 border-stone-100 min-w-[210px] pl-0 lg:pl-4 lg:border-l">
          <div className="text-left lg:text-right">
            <p className="text-xl font-black text-stone-900 tracking-tight" suppressHydrationWarning>
              {formatPrice(flight)}
            </p>
            <p className="text-[10px] text-stone-500 font-semibold mt-0.5">
              {pax > 1
                ? `Total for ${pax} travelers (${formatPerPersonPrice(flight)} / person)`
                : `Total for 1 traveler${showReturn ? " (round trip)" : ""}`}
            </p>
            {flight.emissions && (
              <p
                className={`text-[10px] font-semibold mt-0.5 flex items-center gap-1 justify-start lg:justify-end ${
                  isLowerEmissions ? "text-emerald-700" : "text-stone-500"
                }`}
              >
                {isLowerEmissions && <Leaf className="w-2.5 h-2.5 text-emerald-600" />}
                <span>{flight.emissions}</span>
              </p>
            )}
          </div>

          <div className="mt-2.5 flex items-center gap-2">
            <button
              type="button"
              onClick={() => onAddToTrip && onAddToTrip(flight)}
              className="inline-flex items-center gap-1 rounded-2xl border border-stone-200 bg-white px-3.5 py-2 text-xs font-bold text-stone-800 hover:bg-stone-50 hover:border-stone-400 active:scale-98 transition-all shadow-2xs"
              title="Add flight to trip itinerary"
            >
              <Plus className="w-3.5 h-3.5 text-amber-600" />
              <span>Add to Trip</span>
            </button>
            <a
              href={
                flight.booking_url ||
                `https://www.google.com/travel/flights?q=flights+from+${flight.origin}+to+${flight.destination}&curr=INR`
              }
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-2xl bg-stone-900 px-3.5 py-2 text-xs font-semibold text-white hover:bg-stone-800 active:scale-98 transition-all shadow-xs"
            >
              <span>Book</span>
              <ExternalLink className="w-3 h-3 text-stone-300" />
            </a>
          </div>
        </div>
      </div>
    </article>
  );
}
