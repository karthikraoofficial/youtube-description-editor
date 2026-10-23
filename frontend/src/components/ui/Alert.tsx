import type { ComponentProps } from "react";

export const ALERT_TONE = {
  danger: "border-danger/25 bg-danger/10 text-danger",
  warn: "border-warn/25 bg-warn/10 text-warn",
} as const;

const SIZE = {
  md: "px-3 py-2 text-sm",
  /** For a flag inside a card. */
  sm: "px-2.5 py-1.5 text-xs",
  /** For a whole panel's worth of message. */
  lg: "p-8 text-center text-sm",
} as const;

/** A tinted box for a warning or an error. Pass role="alert" when it appears in response to something. */
export function Alert({
  tone,
  size = "md",
  className = "",
  ...rest
}: ComponentProps<"div"> & { tone: keyof typeof ALERT_TONE; size?: keyof typeof SIZE }) {
  return <div className={`rounded-lg border ${SIZE[size]} ${ALERT_TONE[tone]} ${className}`} {...rest} />;
}
