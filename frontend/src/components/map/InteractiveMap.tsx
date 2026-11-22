"use client";

import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { ChevronRight, Globe, Check } from "lucide-react";

const CATEGORY_COLOR: Record<string, string> = {
  hotel: "#434717",
  restaurant: "#e86a4a",
  cafe: "#9a5f2c",
  attraction: "#2f4a63",
  activity: "#6b4f8a",
  bar: "#b85c38",
  shopping: "#a8d8ea",
  recommended: "#78716c",
  other: "#434717",
};

interface Pin {
  id: string;
  name: string;
  category?: string;
  lat: number;
  lon: number;
  rating?: number | null;
  address?: string;
  photo?: string;
  day_index?: number;
  order?: number;
  label?: string;
  trip_id?: string;
  description?: string;
  is_itinerary_stop?: boolean;
}

interface InteractiveMapProps {
  pins: Pin[];
  activePinId?: string | null;
  highlightCard?: string | null;
  onPinClick?: (id: string) => void;
}

// Fallback raster OpenStreetMap style in case of offline or network interruption
const OSM_RASTER_STYLE: any = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: [
        "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "https://c.tile.openstreetmap.org/{z}/{x}/{y}.png",
      ],
      tileSize: 256,
      maxzoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

const ENGLISH_TEXT_FIELD = [
  "coalesce",
  ["get", "name:en"],
  ["get", "name_en"],
  ["get", "name:latin"],
  ["get", "name"],
];

const LOCAL_TEXT_FIELD = [
  "coalesce",
  ["get", "name"],
  ["get", "name_en"],
  ["get", "name:latin"],
];

const HTML_ESCAPES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

function escapeHtml(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (char) => HTML_ESCAPES[char] || char);
}

// Module-level in-memory caches
let cachedEnglishStyle: any = null;
let cachedRawStyle: any = null;

function shouldTranslateTextField(textField: unknown): boolean {
  if (typeof textField === "string") {
    return textField.includes("{name") || textField.includes("{name_en");
  }
  if (Array.isArray(textField)) {
    const s = JSON.stringify(textField);
    // Only translate layers that strictly refer to name, avoiding elevations ["get", "ele"], housenumbers, etc.
    return (
      s.includes('"name"') ||
      s.includes('"name:en"') ||
      s.includes('"name_en"') ||
      s.includes('"name:latin"')
    );
  }
  return false;
}

function transformStyleLanguage(style: any, lang: "en" | "local"): any {
  if (!style || !Array.isArray(style.layers)) return style;
  const cloned = JSON.parse(JSON.stringify(style));
  const targetExpr = lang === "en" ? ENGLISH_TEXT_FIELD : LOCAL_TEXT_FIELD;

  for (const layer of cloned.layers) {
    const layout = (layer as any).layout;
    if (layout && layout["text-field"]) {
      const cur = layout["text-field"];
      if (!shouldTranslateTextField(cur)) continue;
      layout["text-field"] = targetExpr;
    }
  }
  return cloned;
}

async function loadOpenStreetMapStyle(lang: "en" | "local" = "en"): Promise<any> {
  if (lang === "en" && cachedEnglishStyle) {
    return JSON.parse(JSON.stringify(cachedEnglishStyle));
  }
  if (lang === "local" && cachedRawStyle) {
    return JSON.parse(JSON.stringify(cachedRawStyle));
  }

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 4000);

    // OpenFreeMap Liberty style: complete OpenStreetMap vector data with free global CDN
    const response = await fetch("https://tiles.openfreemap.org/styles/liberty", {
      signal: controller.signal,
      cache: "force-cache",
    });
    clearTimeout(timeoutId);

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const rawStyle = await response.json();
    cachedRawStyle = rawStyle;

    cachedEnglishStyle = transformStyleLanguage(rawStyle, "en");
    return JSON.parse(JSON.stringify(lang === "en" ? cachedEnglishStyle : cachedRawStyle));
  } catch (err) {
    console.warn("Could not load OpenFreeMap vector style; falling back to OSM raster:", err);
    return OSM_RASTER_STYLE;
  }
}

