"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import Image from "next/image";
import Link from "next/link";
import { api, API_BASE } from "@/lib/api";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { InteractiveMap } from "@/components/map/InteractiveMap";
import { PlaceCard } from "@/components/chat/PlaceCard";
import { Sparkle, ChevronUp, X, Send, Mic, MicOff, Paperclip, Maximize2, RotateCcw, Compass } from "lucide-react";

const SUGGESTIONS = [
  "Plan a 3-day food tour in Rome",
  "Romantic long weekend in Paris",
  "3 days in Kyoto temples & tea",
  "5 quiet days in the Swiss Alps",
];

export default function ChatPage() {
  // Keep the initial value deterministic so server and client markup match.
  // The real session id is created in the mount effect below.
  const [sessionId, setSessionId] = useState<string>("");
  const [messages, setMessages] = useState<Array<{
    id?: number | string;
    sender: string;
    message: string;
    cards: any[];
    pins: any[];
    created_at?: string;
    loading?: boolean;
    error?: string;
    retryable?: boolean;
    retryPrompt?: string;
    retryCount?: number;
  }>>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [tripId, setTripId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"split" | "map" | "chat">("split");
  const [activePinId, setActivePinId] = useState<string | null>(null);
  const [highlightCard, setHighlightCard] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const messageIdCounter = useRef(0);

  useEffect(() => {
    async function init() {
      if (typeof window === "undefined") return;
      const params = new URLSearchParams(window.location.search);
      const urlTripId = params.get("trip_id");
      const urlSessionId = params.get("session_id");

      // 1. If trip_id is in URL, load trip chat context
      if (urlTripId) {
        setTripId(urlTripId);
        try {
          const res = await api(`/chat/trip/${urlTripId}`);
          if (res.ok) {
            const data = await res.json();
            if (data.session_id) {
              setSessionId(data.session_id);
              localStorage.setItem("mindtrip_session_id", data.session_id);
            }
            if (Array.isArray(data.messages) && data.messages.length > 0) {
              setMessages(data.messages);
              const lastAssistant = [...data.messages].reverse().find((m: any) => m.sender === "assistant" && m.pins?.length);
              if (lastAssistant && lastAssistant.pins?.length) {
                setActivePinId(lastAssistant.pins[0].id);
              }
              return;
            } else if (data.trip) {
              const tripPins = data.trip.days?.flatMap((d: any) => d.stops?.map((s: any, idx: number) => ({
                id: s.place_id || `stop-${d.day_index || 1}-${idx}`,
                name: s.place?.name || s.notes || "Stop",
                category: s.place?.category || "attraction",
                lat: s.place?.lat || 0,
                lon: s.place?.lon || 0,
                label: String(idx + 1),
                day_index: d.day_index || 1,
                order: idx,
                address: s.place?.address || "",
                photo: (s.place?.photos && s.place.photos[0]) || "",
              }))).filter((p: any) => p && p.lat && p.lon) || [];

              if (data.trip.hotel && data.trip.hotel.lat && data.trip.hotel.lon) {
                tripPins.unshift({
                  id: data.trip.hotel.id || "hotel-stay",
                  name: data.trip.hotel.name,
                  category: "hotel",
                  lat: data.trip.hotel.lat,
                  lon: data.trip.hotel.lon,
                  label: "H",
                  day_index: 0,
                  order: 0,
                  address: data.trip.hotel.address || "",
                  photo: (data.trip.hotel.photos && data.trip.hotel.photos[0]) || "",
                });
              }

              setMessages([
                {
                  id: "trip_intro",
                  sender: "assistant",
                  message: `Welcome! I've loaded your itinerary for “${data.trip.title}”. What would you like to explore or customize? I can recommend spots, swap hotels, or re-time your days.`,
                  cards: [{ type: "trip", ...data.trip }],
                  pins: tripPins,
                }
              ]);
              if (tripPins.length > 0) setActivePinId(tripPins[0].id);
              return;
            }
          }
        } catch (e) {
          console.warn("Could not load trip context:", e);
        }
      }

      // 2. Load stored session history from localStorage
      const savedSession = urlSessionId || localStorage.getItem("mindtrip_session_id");
      if (savedSession) {
        setSessionId(savedSession);
        try {
          const res = await api(`/chat/history/${savedSession}`);
          if (res.ok) {
            const data = await res.json();
            if (Array.isArray(data.messages) && data.messages.length > 0) {
              setMessages(data.messages);
              const lastAssistant = [...data.messages].reverse().find((m: any) => m.sender === "assistant" && m.pins?.length);
              if (lastAssistant && lastAssistant.pins?.length) {
                setActivePinId(lastAssistant.pins[0].id);
              }
              return;
            }
          }
        } catch (err) {
          console.warn("Could not load chat history:", err);
        }
      }

      // 3. Otherwise create fresh session
      try {
        const res = await api("/chat/session", { method: "POST" });
        const json = await res.json();
        if (json.session_id) {
          setSessionId(json.session_id);
          localStorage.setItem("mindtrip_session_id", json.session_id);
        }
      } catch (err) {
        console.warn("Using offline fallback session:", err);
        const fallback = "guest_" + Math.random().toString(36).substring(2, 11);
        setSessionId(fallback);
        localStorage.setItem("mindtrip_session_id", fallback);
      }
    }
    init();
  }, []);

  // Wire up the dead "mt-highlight-card" event from PlaceCard/PlaceDetailModal.
  // Centers the map on the pinned place and highlights the corresponding card.
  useEffect(() => {
    const handleHighlightCard = (event: CustomEvent<{ id?: string; name?: string }>) => {
      const { id, name } = event.detail || {};
      if (!id && !name) return;
      setActivePinId(id ?? null);
      setViewMode("map");
      const card = messages.flatMap((m) => m.cards || []).find(
        (c) => (id && c.id === id) || (name && c.name === name)
      );
      if (card) {
        setHighlightCard(card.id);
        setTimeout(() => setHighlightCard(null), 2500);
      }
    };
    window.addEventListener("mt-highlight-card", handleHighlightCard as EventListener);
    return () => window.removeEventListener("mt-highlight-card", handleHighlightCard as EventListener);
  }, [messages, setViewMode, setActivePinId, setHighlightCard]);

  const handleNewChat = useCallback(async () => {
    try {
      const res = await api("/chat/session", { method: "POST" });
      const json = await res.json();
      const newId = json.session_id || "guest_" + Math.random().toString(36).substring(2, 11);
      setSessionId(newId);
      localStorage.setItem("mindtrip_session_id", newId);
      setMessages([]);
      setTripId(null);
      setActivePinId(null);
    } catch {
      const newId = "guest_" + Math.random().toString(36).substring(2, 11);
      setSessionId(newId);
      localStorage.setItem("mindtrip_session_id", newId);
      setMessages([]);
      setTripId(null);
      setActivePinId(null);
    }
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const [initialSent, setInitialSent] = useState(false);

  const sendMessage = useCallback(async (userMessage: string) => {
    if (!userMessage.trim() || !sessionId || streaming) return;
    setStreaming(true);

    const userMsgId = `msg-${++messageIdCounter.current}-user`;
    const assistantMsgId = `msg-${++messageIdCounter.current}-assistant`;

    setMessages((prev) => [
      ...prev,
      { id: userMsgId, sender: "user", message: userMessage, cards: [], pins: [] },
      {
        id: assistantMsgId,
        sender: "assistant",
        message: "",
        cards: [],
        pins: [],
        loading: true,
        retryPrompt: userMessage,
      },
    ]);

    try {
      // Create a new AbortController for this request so the user can cancel it
      abortControllerRef.current = new AbortController();

      const response = await fetch(`${API_BASE}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: abortControllerRef.current.signal,
        body: JSON.stringify({
          message: userMessage,
          session_id: sessionId,
          context: tripId ? { trip_id: tripId } : {},
        }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`Stream HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let sawToken = false;
      let sawDone = false;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";

        for (const block of parts) {
          const lines = block.split("\n");
          let event = "message";
          let dataStr = "";

          for (const line of lines) {
            if (line.startsWith("event: ")) {
              event = line.replace("event: ", "").trim();
            } else if (line.startsWith("data: ")) {
              dataStr = line.replace("data: ", "").trim();
            }
          }

          if (!dataStr) continue;
          let data: any;
          try {
            data = JSON.parse(dataStr);
          } catch {
            // Ignore partial/invalid JSON chunks.
            continue;
          }

          if (event === "status") {
            if (data.text) setStatusMessage(data.text);
          } else if (event === "token") {
            sawToken = true;
            setStatusMessage(null);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, message: m.message + (data.text || ""), loading: false }
                  : m
              )
            );
          } else if (event === "cards") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId ? { ...m, cards: data, loading: false } : m
              )
            );
          } else if (event === "pins") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId ? { ...m, pins: data } : m
              )
            );
            if (Array.isArray(data) && data.length > 0) {
              setActivePinId(data[0].id);
            }
          } else if (event === "done") {
            sawDone = true;
            setStatusMessage(null);
            setMessages((prev) =>
              prev.map((m) => (m.id === assistantMsgId ? { ...m, loading: false } : m))
            );
            if (data.trip_id) {
              setTripId(data.trip_id);
              if (typeof window !== "undefined") {
                const p = new URLSearchParams(window.location.search);
                p.set("trip_id", data.trip_id);
                window.history.replaceState({}, "", `${window.location.pathname}?${p.toString()}`);
              }
            }
          } else if (event === "error") {
            const serverError = new Error(data.message || "The concierge hit a snag.") as Error & {
              isServerError?: boolean;
              retryable?: boolean;
            };
            serverError.isServerError = true;
            serverError.retryable = data.retryable !== false;
            throw serverError;
          }
        }
      }

      // A stream that closes without any reply would otherwise leave an empty
      // bubble forever. Fall through to the direct endpoint in that case.
      if (!sawDone && !sawToken) {
        throw new Error("Stream ended without a reply");
      }
    } catch (streamErr) {
      const aborted =
        abortControllerRef.current?.signal.aborted ||
        (streamErr instanceof DOMException && streamErr.name === "AbortError") ||
        (streamErr as { name?: string })?.name === "AbortError";

      if (aborted) {
        setStatusMessage("Stream cancelled.");
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId && m.loading
              ? {
                  ...m,
                  message: m.message || "Request cancelled.",
                  loading: false,
                }
              : m
          )
        );
        setTimeout(() => setStatusMessage(null), 3000);
        return;
      }

      if ((streamErr as { isServerError?: boolean })?.isServerError) {
        // The server already told us what went wrong. Show an error state with retry option.
        setStatusMessage(null);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId && !m.message
              ? {
                  ...m,
                  message: (streamErr as Error).message || "The concierge hit a snag.",
                  error: (streamErr as Error).message,
                  retryable: (streamErr as { retryable?: boolean }).retryable !== false,
                  loading: false,
                }
              : m
          )
        );
        return;
      }

      console.warn("SSE stream interrupted; falling back to direct API:", streamErr);
      try {
        const res = await api("/chat/message", {
          method: "POST",
          body: JSON.stringify({
            message: userMessage,
            session_id: sessionId,
            context: tripId ? { trip_id: tripId } : {},
          }),
        });
        const reply = await res.json();
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? {
                  ...m,
                  message: reply.message || m.message,
                  cards: reply.cards || [],
                  pins: reply.pins || [],
                  created_at: reply.created_at,
                  loading: false,
                  error: undefined,
                }
              : m
          )
        );
        if (reply.trip_id) {
          setTripId(reply.trip_id);
          if (typeof window !== "undefined") {
            const p = new URLSearchParams(window.location.search);
            p.set("trip_id", reply.trip_id);
            window.history.replaceState({}, "", `${window.location.pathname}?${p.toString()}`);
          }
        }
        if (reply.pins?.length) setActivePinId(reply.pins[0].id);
        setStatusMessage(null);
      } catch (err) {
        // If the user cancelled the request, don't show an error message
        if (err instanceof DOMException && err.name === "AbortError") {
          setStatusMessage("Stream cancelled.");
          setTimeout(() => setStatusMessage(null), 3000);
        } else {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId && !m.message
                ? {
                    ...m,
                    message: "The concierge hit a snag. Please try again.",
                    error: "Request failed",
                    retryable: true,
                    loading: false,
                  }
                : m
            )
          );
        }
      }
    } finally {
      setStreaming(false);
      abortControllerRef.current = null;
    }
  }, [sessionId, streaming, tripId]);

  useEffect(() => {
    if (initialSent || !sessionId) return;
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const q = params.get("q");
      const dest = params.get("destination");
      const prompt = (q && q.trim()) || (dest && dest.trim() ? `Plan a 3-day trip to ${dest.trim()}` : "");
      if (prompt) {
        setInitialSent(true);
        // Clean ?q= / ?destination= from URL history immediately so refreshing never re-submits it!
        params.delete("q");
        params.delete("destination");
        const remaining = params.toString();
        window.history.replaceState({}, "", window.location.pathname + (remaining ? `?${remaining}` : ""));
        sendMessage(prompt);
      }
    }
  }, [sessionId, initialSent, sendMessage]);

  // Extract pins from the latest message that contains pins, deduplicated by ID
  const activePins = (() => {
    const lastWithPins = [...messages].reverse().find((m) => m.pins && m.pins.length > 0);
    if (!lastWithPins) return [];
    const seen = new Set<string>();
    return lastWithPins.pins.filter((p: any) => {
      const id = p.id || `${p.lat}-${p.lon}`;
      if (seen.has(id)) return false;
      seen.add(id);
      return true;
    });
  })();

  // Dynamically adapt suggestions based on the active conversation and trip context
  const dynamicSuggestions = (() => {
    const lastTripCard = messages.flatMap((m) => m.cards || []).find((c) => c.type === "trip");
    const dest = lastTripCard?.destination || (lastTripCard?.title ? lastTripCard.title.split(":")[0] : "");
    if (dest) {
      return [
        `🏨 Show boutique hotels in ${dest}`,
        `💰 Cheaper stays under $150 in ${dest}`,
        `🍴 Swap Day 2 dinner to local cuisine`,
        `☕ Add a coffee stop on Day 1`,
        `✈️ Check flight options to ${dest}`,
      ];
    }
    if (messages.length > 0) {
      return [
        "🏨 Find boutique hotels nearby",
        "🍴 Recommend best local dining for dinner",
        "🌅 Best sunset spots around here",
        "🚶 Walkable sights nearby",
      ];
    }
    return SUGGESTIONS;
  })();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !sessionId) return;
    const userMessage = input;
    setInput("");
    await sendMessage(userMessage);
  };

  const handleScrollToTrip = useCallback(() => {
    if (tripId) window.location.href = `/trip/${tripId}`;
  }, [tripId]);

  return (
    <div className="relative h-[calc(100vh-4rem)] sm:h-[calc(100vh-4.5rem)] max-h-[calc(100vh-4rem)] sm:max-h-[calc(100vh-4.5rem)] bg-paper flex flex-col overflow-hidden">
      {/* Chat Workspace Controls Toolbar */}
      <div className="border-b border-line/70 bg-paper/90 px-5 py-2.5 backdrop-blur-md shadow-2xs shrink-0 z-20">
        <div className="mx-auto flex w-full max-w-[1440px] items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted">
            <span className="size-2 rounded-full bg-olive animate-pulse" />
            AI Travel Concierge
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setViewMode("chat")}
              className={`px-3 py-1.5 rounded-full flex items-center justify-center border text-xs font-semibold transition-all ${
                viewMode === "chat" ? "bg-ink text-white border-ink shadow-xs" : "border-line bg-white text-ink hover:bg-cream"
              }`}
            >
              Chat
            </button>
            <button
              onClick={() => setViewMode("map")}
              className={`px-3 py-1.5 rounded-full flex items-center justify-center border text-xs font-semibold transition-all ${
                viewMode === "map" ? "bg-ink text-white border-ink shadow-xs" : "border-line bg-white text-ink hover:bg-cream"
              }`}
            >
              Map
            </button>
            <button
              onClick={() => setViewMode("split")}
              className={`px-3 py-1.5 rounded-full flex items-center justify-center border text-xs font-semibold transition-all ${
                viewMode === "split" ? "bg-ink text-white border-ink shadow-xs" : "border-line bg-white text-ink hover:bg-cream"
              }`}
            >
              Split
            </button>
            {tripId && (
              <Link
                href={`/trip/${tripId}`}
                className="flex items-center gap-1.5 rounded-full border border-line/80 bg-paper px-3.5 py-1.5 text-xs font-semibold text-ink shadow-2xs hover:bg-ink hover:text-white transition-all ml-2"
              >
                <ChevronUp size={14} /> View itinerary
              </Link>
            )}
            <button
              type="button"
              onClick={handleNewChat}
              className="flex items-center gap-1.5 rounded-full border border-line bg-white px-3 py-1.5 text-xs font-semibold text-ink shadow-2xs hover:bg-stone-100 transition-all ml-1"
              title="Start a fresh conversation"
            >
              <RotateCcw size={12} /> New Chat
            </button>
          </div>
        </div>
      </div>

      <main className="flex-1 relative flex flex-col min-h-0 h-full overflow-hidden">
        {viewMode === "map" && (
          <div className="h-full w-full relative">
            <InteractiveMap
              pins={activePins}
              activePinId={activePinId}
              onPinClick={(id) => {
                setActivePinId(id);
                const card = messages.flatMap((m) => m.cards).find((c) => c.id === id || c.name === id);
                if (card) setHighlightCard(card.id);
                setTimeout(() => setHighlightCard(null), 2000);
              }}
            />
            {tripId && (
              <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-50 flex gap-2">
                <Link
                  href={`/trip/${tripId}`}
                  className="rounded-full border border-line bg-white px-4 py-2 text-sm font-medium text-ink shadow-luxe hover:bg-ink/5 transition-colors"
                >
                  Open full itinerary
                </Link>
              </div>
            )}
          </div>
        )}
        {viewMode === "chat" && (
          <div className="h-full w-full flex flex-col min-h-0 overflow-hidden">
            <div className="flex-1 min-h-0 overflow-y-auto px-5 py-6 sm:px-8 thin-scrollbar">
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full text-center text-muted py-12">
                  <Sparkle className="mb-4 w-12 h-12 text-olive" />
                  <h2 className="text-2xl font-serif-italic font-bold text-ink">Start your trip</h2>
                  <p className="mt-2 max-w-md text-sm text-ink/75">
                    Ask me to plan a trip — day by day, stop by stop, synchronized to the live map.
                  </p>
                  <div className="mt-6 flex flex-wrap justify-center gap-2 max-w-lg">
                    {SUGGESTIONS.map((suggestion, sIdx) => (
                      <button
                        key={`start-sugg-${sIdx}`}
                        type="button"
                        onClick={() => sendMessage(suggestion)}
                        className="rounded-full border border-line/80 bg-paper px-3.5 py-1.5 text-xs font-semibold text-ink shadow-2xs hover:bg-ink hover:text-white hover:border-ink transition-all active:scale-95"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <div className="max-w-2xl mx-auto space-y-6">
                {messages.map((message, mIdx) => (
                  <MessageBubble
                    key={message.id ? `msg-${message.id}-${mIdx}` : `msg-${mIdx}`}
                    message={message}
                    onSendMessage={(msg) => sendMessage(msg)}
                  />
                ))}
                {streaming && statusMessage && (
                  <div className="flex items-center gap-2 text-xs font-semibold text-olive bg-olive/10 border border-olive/20 rounded-full px-3.5 py-1.5 w-fit shadow-2xs animate-pulse">
                    <span className="size-2 rounded-full bg-olive animate-ping" />
                    {statusMessage}
                    <button
                      type="button"
                      onClick={() => abortControllerRef.current?.abort()}
                      className="text-xs font-bold underline decoration-olive/40 hover:decoration-olive transition-colors"
                      title="Cancel current request"
                    >
                      Cancel
                    </button>
                  </div>
                )}
              </div>
              <div ref={messagesEndRef} />
            </div>
            <div className="shrink-0 bg-paper border-t border-line/60">
              <ChatInput
                onSubmit={handleSubmit}
                input={input}
                setInput={setInput}
                inputRef={inputRef}
                disabled={!sessionId || streaming}
                streaming={streaming}
                onCancel={() => abortControllerRef.current?.abort()}
                onSuggestionClick={(q) => sendMessage(q)}
                suggestions={dynamicSuggestions}
              />
            </div>
          </div>
        )}
        {viewMode === "split" && (
          <div className="h-full w-full flex flex-col lg:flex-row overflow-hidden min-h-0">
            {/* Left Column: Dedicated isolated chat container */}
            <div className="flex-1 min-w-0 border-r border-line bg-paper flex flex-col min-h-0 h-full overflow-hidden">
              <div className="flex-1 min-h-0 overflow-y-auto px-5 py-6 sm:px-8 thin-scrollbar">
                {messages.length === 0 && (
                  <div className="flex flex-col items-center justify-center h-full text-center text-muted py-12">
                    <Sparkle className="mb-4 w-12 h-12 text-olive" />
                    <h2 className="text-2xl font-serif-italic font-bold text-ink">Start your trip</h2>
                    <p className="mt-2 max-w-md mx-auto text-sm text-ink/75">
                      Ask me to plan a trip — day by day, stop by stop, synchronized to the live map.
                    </p>
                    <div className="mt-6 flex flex-wrap justify-center gap-2 max-w-lg">
                      {SUGGESTIONS.map((suggestion, sIdx) => (
                        <button
                          key={`split-start-sugg-${sIdx}`}
                          type="button"
                          onClick={() => sendMessage(suggestion)}
                          className="rounded-full border border-line/80 bg-paper px-3.5 py-1.5 text-xs font-semibold text-ink shadow-2xs hover:bg-ink hover:text-white hover:border-ink transition-all active:scale-95"
                        >
                          {suggestion}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                <div className="max-w-2xl mx-auto space-y-6">
                  {messages.map((message, mIdx) => (
                    <MessageBubble
                      key={message.id ? `msg-${message.id}-${mIdx}` : `msg-${mIdx}`}
                      message={message}
                      onSendMessage={(msg) => sendMessage(msg)}
                    />
                  ))}
                  {streaming && statusMessage && (
                    <div className="flex items-center gap-2 text-xs font-semibold text-olive bg-olive/10 border border-olive/20 rounded-full px-3.5 py-1.5 w-fit shadow-2xs animate-pulse">
                      <span className="size-2 rounded-full bg-olive animate-ping" />
                      {statusMessage}
                      <button
                        type="button"
                        onClick={() => abortControllerRef.current?.abort()}
                        className="text-xs font-bold underline decoration-olive/40 hover:decoration-olive transition-colors"
                        title="Cancel current request"
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                </div>
                <div ref={messagesEndRef} />
              </div>
              <div className="shrink-0 bg-paper border-t border-line/60">
                <ChatInput
                  onSubmit={handleSubmit}
                  input={input}
                  setInput={setInput}
                  inputRef={inputRef}
                  disabled={!sessionId || streaming}
                  streaming={streaming}
                  onCancel={() => abortControllerRef.current?.abort()}
                  onSuggestionClick={(q) => sendMessage(q)}
                  suggestions={dynamicSuggestions}
                />
              </div>
            </div>

            {/* Right Column: Centered curved-edge square map covering 70% of vertical height */}
            <div className="lg:w-[40%] xl:w-[38%] min-w-[340px] max-w-[620px] flex flex-col items-center justify-center border-l border-line bg-stone-50/70 p-4 sm:p-6 shrink-0 h-full overflow-hidden">
              <div className="w-full max-w-[480px] h-[70%] max-h-[70vh] aspect-square rounded-3xl overflow-hidden shadow-card border border-line/80 relative bg-white">
                <InteractiveMap
                  pins={activePins}
                  activePinId={activePinId}
                  highlightCard={highlightCard}
                  onPinClick={(id) => {
                    setActivePinId(id);
                    setViewMode("map");
                  }}
                />
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function ChatInput({
  onSubmit,
  input,
  setInput,
  inputRef,
  disabled,
  streaming,
  onCancel,
  onSuggestionClick,
  suggestions,
}: {
  onSubmit: (e: React.FormEvent) => void;
  input: string;
  setInput: (v: string) => void;
  inputRef: React.RefObject<HTMLTextAreaElement>;
  disabled: boolean;
  streaming?: boolean;
  onCancel?: () => void;
  onSuggestionClick?: (s: string) => void;
  suggestions?: string[];
}) {
  const [isListening, setIsListening] = useState(false);
  const [speechAvailable, setSpeechAvailable] = useState(false);
  const recognitionRef = useRef<any>(null);

  // Auto-resize textarea height smoothly
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 140)}px`;
    }
  }, [input, inputRef]);

  // Initialize SpeechRecognition if supported
  useEffect(() => {
    if (typeof window !== "undefined") {
      const SpeechRecognition =
        (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (SpeechRecognition) {
        setSpeechAvailable(true);
        const recognizer = new SpeechRecognition();
        recognizer.continuous = false;
        recognizer.interimResults = true;
        recognizer.lang = "en-US";

        recognizer.onresult = (event: any) => {
          let transcript = "";
          for (let i = 0; i < event.results.length; i++) {
            transcript += event.results[i][0].transcript;
          }
          if (transcript.trim()) {
            setInput(transcript);
          }
        };

        recognizer.onerror = () => setIsListening(false);
        recognizer.onend = () => setIsListening(false);
        recognitionRef.current = recognizer;
      }
    }
    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {
          // ignore
        }
      }
    };
  }, [setInput]);

  const toggleListening = () => {
    if (!recognitionRef.current) return;
    if (isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
    } else {
      try {
        recognitionRef.current.start();
        setIsListening(true);
      } catch (err) {
        console.error("SpeechRecognition start error:", err);
        setIsListening(false);
      }
    }
  };

  const promptList =
    suggestions && suggestions.length > 0
      ? suggestions
      : [
          "Plan a 3-day trip to Dubai with flight arriving at 14:00",
          "4 days in Tokyo (temples & culinary)",
          "3 days in Rome (foodie edit)",
          "Romantic long weekend in Paris",
        ];

  return (
    <div className="border-t border-line/80 bg-white/95 backdrop-blur-md px-4 pt-2.5 pb-4 sm:px-8 sticky bottom-0 z-40 transition-all">
      <div className="max-w-[1440px] mx-auto">
        {/* Suggestion prompt pills */}
        {!input.trim() && !disabled && (
          <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-none text-xs">
            <span className="text-[11px] font-semibold text-muted uppercase tracking-wider shrink-0 flex items-center gap-1">
              <Sparkle size={12} className="text-olive" /> Suggestions:
            </span>
            {promptList.map((prompt, pIdx) => (
              <button
                key={`prompt-${pIdx}`}
                type="button"
                onClick={() => {
                  const cleaned = prompt.replace(/^[\p{Emoji}\s]+/u, "").trim();
                  if (onSuggestionClick) {
                    onSuggestionClick(cleaned || prompt);
                  } else {
                    setInput(cleaned || prompt);
                    inputRef.current?.focus();
                  }
                }}
                className="shrink-0 rounded-full border border-line bg-paper/60 px-3 py-1 text-xs font-medium text-ink hover:border-ink/30 hover:bg-white active:scale-95 transition-all shadow-2xs"
              >
                {prompt}
              </button>
            ))}
          </div>
        )}

        {/* Listening indicator alert banner */}
        {isListening && (
          <div className="mb-2 flex items-center justify-between rounded-lg bg-olive/10 border border-olive/30 px-3 py-1.5 text-xs text-olive animate-pulse">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-olive opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-olive"></span>
              </span>
              <span className="font-medium">Listening... speak your travel request</span>
            </div>
            <button
              type="button"
              onClick={toggleListening}
              className="text-xs font-semibold underline hover:text-ink transition-colors"
            >
              Stop
            </button>
          </div>
        )}

        {/* Input box */}
        <form
          onSubmit={onSubmit}
          className="relative flex items-end gap-2.5 rounded-2xl border border-line bg-white p-2.5 shadow-sm focus-within:border-ink/50 focus-within:ring-2 focus-within:ring-ink/10 transition-all"
        >
          {/* Voice Input button */}
          <button
            type="button"
            onClick={toggleListening}
            title={speechAvailable ? (isListening ? "Stop listening" : "Speak to Concierge") : "Voice input not supported in this browser"}
            disabled={disabled || !speechAvailable}
            className={`flex size-9 shrink-0 items-center justify-center rounded-full transition-all ${
              isListening
                ? "bg-rose-500 text-white animate-pulse"
                : speechAvailable
                ? "text-muted hover:text-ink hover:bg-paper"
                : "text-muted/40 cursor-not-allowed"
            }`}
          >
            {isListening ? <MicOff size={18} /> : <Mic size={18} />}
          </button>

          {/* Dynamic Auto-resizing Textarea */}
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSubmit(e as any);
              }
            }}
            rows={1}
            disabled={disabled}
            placeholder={isListening ? "Listening to your voice..." : "Ask Mindtrip anything: 'Plan 3 days in Dubai, flight arrives 2 PM'..."}
            className="flex-1 max-h-36 min-h-[38px] py-1.5 px-1 border-none bg-transparent resize-none text-sm text-ink placeholder:text-muted/70 focus:ring-0 sm:text-base leading-relaxed"
          />

          {/* Clear text button */}
          {input.length > 0 && (
            <button
              type="button"
              onClick={() => {
                setInput("");
                inputRef.current?.focus();
              }}
              title="Clear input"
              className="flex size-7 shrink-0 items-center justify-center rounded-full text-muted hover:text-ink hover:bg-paper transition-colors"
            >
              <X size={16} />
            </button>
          )}

          {/* Cancel streaming button */}
          {streaming && onCancel && (
            <button
              type="button"
              onClick={onCancel}
              title="Cancel current response"
              className="flex size-9 shrink-0 items-center justify-center rounded-full bg-rose-500 text-white hover:bg-rose-600 active:scale-95 transition-all shadow-sm"
            >
              <X size={16} />
              <span className="sr-only">Cancel</span>
            </button>
          )}

          {/* Send Action */}
          <button
            type="submit"
            disabled={disabled || !input.trim()}
            title="Send message (Enter)"
            className="flex size-9 shrink-0 items-center justify-center rounded-full bg-ink text-white hover:bg-ink-soft active:scale-95 transition-all disabled:opacity-25 disabled:pointer-events-none shadow-sm"
          >
            <Send size={16} />
          </button>
        </form>

        {/* Footer shortcuts hint */}
        <div className="mt-1.5 flex items-center justify-between px-2 text-[11px] text-muted">
          <span>Mindtrip AI Concierge • Instant itinerary & live routes</span>
          <span className="hidden sm:inline">Press <kbd className="font-mono bg-paper px-1 py-0.5 rounded border border-line text-[10px]">Enter ↵</kbd> to send, <kbd className="font-mono bg-paper px-1 py-0.5 rounded border border-line text-[10px]">Shift+Enter</kbd> for newline</span>
        </div>
      </div>
    </div>
  );
}
