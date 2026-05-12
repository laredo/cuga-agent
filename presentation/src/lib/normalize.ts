export function normalizeKeyword(raw: string): string {
  return raw
    .toLowerCase()
    .trim()
    .replace(/[^\p{Letter}\p{Number}\s-]/gu, '')
    .replace(/\s+/g, ' ');
}
