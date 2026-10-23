/** Every screen a signed-in Owner can be on. */
export type Screen = "videos" | "edit" | "review" | "run" | "history";

/** The screens with their own entry in the nav, in nav order. */
export const NAV = [
  { target: "videos", label: "Videos" },
  { target: "history", label: "History" },
] as const satisfies readonly { target: Screen; label: string }[];
export type NavTarget = (typeof NAV)[number]["target"];

/** The nav entry to highlight: Edit and Review belong to Videos, and a Run to wherever it was opened from. */
export function activeNav(screen: Screen, runFrom: NavTarget): NavTarget {
  if (screen === "history") return "history";
  if (screen === "run") return runFrom;
  return "videos";
}

const TITLES: Record<Screen, string> = { videos: "Videos", edit: "Edit", review: "Review", run: "Run", history: "History" };

/** The screen's name, shown in the phone top bar. */
export function screenTitle(screen: Screen): string {
  return TITLES[screen];
}
