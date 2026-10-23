import { describe, expect, it } from "vitest";
import type { Video } from "../api/videos";
import { DEFAULT_FILTERS, filterVideos, activeFilterCount, isFiltered } from "./filters";
import { descriptionPreview } from "./format";

const v = (over: Partial<Video>): Video => ({
  id: "x",
  title: "Untitled",
  description: "",
  tags: [],
  published_at: "2025-01-01T00:00:00Z",
  duration_s: 300,
  thumbnail_url: null,
  is_short: false,
  short_source: "probe",
  edited: false,
  ...over,
});

const videos = [
  v({ id: "a", title: "Late Night Jam", description: "Listen: https://old.link", published_at: "2025-03-10T18:00:00Z" }),
  v({ id: "b", title: "#Shorts riff", is_short: true, published_at: "2025-05-01T18:00:00Z", edited: true }),
  v({ id: "c", title: "Café Session", description: "no links here", published_at: "2026-01-02T18:00:00Z" }),
  v({ id: "d", title: "Unclassified", is_short: null, published_at: "2026-02-01T18:00:00Z" }),
];

const ids = (vs: Video[]) => vs.map((x) => x.id);

describe("filterVideos", () => {
  it("returns everything with the default filters", () => {
    expect(ids(filterVideos(videos, DEFAULT_FILTERS))).toEqual(["a", "b", "c", "d"]);
  });

  it("searches titles and descriptions, ignoring case and accents", () => {
    expect(ids(filterVideos(videos, { ...DEFAULT_FILTERS, search: "OLD.LINK" }))).toEqual(["a"]);
    expect(ids(filterVideos(videos, { ...DEFAULT_FILTERS, search: "cafe" }))).toEqual(["c"]);
    expect(ids(filterVideos(videos, { ...DEFAULT_FILTERS, search: "  jam  " }))).toEqual(["a"]);
  });

  it("filters Shorts and non-Shorts; unclassified Videos only appear under 'all'", () => {
    expect(ids(filterVideos(videos, { ...DEFAULT_FILTERS, short: "shorts" }))).toEqual(["b"]);
    expect(ids(filterVideos(videos, { ...DEFAULT_FILTERS, short: "videos" }))).toEqual(["a", "c"]);
  });

  it("filters by publish date range, inclusive of both days", () => {
    const f = { ...DEFAULT_FILTERS, from: "2025-05-01", to: "2026-01-02" };
    expect(ids(filterVideos(videos, f))).toEqual(["b", "c"]);
  });

  it("filters by edited status", () => {
    expect(ids(filterVideos(videos, { ...DEFAULT_FILTERS, edited: "edited" }))).toEqual(["b"]);
    expect(ids(filterVideos(videos, { ...DEFAULT_FILTERS, edited: "unedited" }))).toEqual(["a", "c", "d"]);
  });

  it("combines filters", () => {
    const f = { ...DEFAULT_FILTERS, search: "session", short: "videos" as const, from: "2026-01-01" };
    expect(ids(filterVideos(videos, f))).toEqual(["c"]);
  });
});

describe("isFiltered", () => {
  it("is false only for the defaults", () => {
    expect(isFiltered(DEFAULT_FILTERS)).toBe(false);
    expect(isFiltered({ ...DEFAULT_FILTERS, to: "2026-01-01" })).toBe(true);
  });
});

describe("descriptionPreview", () => {
  it("uses the first non-empty line", () => {
    expect(descriptionPreview("\n\n  First line  \nSecond")).toBe("First line");
    expect(descriptionPreview("")).toBe("");
  });
});

describe("activeFilterCount", () => {
  it("counts the filters folded behind the phone Filter button, not the search box", () => {
    expect(activeFilterCount(DEFAULT_FILTERS)).toBe(0);
    expect(activeFilterCount({ ...DEFAULT_FILTERS, search: "late" })).toBe(0);
    expect(activeFilterCount({ ...DEFAULT_FILTERS, short: "shorts", edited: "edited" })).toBe(2);
  });

  it("counts a date range as one filter", () => {
    expect(activeFilterCount({ ...DEFAULT_FILTERS, from: "2026-01-01" })).toBe(1);
    expect(activeFilterCount({ ...DEFAULT_FILTERS, from: "2026-01-01", to: "2026-02-01" })).toBe(1);
  });
});
