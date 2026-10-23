/**
 * A segmented control: one choice out of a few, shown as joined buttons. It's a radio group,
 * so each option has role="radio".
 */
export function Segmented<K extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { id: K; label: string }[];
  value: K;
  onChange: (id: K) => void;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex flex-wrap gap-0.5 rounded-lg border border-line bg-subtle p-0.5">
      {options.map((o) => {
        const checked = o.id === value;
        return (
          <button
            key={o.id}
            type="button"
            role="radio"
            aria-checked={checked}
            onClick={() => onChange(o.id)}
            className={`rounded-md px-3 py-1.5 text-sm ${checked ? "bg-surface font-medium text-fg shadow-card" : "text-muted hover:text-fg"}`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
