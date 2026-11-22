"use client";

import { useState } from "react";
import Image from "next/image";
import { MapPin, Clock } from "lucide-react";
import Link from "next/link";

const SLOT_LABEL: Record<string, string> = {
  morning: "Morning",
  afternoon: "Afternoon",
  evening: "Evening",
};

interface DayTimelineProps {
  trip: any;
  onStopClick?: (placeId: string) => void;
}

export function DayTimeline({ trip, onStopClick }: DayTimelineProps) {
  const [activeDay, setActiveDay] = useState(1);

  const day = trip?.days?.find((d: any) => d.day_index === activeDay) ?? trip?.days?.[0];

  return (
    <div className="space-y-8">
      <div className="flex items-baseline justify-between mb-6">
        <div>
          <h2 className="text-2xl font-serif-italic tracking-tight">Day-by-day</h2>
          <p className="text-sm text-muted">Tap a day to jump to it</p>
        </div>
        <div className="flex gap-2 overflow-x-auto thin-scrollbar pb-1 no-scrollbar">
          {trip.days?.map((d: any) => (
            <button
              key={d.day_index}
              onClick={() => setActiveDay(d.day_index)}
              className={`shrink-0 rounded-full border px-4 py-1.5 text-sm font-medium transition-all ${
                activeDay === d.day_index
                  ? "bg-ink border-ink text-white"
                  : "bg-white border-line text-ink/70 hover:bg-ink/5"
              }`}
            >
              Day {d.day_index}
            </button>
          ))}
        </div>
      </div>

      {day && (
        <section className="space-y-3">
          <h3 className="mb-3 text-lg font-semibold text-ink">
            Day {day.day_index} · {day.date}
          </h3>
          <p className="mb-4 text-sm leading-relaxed text-ink/75">{day.summary}</p>
          <div className="space-y-3">
            {day.stops.map((stop: any, i: number) => {
              const place = stop.place;
              return (
                <article
                  key={stop.id}
                  onClick={() => place?.id && onStopClick?.(place.id)}
                  className={`cursor-pointer flex gap-3 rounded-2xl border p-3 transition-all hover:bg-ink/2 ${
                    i === 0 ? "border-l-4 border-l-ink" : "border-line"
                  }`}
                >
                  <div className="shrink-0 rounded-full border border-line bg-white p-1 text-ink/60 flex items-center justify-center">
                    <span className="text-[10px] font-semibold">{i + 1}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="text-xs font-semibold uppercase tracking-wider text-muted">
                        {SLOT_LABEL[stop.time_slot]}
                      </span>
                      <span className="text-xs font-medium text-ink">{stop.arrival_time}</span>
                      <span className="rounded-full border border-line px-2 py-0.5 text-[10px] font-medium text-muted">
                        {stop.duration_mins} min
                      </span>
                    </div>
                    <h4 className="text-base font-semibold text-ink leading-tight">{place?.name || "Stop"}</h4>
                    <p className="text-xs text-ink/70">
                      {place?.category ? place.category.charAt(0).toUpperCase() + place.category.slice(1) : ""}
                    </p>
                    <p className="mt-1 text-sm leading-relaxed text-ink/75">
                      {stop.notes || place?.description || ""}
                    </p>
                    {stop.transit_info && (
                      <div className="mt-2 flex items-center gap-1 text-[11px] font-medium text-muted">
                        <Clock size={12} /> {stop.transit_info}
                      </div>
                    )}
                  </div>
                  <div className="ml-2 shrink-0 w-10 h-10 rounded-full border border-line bg-white flex items-center justify-center text-[10px] font-semibold text-ink overflow-hidden">
                    {place?.photos?.[0] ? (
                      <Image
                        src={place.photos[0]}
                        alt={place.name}
                        className="rounded-full object-cover"
                        width={40}
                        height={40}
                        style={{ width: "auto", height: "auto" }}
                      />
                    ) : (
                      place?.category ? place.category.charAt(0).toUpperCase() : "?"
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
