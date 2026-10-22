import { useEffect, useRef } from "react";
import { DEFAULT_FILTERS, type VideoFilters, isFiltered } from "../lib/filters";

type Props = { filters: VideoFilters; onChange: (f: VideoFilters) => void };

const field =
  "rounded-md border border-line bg-surface px-2.5 py-1.5 text-sm";

export function VideoFiltersBar({ filters, onChange }: Props) {
  const search = useRef<HTMLInputElement>(null);
  const set = <K extends keyof VideoFilters>(key: K, value: VideoFilters[K]) => onChange({ ...filters, [key]: value });

  // "/" focuses search, like most list UIs.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = (e.target as HTMLElement).closest("input,textarea,select");
      if (e.key === "/" && !typing) {
        e.preventDefault();
        search.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="mb-3 flex flex-wrap items-center gap-2">
      <input
        ref={search}
        type="search"
        value={filters.search}
        onChange={(e) => set("search", e.target.value)}
        placeholder="Search titles and descriptions  ( / )"
        aria-label="Search titles and descriptions"
        className={`${field} min-w-64 flex-1`}
      />
      <select
        value={filters.short}
        onChange={(e) => set("short", e.target.value as VideoFilters["short"])}
        aria-label="Shorts filter"
        className={field}
      >
        <option value="all">Shorts and videos</option>
        <option value="shorts">Shorts only</option>
        <option value="videos">Videos only</option>
      </select>
      <select
        value={filters.edited}
        onChange={(e) => set("edited", e.target.value as VideoFilters["edited"])}
        aria-label="Edited filter"
        className={field}
      >
        <option value="all">Any status</option>
        <option value="edited">Edited</option>
        <option value="unedited">Not edited</option>
      </select>
      <label className="flex items-center gap-1.5 text-sm text-muted">
        From
        <input type="date" value={filters.from} max={filters.to || undefined} onChange={(e) => set("from", e.target.value)} className={field} />
      </label>
      <label className="flex items-center gap-1.5 text-sm text-muted">
        To
        <input type="date" value={filters.to} min={filters.from || undefined} onChange={(e) => set("to", e.target.value)} className={field} />
      </label>
      {isFiltered(filters) && (
        <button type="button" onClick={() => onChange(DEFAULT_FILTERS)} className="px-2 py-1.5 text-sm text-accent hover:underline">
          Clear filters
        </button>
      )}
    </div>
  );
}
