/** Tags as the owner types them, separated by commas or on their own lines: trimmed, without blanks. Matching
 * and repeats are the backend's business (ADR-0001). */
export function parseTags(text: string): string[] {
  return text
    .split(/[,\n]/)
    .map((t) => t.trim())
    .filter(Boolean);
}
