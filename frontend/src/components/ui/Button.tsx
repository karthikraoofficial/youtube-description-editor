import type { ComponentProps, ReactNode } from "react";

export type ButtonVariant = "primary" | "outline" | "ghost" | "danger";

const VARIANT: Record<ButtonVariant, string> = {
  primary: "bg-accent text-on-accent shadow-card hover:opacity-90",
  outline: "border border-line bg-surface text-fg shadow-card hover:bg-subtle",
  ghost: "text-muted hover:bg-subtle hover:text-fg",
  danger: "bg-danger text-on-accent shadow-card hover:opacity-90 focus-visible:outline-danger",
};

const SIZE = {
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
