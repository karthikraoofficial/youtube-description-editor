import type { ComponentProps } from "react";

const TONE = {
  plain: "border-line bg-surface",
  /** Something in it needs attention before going on. */
  danger: "border-danger/25 bg-danger/5",
} as const;

/** A white panel on the grey canvas. */
export function Card({ tone = "plain", className = "", ...rest }: ComponentProps<"div"> & { tone?: keyof typeof TONE }) {
  return <div className={`rounded-xl border shadow-card ${TONE[tone]} ${className}`} {...rest} />;
}
