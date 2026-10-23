import { ListFilter, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { DEFAULT_FILTERS, type VideoFilters, activeFilterCount, isFiltered } from "../lib/filters";
import { PHONE, useMediaQuery } from "../lib/useMediaQuery";
import { Button } from "./ui/Button";
import { Count } from "./ui/Count";
import { inputClass } from "./ui/inputs";
import { SearchInput } from "./ui/SearchInput";

type Props = { filters: VideoFilters; onChange: (f: VideoFilters) => void };

/** Search plus the Short, edited and date filters. On a phone the filters fold behind a Filter button. */
export function VideoFiltersBar({ filters, onChange }: Props) {
  const search = useRef<HTMLInputElement>(null);
  const phone = useMediaQuery(PHONE);
  const [open, setOpen] = useState(false);
  // Fold again whenever the width crosses the phone breakpoint.
  useEffect(() => setOpen(false), [phone]);
  const set = <K extends keyof VideoFilters>(key: K, value: VideoFilters[K]) => onChange({ ...filters, [key]: value });
  const count = activeFilterCount(filters);

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

  const showFilters = !phone || open;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <SearchInput
        ref={search}
        value={filters.search}
        onChange={(e) => set("search", e.target.value)}
        placeholder="Search titles and descriptions"
        aria-label="Search titles and descriptions"
        hint="/"
        className="min-w-0 flex-1 sm:min-w-56 sm:max-w-sm"
      />
      {phone && (
        <Button
          icon={<ListFilter aria-hidden className="size-4" />}
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-controls={open ? "video-filters" : undefined}
        >
          Filter
          {count > 0 && (
            <>
              <span aria-hidden>
                <Count value={count} active />
              </span>
              <span className="sr-only"> ({count} on)</span>
            </>
          )}
        </Button>
      )}
      {showFilters && (
        <div id="video-filters" className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <select
            value={filters.short}
            onChange={(e) => set("short", e.target.value as VideoFilters["short"])}
            aria-label="Shorts filter"
            className={inputClass}
          >
            <option value="all">Shorts and videos</option>
            <option value="shorts">Shorts only</option>
            <option value="videos">Videos only</option>
          </select>
          <select
            value={filters.edited}
            onChange={(e) => set("edited", e.target.value as VideoFilters["edited"])}
            aria-label="Edited filter"
            className={inputClass}
          >
            <option value="all">Any status</option>
            <option value="edited">Edited</option>
            <option value="unedited">Not edited</option>
          </select>
          <label className="flex items-center gap-1.5 text-sm text-muted">
            From
            <input type="date" value={filters.from} max={filters.to || undefined} onChange={(e) => set("from", e.target.value)} className={inputClass} />
          </label>
          <label className="flex items-center gap-1.5 text-sm text-muted">
            To
            <input type="date" value={filters.to} min={filters.from || undefined} onChange={(e) => set("to", e.target.value)} className={inputClass} />
          </label>
        </div>
      )}
      {isFiltered(filters) && (
        <Button variant="ghost" size="sm" icon={<X aria-hidden className="size-3.5" />} onClick={() => onChange(DEFAULT_FILTERS)}>
          Clear filters
        </Button>
      )}
    </div>
  );
}