export function InteractiveMap({ pins, activePinId, highlightCard, onPinClick }: InteractiveMapProps) {
  const mapRef = useRef<maplibregl.Map | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);
  const markersRef = useRef<Map<string, maplibregl.Marker>>(new Map());
  const fittedOnceRef = useRef(false);
  const [highlighted, setHighlighted] = useState<string | null>(null);
  const [currentLang, setCurrentLang] = useState<"en" | "local">("en");
  const [isVectorMap, setIsVectorMap] = useState<boolean>(true);
  const [activeDayFilter, setActiveDayFilter] = useState<number | "all">("all");

  // Derive unique day indices from pin list
  const daysList = useMemo(() => {
    const set = new Set<number>();
    pins.forEach((p) => {
      const d = Number(p.day_index);
      if (Number.isInteger(d) && d > 0) set.add(d);
    });
    return Array.from(set).sort((a, b) => a - b);
  }, [pins]);

  const goToPin = useCallback(
    (id: string) => {
      const pin = pins.find((p) => p.id === id);
      if (!pin || !mapRef.current) return;
      mapRef.current.flyTo({ center: [pin.lon, pin.lat], zoom: 14, duration: 1200 });
      const marker = markersRef.current.get(id);
      if (marker) marker.getElement().classList.add("active");
      setTimeout(() => marker?.getElement().classList.remove("active"), 2200);
    },
    [pins]
  );

  const fitToPins = useCallback((map: maplibregl.Map, pinList: Pin[]) => {
    const valid = pinList.filter(
      (p) => Number.isFinite(p.lat) && Number.isFinite(p.lon) && (p.lat !== 0 || p.lon !== 0)
    );
    if (valid.length === 0) return;
    if (valid.length === 1) {
      map.flyTo({ center: [valid[0].lon, valid[0].lat], zoom: 13, duration: 700 });
      return;
    }
    const bounds = new maplibregl.LngLatBounds();
    valid.forEach((p) => bounds.extend([p.lon, p.lat]));
    map.fitBounds(bounds, { padding: 48, maxZoom: 14, duration: 700 });
  }, []);

  // Apply language toggle dynamically to existing map layers
  const toggleLanguage = useCallback(() => {
    const nextLang = currentLang === "en" ? "local" : "en";
    setCurrentLang(nextLang);

    if (!mapRef.current || !isVectorMap) return;
    const map = mapRef.current;
    const style = map.getStyle();
    if (!style || !Array.isArray(style.layers)) return;

    const expr = nextLang === "en" ? ENGLISH_TEXT_FIELD : LOCAL_TEXT_FIELD;

    for (const layer of style.layers) {
      const layout = (layer as any).layout;
      if (layout && layout["text-field"]) {
        const cur = layout["text-field"];
        if (!shouldTranslateTextField(cur)) continue;
        try {
          map.setLayoutProperty(layer.id, "text-field", expr);
        } catch {
          // ignore layers that do not support dynamic layout updates
        }
      }
    }
  }, [currentLang, isVectorMap]);

  useEffect(() => {
    if (!containerRef.current) return;
    if (mapRef.current) {
      setReady(true);
      return;
    }

    let isMounted = true;

    async function initMap() {
      // 1. Load OpenStreetMap style defaulted to English
      const style = await loadOpenStreetMapStyle("en");
      if (!isMounted || !containerRef.current) return;

      const hasVector = Boolean(style.sources && !style.sources.osm);
      setIsVectorMap(hasVector);

      // Initial center based on first pin if available
      const initialCenter: [number, number] =
        pins.length > 0 && pins[0].lon && pins[0].lat
          ? [pins[0].lon, pins[0].lat]
          : [135.7681, 35.0116];

      const map = new maplibregl.Map({
        container: containerRef.current,
        style: style,
        center: initialCenter,
        zoom: pins.length > 0 ? 12 : 3,
        scrollZoom: true,
        touchZoomRotate: true,
        doubleClickZoom: true,
        interactive: true,
      });

      // Ensure zooming and interactions are fully enabled
      map.scrollZoom.enable();
      map.dragPan.enable();
      map.boxZoom.enable();
      map.doubleClickZoom.enable();

      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
      map.addControl(new maplibregl.ScaleControl(), "bottom-left");

      map.on("styleimagemissing", (e) => {
        const id = e.id;
        if (!map.hasImage(id)) {
          try {
            if (typeof ImageData !== "undefined") {
              map.addImage(id, new ImageData(new Uint8ClampedArray(4), 1, 1));
            } else {
              map.addImage(id, { width: 1, height: 1, data: new Uint8Array([0, 0, 0, 0]) });
            }
          } catch {
            // ignore if added in a concurrent frame
          }
        }
      });

      map.on("load", () => {
        if (!isMounted) return;
        setReady(true);
        mapRef.current = map;
        renderPins(map);
        updateRouteLines(map, pins, activeDayFilter);

        // Fit map bounds to the pins available at first paint.
        fitToPins(map, pins);
        fittedOnceRef.current = pins.length > 0;
      });

      map.on("click", () => {
        // no-op; pins are HTML markers
      });
    }

    initMap();

    let resizeObserver: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined" && containerRef.current) {
      resizeObserver = new ResizeObserver(() => {
        if (mapRef.current) {
          mapRef.current.resize();
        }
      });
      resizeObserver.observe(containerRef.current);
    }

    return () => {
      isMounted = false;
      resizeObserver?.disconnect();
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
      markersRef.current.clear();
      setReady(false);
    };
  }, []);

  const updateRouteLines = useCallback((map: maplibregl.Map, pinList: Pin[], activeDay: number | "all" = "all") => {
    try {
      // 1. Deduplicate pins by ID
      const seen = new Set<string>();
      const deduped: Pin[] = [];
      pinList.forEach((p) => {
        const id = p.id || `${p.lat}-${p.lon}`;
        if (!seen.has(id)) {
          seen.add(id);
          deduped.push(p);
        }
      });

      // Filter itinerary stops strictly:
      // Must have valid lat/lon, must NOT be hotel or recommended, must have an order index
      const validStops = deduped.filter(
        (p) =>
          p.lat &&
          p.lon &&
          (p.lat !== 0 || p.lon !== 0) &&
          p.category !== "hotel" &&
          p.category !== "recommended" &&
          p.order !== undefined &&
          p.is_itinerary_stop !== false
      );

      // 2. Group stops strictly by day_index so lines do not zig-zag across days
      const stopsByDay: Record<number, Pin[]> = {};
      validStops.forEach((p) => {
        const d = p.day_index || 1;
        if (!stopsByDay[d]) stopsByDay[d] = [];
        stopsByDay[d].push(p);
      });

      const features: any[] = [];
      const daysToDraw =
        activeDay === "all"
          ? Object.keys(stopsByDay).map(Number).sort((a, b) => a - b)
          : [Number(activeDay)];

      daysToDraw.forEach((dayNum) => {
        const dayStops = stopsByDay[dayNum] || [];
        // Sort stops of this day strictly in ascending visiting order (0, 1, 2...)
        const sorted = [...dayStops].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
        const dayCoords = sorted.map((p) => [p.lon, p.lat]);

        // Connect only consecutive spots within that day (Spot 1 -> Spot 2 -> Spot 3)
        // If there are 3 places to visit, this generates strictly 2 connecting branches
        // If a 4th spot is added, this connects 3 branches in sequential manner
        // If a user reorders spots, sorting by order ensures the lines reconnect immediately
        if (dayCoords.length >= 2) {
          features.push({
            type: "Feature",
            properties: { type: "day-route", day: dayNum },
            geometry: {
              type: "LineString",
              coordinates: dayCoords,
            },
          });
        }
      });

      const geojsonData = {
        type: "FeatureCollection",
        features,
      };

      const source = map.getSource("route-branches") as maplibregl.GeoJSONSource;
      if (source) {
        source.setData(geojsonData as any);
      } else if (map.isStyleLoaded()) {
        map.addSource("route-branches", {
          type: "geojson",
          data: geojsonData as any,
        });

        map.addLayer({
          id: "route-branches-casing",
          type: "line",
          source: "route-branches",
          layout: {
            "line-join": "round",
            "line-cap": "round",
          },
          paint: {
            "line-color": "#ffffff",
            "line-width": 5.5,
            "line-opacity": 0.85,
          },
        });

        map.addLayer({
          id: "route-branches-line",
          type: "line",
          source: "route-branches",
          layout: {
            "line-join": "round",
            "line-cap": "round",
          },
          paint: {
            "line-color": "#434717",
            "line-width": 3,
            "line-dasharray": [2.5, 1.5],
            "line-opacity": 0.95,
          },
        });
      }
    } catch {
      // Map style loading in progress
    }
  }, []);

  const renderPins = useCallback((map: maplibregl.Map) => {
    markersRef.current.forEach((m) => m.remove());
    markersRef.current.clear();

    // Deduplicate pins to avoid duplicate DOM markers
    const seen = new Set<string>();
    const dedupedPins = pins.filter((p) => {
      const id = p.id || `${p.lat}-${p.lon}`;
      if (seen.has(id)) return false;
      seen.add(id);
      return true;
    });

    // Filter pins if activeDayFilter is selected
    const visiblePins = dedupedPins.filter(
      (p) => activeDayFilter === "all" || p.category === "hotel" || !p.day_index || p.day_index === activeDayFilter
    );

    visiblePins.forEach((pin) => {
      const el = document.createElement("div");
      el.className = "mt-marker shrink-0 cursor-pointer transition-transform hover:scale-110";
      el.dataset.category = pin.category || "other";
      el.dataset.active = "false";
      el.title = pin.name;
      el.style.background = CATEGORY_COLOR[pin.category || "other"] || CATEGORY_COLOR.other;
      el.innerHTML = `<span style="font-weight: 800; font-size: 11px;">${pin.label || pin.name.charAt(0).toUpperCase()}</span>`;

      const pinMeta = pin.category === "hotel"
        ? "Primary Stay"
        : `Day ${pin.day_index || 1} · Spot #${pin.label || (pin.order != null ? pin.order + 1 : 1)}`;
      const popup = new maplibregl.Popup({ offset: 25, closeButton: false }).setHTML(`
        <div style="font-family: inherit; padding: 5px 8px; max-width: 200px;">
          <div style="font-size: 10px; font-weight: 800; text-transform: uppercase; color: #434717; letter-spacing: 0.5px;">
            ${escapeHtml(pinMeta)}
          </div>
          <div style="font-size: 12px; font-weight: 700; color: #1c1917; margin-top: 2px;">
            ${escapeHtml(pin.name)}
          </div>
          ${pin.address ? `<div style="font-size: 10px; color: #78716c; margin-top: 2px; line-height: 1.2;">${escapeHtml(pin.address)}</div>` : ""}
        </div>
      `);

      const marker = new maplibregl.Marker({ element: el, anchor: "bottom" })
        .setLngLat([pin.lon, pin.lat])
        .setPopup(popup)
        .addTo(map);

      el.addEventListener("mouseenter", () => popup.addTo(map));
      el.addEventListener("mouseleave", () => popup.remove());

      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        if (onPinClick) onPinClick(pin.id);
        setHighlighted(pin.id);
        setTimeout(() => setHighlighted(null), 2000);
        goToPin(pin.id);
      });

      markersRef.current.set(pin.id, marker);
    });

    updateRouteLines(map, visiblePins, activeDayFilter);
  }, [pins, onPinClick, goToPin, updateRouteLines, activeDayFilter]);

  useEffect(() => {
    if (!ready || !mapRef.current) return;
    renderPins(mapRef.current);
    updateRouteLines(mapRef.current, pins, activeDayFilter);

    // If pins arrive after the map mounted (common in chat), frame them once.
    if (pins.length === 0) {
      fittedOnceRef.current = false;
    } else if (!fittedOnceRef.current) {
      fitToPins(mapRef.current, pins);
      fittedOnceRef.current = true;
    }

    // re-apply active states
    markersRef.current.forEach((marker, id) => {
      const el = marker.getElement();
      el.dataset.active = id === activePinId ? "true" : "false";
      if (id === activePinId) {
        mapRef.current?.flyTo({
          center: [pins.find((p) => p.id === id)?.lon ?? 0, pins.find((p) => p.id === id)?.lat ?? 0],
          zoom: 14,
          duration: 800,
        });
      }
    });
  }, [ready, pins, activeDayFilter, activePinId, renderPins, updateRouteLines, fitToPins]);

  // Keep the day filter valid and frame the selected day when it changes.
  useEffect(() => {
    if (activeDayFilter !== "all" && !daysList.includes(activeDayFilter)) {
      setActiveDayFilter("all");
    }
  }, [daysList, activeDayFilter]);

  useEffect(() => {
    if (!ready || !mapRef.current || activeDayFilter === "all") return;
    const dayPins = pins.filter((p) => p.day_index === activeDayFilter);
    if (dayPins.length > 0) fitToPins(mapRef.current, dayPins);
  }, [activeDayFilter, ready, pins, fitToPins]);

  useEffect(() => {
    if (highlightCard) {
      const pin = pins.find((p) => p.id === highlightCard);
      if (pin) {
        setHighlighted(pin.id);
        goToPin(pin.id);
        setTimeout(() => setHighlighted(null), 2000);
      }
    }
  }, [highlightCard, pins, goToPin]);

  return (
    <div
      ref={containerRef}
      className="h-full w-full relative bg-stone-100 overflow-hidden"
      style={{ height: "100%", minHeight: "100%" }}
    >
      {!ready && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-stone-50 z-10">
          <div className="shimmer rounded-full w-12 h-12 mb-2"></div>
          <div className="shimmer h-4 w-32 rounded-full"></div>
          <span className="text-[11px] text-stone-500 font-medium mt-2">Loading English map...</span>
        </div>
      )}

      {/* English Language Indicator & Toggle Badge */}
      {ready && isVectorMap && (
        <div className="absolute top-3 left-3 z-20 flex items-center gap-1.5 rounded-full border border-stone-200/90 bg-white/95 backdrop-blur px-2.5 py-1 text-[11px] font-bold text-stone-800 shadow-xs transition-all">
          <Globe size={12} className="text-sky-600 shrink-0" />
          <span>{currentLang === "en" ? "English Labels" : "Native Script"}</span>
          <button
            type="button"
            onClick={toggleLanguage}
            className="ml-1 text-[10px] text-stone-400 hover:text-stone-900 underline font-normal transition-colors"
            title="Switch between English and Local language labels"
          >
            {currentLang === "en" ? "show native" : "set English"}
          </button>
        </div>
      )}

      {/* Day Selector Pills for Clean Route Branches */}
      {ready && daysList.length > 1 && (
        <div className="absolute top-11 left-3 z-20 flex items-center gap-1 rounded-full border border-stone-200/90 bg-white/95 backdrop-blur p-1 shadow-xs transition-all">
          <button
            type="button"
            onClick={() => setActiveDayFilter("all")}
            className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold transition-all ${
              activeDayFilter === "all"
                ? "bg-stone-900 text-white shadow-xs"
                : "text-stone-600 hover:text-stone-900 hover:bg-stone-100"
            }`}
          >
            All Days
          </button>
          {daysList.map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => setActiveDayFilter(d)}
              className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold transition-all ${
                activeDayFilter === d
                  ? "bg-stone-900 text-white shadow-xs"
                  : "text-stone-600 hover:text-stone-900 hover:bg-stone-100"
              }`}
            >
              Day {d}
            </button>
          ))}
        </div>
      )}

      {/* Center on Pin / Map button */}
      <button
        onClick={() => {
          const next = highlighted ? null : activePinId ?? pins[0]?.id;
          setHighlighted(next);
          if (next) goToPin(next);
        }}
        className="absolute top-3 right-12 z-20 flex size-8 items-center justify-center rounded-full border border-stone-200 bg-white shadow-xs hover:bg-stone-900 hover:text-white transition-colors"
        title="Cycle through itinerary stops"
      >
        {highlighted ? <ChevronRight size={14} /> : <span className="text-[10px] font-bold uppercase tracking-wider">pin</span>}
      </button>
    </div>
  );
}
