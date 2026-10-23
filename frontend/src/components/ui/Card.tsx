import type { ComponentProps } from "react";

/** A white panel on the grey canvas. */
export function Card({ className = "", ...rest }: ComponentProps<"div">) {
  return <div className={`rounded-xl border border-line bg-surface shadow-card ${className}`} {...rest} />;
}
