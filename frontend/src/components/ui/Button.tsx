import type { ComponentProps, ReactNode } from "react";

export type ButtonVariant = "primary" | "outline" | "accent-outline" | "danger-outline" | "ghost" | "link" | "danger";

/** Each variant's colours; nav links that look like ghost buttons reuse them. */
export const VARIANT: Record<ButtonVariant, string> = {
  primary: "bg-accent text-on-accent shadow-card hover:opacity-90",
  outline: "border border-line bg-surface text-fg shadow-card hover:bg-subtle",
  /** Outlined in the accent colour: a secondary action that still matters, like Restore. */
  "accent-outline": "border border-accent/40 bg-surface text-accent shadow-card hover:bg-accent/10",
  /** Outlined in red: stops or discards something, like Cancel. */
  "danger-outline": "border border-danger/40 bg-surface text-danger shadow-card hover:bg-danger/10 focus-visible:outline-danger",
  ghost: "text-muted hover:bg-subtle hover:text-fg",
  /** Accent text with no frame, for in-line actions like "Back to videos". */
  link: "text-accent hover:bg-accent/10",
  danger: "bg-danger text-on-accent shadow-card hover:opacity-90 focus-visible:outline-danger",
};

const SIZE = {
  /** For an in-line action inside a list row. */
  xs: "h-7 gap-1 px-2 text-xs",
  sm: "h-8 gap-1.5 px-3 text-sm",
  md: "h-9 gap-2 px-4 text-sm",
  /** A square button holding only an icon; give it an aria-label. */
  icon: "size-9",
} as const;

/** Every button in the app: pick a variant instead of writing classes. */
export function buttonClass(variant: ButtonVariant = "outline", size: keyof typeof SIZE = "md") {
  return `inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${VARIANT[variant]} ${SIZE[size]}`;
}

type Props = ComponentProps<"button"> & {
  variant?: ButtonVariant;
  size?: keyof typeof SIZE;
  /** An icon shown before the label. */
  icon?: ReactNode;
};

export function Button({ variant, size, icon, className = "", type = "button", children, ...rest }: Props) {
  return (
    <button type={type} className={`${buttonClass(variant, size)} ${className}`} {...rest}>
      {icon}
      {children}
    </button>
  );
}
