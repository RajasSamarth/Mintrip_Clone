"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { Sparkles, MapPin, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import Footer from "@/components/navigation/Footer";

export default function InspirationPage() {
  const [collections, setCollections] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const res = await api("/inspiration");
        const json = await res.json();
        setCollections(json.collections || []);
      } catch (err) {
        console.warn("Failed to load inspiration:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div className="min-h-screen bg-paper flex flex-col justify-between">
      <div>
        <header className="border-b border-line bg-white/70 backdrop-blur-md sticky top-0 z-20">
          <div className="mx-auto max-w-[1440px] px-5 py-6 sm:px-8">
            <span className="text-xs font-semibold uppercase tracking-widest text-muted">Inspiration</span>
            <h1 className="text-3xl font-serif-italic text-ink sm:text-4xl mt-1">Curated Travel Collections</h1>
            <p className="mt-2 text-sm text-ink/75 max-w-xl">
              Handcrafted itineraries and visual guides inspired by local experts, foodies, and storytellers.
            </p>
          </div>
        </header>

        <main className="mx-auto max-w-[1440px] px-5 py-10 sm:px-8">
          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {[1, 2, 3].map((n) => (
                <div key={n} className="rounded-3xl border border-line bg-white p-4">
                  <div className="shimmer h-64 w-full rounded-2xl mb-4" />
                  <div className="shimmer h-6 w-2/3 rounded-full mb-2" />
                  <div className="shimmer h-4 w-1/3 rounded-full" />
                </div>
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {collections.map((item) => (
                <article
                  key={item.id}
                  className="group rounded-3xl border border-line bg-white overflow-hidden hover:shadow-card transition-all flex flex-col"
                >
                  <div className="relative h-72 w-full overflow-hidden bg-cream">
                    {item.cover_photo && (
                      <Image
                        src={item.cover_photo}
                        alt={item.title}
                        fill
                        className="object-cover group-hover:scale-105 transition-transform duration-500"
                        sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
                      />
                    )}
                    <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/20 to-transparent" />
                    <div className="absolute bottom-4 left-4 right-4">
                      <span className="rounded-full bg-white/90 backdrop-blur px-3 py-1 text-xs font-semibold text-ink capitalize">
                        {item.destination}
                      </span>
                      <h2 className="mt-2 text-2xl font-serif-italic text-white leading-snug">
                        {item.title}
                      </h2>
                    </div>
                  </div>

                  <div className="p-6 flex-1 flex flex-col justify-between">
                    <p className="text-sm leading-relaxed text-ink/75 line-clamp-3 mb-4">
                      {item.summary || item.destination_detail?.description || "A breathtaking escape crafted for unforgettable memories."}
                    </p>
                    <div className="pt-4 border-t border-line flex items-center justify-between">
                      <span className="text-xs text-muted font-medium flex items-center gap-1">
                        <MapPin size={13} /> {item.destination_detail?.country || item.destination}
                      </span>
                      <Link
                        href={`/trip/${item.id}`}
                        className="inline-flex items-center gap-1 text-sm font-semibold text-ink group-hover:translate-x-0.5 transition-transform"
                      >
                        Explore Guide <ArrowRight size={14} />
                      </Link>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </main>
      </div>
      <Footer />
    </div>
  );
}
