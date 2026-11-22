"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("App error:", error);
  }, [error]);

  return (
    <div className="min-h-[50vh] flex flex-col items-center justify-center p-6 text-center">
      <h2 className="text-xl font-bold mb-2">Something went wrong</h2>
      <p className="text-sm text-stone-500 mb-4">{error?.message || "Unexpected error"}</p>
      <button
        onClick={() => reset()}
        className="px-4 py-2 bg-stone-900 text-white rounded-full text-sm font-semibold"
      >
        Try again
      </button>
    </div>
  );
}
