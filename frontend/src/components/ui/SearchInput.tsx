import { Search } from "lucide-react";
import type { ComponentProps } from "react";
import { inputClass } from "./inputs";

/** A search box with a magnifier icon. An optional key hint shows on the right on wide screens. */
export function SearchInput({ className = "", hint, ref, ...rest }: ComponentProps<"input"> & { hint?: string }) {
  return (
    <div className={`relative ${className}`}>
      <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
      <input ref={ref} type="search" className={`${inputClass} w-full pl-9 ${hint ? "sm:pr-9" : ""}`} {...rest} />
      {hint && (
        <kbd aria-hidden className="pointer-events-none absolute right-2.5 top-1/2 hidden -translate-y-1/2 rounded border border-line px-1.5 text-xs text-muted sm:block">
          {hint}
        </kbd>
      )}
    </div>
  );
}
