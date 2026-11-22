import Link from "next/link";

export function Logo({ light = false, compact = false }: { light?: boolean; compact?: boolean }) {
  return (
    <Link href="/" className={`group inline-flex items-center gap-2 ${light ? "text-white" : "text-ink"}`} aria-label="Mindtrip home">
      <svg viewBox="0 0 24 24" fill="currentColor" className="size-7 transition-transform duration-500 group-hover:rotate-45" aria-hidden="true">
        <path d="M17.991 5.27c1.466-.272 2.314-1.13 2.555-2.575.152 1.392 1.214 2.397 2.533 2.565-1.45.267-2.303 1.12-2.544 2.58a2.862 2.862 0 0 0-.806-1.732 2.887 2.887 0 0 0-1.738-.838ZM1.318 12.877C7.662 11.699 11.332 7.983 12.374 1.73c.657 6.026 5.256 10.375 10.964 11.1C17.063 13.987 13.37 17.68 12.328 24c-.317-2.877-1.45-5.414-3.488-7.499-2.085-2.084-4.6-3.262-7.522-3.624ZM.66 3.434C2.614 3.07 3.745 1.926 4.066 0c.202 1.857 1.62 3.197 3.378 3.42-1.933.356-3.07 1.494-3.392 3.44-.098-.886-.447-1.667-1.075-2.31C2.335 3.909 1.56 3.547.66 3.435Z" />
      </svg>
      {!compact && (
        <span className="text-[22px] font-semibold tracking-[-0.04em]">
          mindtrip
        </span>
      )}
    </Link>
  );
}
