import { type KeyboardEvent, type ReactNode, useRef } from "react";

type Tab<K extends string> = { id: K; label: ReactNode; count?: number };

/**
 * An underline tab bar. The caller renders the chosen tab's panel with `role="tabpanel"` and
 * `aria-labelledby={tabId(idPrefix, value)}`. Left/Right/Home/End move between tabs.
 */
export function Tabs<K extends string>({
  tabs,
  value,
  onChange,
  label,
  idPrefix,
  className = "",
}: {
  tabs: Tab<K>[];
  value: K;
  onChange: (id: K) => void;
  label: string;
  idPrefix: string;
  className?: string;
}) {
  const refs = useRef(new Map<K, HTMLButtonElement>());
  const onKeyDown = (e: KeyboardEvent) => {
    const i = tabs.findIndex((t) => t.id === value);
    const next =
      e.key === "ArrowRight" ? (i + 1) % tabs.length
      : e.key === "ArrowLeft" ? (i - 1 + tabs.length) % tabs.length
      : e.key === "Home" ? 0
      : e.key === "End" ? tabs.length - 1
      : -1;
    if (next < 0) return;
    e.preventDefault();
    onChange(tabs[next].id);
    refs.current.get(tabs[next].id)?.focus();
  };
  return (
    <div role="tablist" aria-label={label} onKeyDown={onKeyDown} className={`flex flex-wrap gap-x-5 border-b border-line ${className}`}>
      {tabs.map((t) => {
        const active = t.id === value;
        return (
          <button
            key={t.id}
            ref={(el) => {
              if (el) refs.current.set(t.id, el);
              else refs.current.delete(t.id);
            }}
            id={tabId(idPrefix, t.id)}
            type="button"
            role="tab"
            aria-selected={active}
            aria-controls={panelId(idPrefix)}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(t.id)}
            className={`-mb-px inline-flex items-center gap-1.5 border-b-2 py-2.5 text-sm font-medium ${
              active ? "border-accent text-accent" : "border-transparent text-muted hover:text-fg"
            }`}
          >
            {t.label}
            {t.count !== undefined && (
              <span className={`rounded-full px-1.5 text-xs tabular-nums ${active ? "bg-accent/10" : "bg-subtle"}`}>{t.count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

export const tabId = (prefix: string, id: string) => `${prefix}-tab-${id}`;
export const panelId = (prefix: string) => `${prefix}-panel`;
