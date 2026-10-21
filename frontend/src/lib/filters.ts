import type { Video } from "../api/videos";
import { localDay } from "./format";

export type VideoFilters = {
  search: string;
  short: "all" | "shorts" | "videos";
  edited: "all" | "edited" | "unedited";
  from: string; // YYYY-MM-DD, inclusive; "" = no bound
  to: string; // YYYY-MM-DD, inclusive; "" = no bound
};

export const DEFAULT_FILTERS: VideoFilters = { search: "", short: "all", edited: "all", from: "", to: "" };

/** Lower-case and strip accents so "cafe" finds "Café". */
function fold(text: string): string {
  return text.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();
}

export function filterVideos(videos: Video[], f: VideoFilters): Video[] {
  const needle = fold(f.search.trim());
  return videos.filter((v) => {
    if (needle && !fold(v.title).includes(needle) && !fold(v.description).includes(needle)) return false;
    if (f.short === "shorts" && v.is_short !== true) return false;
    if (f.short === "videos" && v.is_short !== false) return false;
    if (f.edited === "edited" && !v.edited) return false;
    if (f.edited === "unedited" && v.edited) return false;
    const day = localDay(v.published_at); // the same day the table shows
    if (f.from && day < f.from) return false;
    if (f.to && day > f.to) return false;
    return true;
  });
}

export function isFiltered(f: VideoFilters): boolean {
  return (Object.keys(DEFAULT_FILTERS) as (keyof VideoFilters)[]).some((k) => f[k] !== DEFAULT_FILTERS[k]);
}

