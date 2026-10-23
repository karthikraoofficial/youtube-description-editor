import { useSyncExternalStore } from "react";

/** Whether a CSS media query matches now, re-rendering when that changes. */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const list = window.matchMedia(query);
      list.addEventListener("change", onChange);
      return () => list.removeEventListener("change", onChange);
    },
    () => window.matchMedia(query).matches,
  );
}

/** Below Tailwind's `sm` breakpoint (640 px): phones. */
export const PHONE = "(max-width: 639.98px)";
/** Below Tailwind's `md` breakpoint (768 px): too narrow for two text columns side by side. */
export const NARROW = "(max-width: 767.98px)";
/** Tailwind's `lg` breakpoint (1024 px) and up: room for the sidebar. */
export const DESKTOP = "(min-width: 1024px)";
