"use client";

import { useState } from "react";
import { PlaceCard } from "@/components/chat/PlaceCard";
import { TripCard } from "@/components/chat/TripCard";
import { FlightCard } from "@/components/chat/FlightCard";
import { HotelCard } from "@/components/chat/HotelCard";
import { TripIntakeCard } from "@/components/chat/TripIntakeCard";
import { MarkdownRenderer } from "@/components/chat/MarkdownRenderer";
import { RefreshCw, AlertCircle } from "lucide-react";

interface MessageBubbleProps {
  message: {
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
  };
  onSendMessage?: (msg: string) => void;
}

interface CardSkeletonProps {
  type: "place" | "hotel" | "flight" | "trip";
}

function CardSkeleton({ type }: CardSkeletonProps) {
  const isWide = type === "trip" || type === "flight";
  return (
    <article
      className={`shrink-0 ${isWide ? "w-[320px]" : "w-[260px]"} rounded-3xl border border-line/40 bg-line/20 overflow-hidden flex flex-col`}
    >
      <div className="h-[170px] bg-gradient-to-r from-line/40 via-line/20 to-line/40 animate-shimmer" />
      <div className="p-4 flex flex-col gap-3 flex-1">
        <div className="h-3 bg-gradient-to-r from-line/40 via-line/20 to-line/40 animate-shimmer w-3/4" />
        <div className="h-1.5 bg-gradient-to-r from-line/40 via-line/20 to-line/40 animate-shimmer w-1/2" />
        <div className="h-1.5 bg-gradient-to-r from-line/40 via-line/20 to-line/40 animate-shimmer w-3/4" />
        <div className="h-1 bg-gradient-to-r from-line/40 via-line/20 to-line/40 animate-shimmer w-1/3" />
      </div>
    </article>
  );
}

export function MessageBubble({ message, onSendMessage }: MessageBubbleProps) {
  const isUser = message.sender === "user";
  const [retryCount, setRetryCount] = useState(0);

  const renderCard = (card: any, idx: number) => {
    const key = `${card.id || card.trip_id || card.name || "card"}-${idx}`;
    if (card.type === "trip_intake") {
      return <TripIntakeCard key={key} card={card} onSubmit={onSendMessage} />;
    }
    if (card.type === "trip" || (card.day_count && card.stop_count)) {
      return <TripCard key={key} card={card} />;
    }
    if (card.type === "flight" || card.airline) {
      return <FlightCard key={key} card={card} />;
    }
    if (card.type === "hotel" || (card.stars != null && card.price_per_night != null)) {
      return <HotelCard key={key} card={card} />;
    }
    return <PlaceCard key={key} card={card} />;
  };

  const handleRetry = () => {
    const promptToRetry = message.retryPrompt || (!message.error ? message.message : "");
    if (onSendMessage && promptToRetry) {
      setRetryCount((c) => c + 1);
      onSendMessage(promptToRetry);
    }
  };

  return (
    <div className={`flex flex-col ${isUser ? "items-end" : "items-start"} mb-6 w-full`}>
      <div
        className={`max-w-[88%] rounded-3xl p-4 px-5 py-3.5 text-sm leading-relaxed shadow-sm ${
          isUser
            ? "bg-ink text-white whitespace-pre-wrap"
            : "bg-white border border-line/80 text-ink/90 font-normal"
        }`}
      >
        {message.error ? (
          <div className="flex items-center gap-2 rounded-lg bg-rose-50 border border-rose-200 px-3 py-2 text-xs text-rose-700">
            <AlertCircle size={14} className="shrink-0" />
            <span>{message.message || message.error}</span>
            {message.retryable && message.retryPrompt && (
              <button
                type="button"
                onClick={handleRetry}
                className="ml-auto inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-white border border-rose-200 text-rose-700 font-semibold hover:bg-rose-100 transition-colors shrink-0"
              >
                <RefreshCw size={12} /> Retry
              </button>
            )}
          </div>
        ) : message.message ? (
          isUser ? (
            message.message
          ) : (
            <MarkdownRenderer content={message.message} />
          )
        ) : message.loading ? (
          <span className="inline-flex items-center gap-1.5 px-2 py-1" aria-label="Thinking">
            <span className="size-2 rounded-full bg-ink/60 typing-dot" />
            <span className="size-2 rounded-full bg-ink/60 typing-dot" />
            <span className="size-2 rounded-full bg-ink/60 typing-dot" />
          </span>
        ) : (
          <span className="text-ink/50">No response</span>
        )}
      </div>
      {message.loading && message.cards && message.cards.length > 0 && !isUser && (
        <div className="mt-3.5 flex w-full max-w-full gap-3 overflow-x-auto thin-scrollbar pb-2 pt-1">
          {message.cards.map((card: any, idx: number) => (
            <CardSkeleton key={`${card.id || card.trip_id || card.name || "card"}-${idx}`} type="place" />
          ))}
        </div>
      )}
      {Boolean(message.cards && message.cards.length > 0 && !message.loading && !isUser) && (
        <div className="mt-3.5 flex w-full max-w-full gap-3 overflow-x-auto thin-scrollbar pb-2 pt-1">
          {message.cards.map((card: any, idx: number) => renderCard(card, idx))}
        </div>
      )}
    </div>
  );
}
