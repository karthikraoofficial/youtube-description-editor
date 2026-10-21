/** Page `page` of `size` ids, wrapping around the end; the whole list if it's smaller than a page. */
export function sampleIds(ids: readonly string[], page: number, size: number): string[] {
  if (ids.length <= size) return [...ids];
  const start = (page * size) % ids.length;
  return Array.from({ length: size }, (_, i) => ids[(start + i) % ids.length]);
}
