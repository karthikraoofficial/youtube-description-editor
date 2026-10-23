/** A small rounded number beside a label, as on tabs and the Filter button. */
export function Count({ value, active = false }: { value: number; active?: boolean }) {
  return <span className={`rounded-full px-1.5 text-xs tabular-nums ${active ? "bg-accent/10 text-accent" : "bg-subtle"}`}>{value}</span>;
}
