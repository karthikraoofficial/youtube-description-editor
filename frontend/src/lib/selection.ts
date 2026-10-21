/** Selected Video ids. Updates are functional so rapid toggles never lose one another. */
export type Selection = ReadonlySet<string>;
export type SelectionUpdate = (update: (prev: Selection) => Selection) => void;

export function toggled(prev: Selection, id: string): Selection {
  const next = new Set(prev);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  return next;
}

export function withMany(prev: Selection, ids: string[], select: boolean): Selection {
  const next = new Set(prev);
  for (const id of ids) {
    if (select) next.add(id);
    else next.delete(id);
  }
  return next;
}

/** Keeps only ids that still exist, returning `prev` itself when nothing changed. */
export function pruned(prev: Selection, existing: ReadonlySet<string>): Selection {
  for (const id of prev) {
    if (!existing.has(id)) return new Set([...prev].filter((x) => existing.has(x)));
  }
  return prev;
}
