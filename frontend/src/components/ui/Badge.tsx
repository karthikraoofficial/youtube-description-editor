import type { ComponentProps } from "react";
import type { Tone } from "./tone";

const TONE: Record<Tone, string> = {
  neutral: "border-line bg-subtle text-muted",
  accent: "border-accent/25 bg-accent/10 text-accent",
  ok: "border-ok/25 bg-ok/10 text-ok",
  warn: "border-warn/25 bg-warn/10 text-warn",
  danger: "border-danger/25 bg-danger/10 text-danger",
};

/** A small tinted pill for a status or label. */
export function Badge({ tone = "neutral", className = "", children, ...rest }: ComponentProps<"span"> & { tone?: Tone; "data-fake-badge"?: boolean }) {
  return (
    <span {...rest} className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md border px-2 py-0.5 text-xs font-medium ${TONE[tone]} ${className}`}>
      {children}
    </span>
  );
}
