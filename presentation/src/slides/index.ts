import { normalizeKeyword } from '../lib/normalize';
import { slides, CLEAR_KEYWORDS } from './content';
import type { Slide } from './types';

const byKey = new Map<string, Slide>();
const canonicalKeys = new Set<string>();
for (const slide of slides) {
  const canonical = normalizeKeyword(slide.id);
  byKey.set(canonical, slide);
  canonicalKeys.add(canonical);
}
for (const slide of slides) {
  for (const alias of slide.aliases) {
    const key = normalizeKeyword(alias);
    if (!canonicalKeys.has(key) && !byKey.has(key)) {
      byKey.set(key, slide);
    }
  }
}

export type ResolveResult =
  | { kind: 'slide'; slide: Slide }
  | { kind: 'clear' }
  | { kind: 'unknown'; keyword: string };

export function resolve(raw: string): ResolveResult {
  const key = normalizeKeyword(raw);
  if (!key) return { kind: 'clear' };
  if (CLEAR_KEYWORDS.has(key)) return { kind: 'clear' };
  const hit = byKey.get(key);
  if (hit) return { kind: 'slide', slide: hit };
  return { kind: 'unknown', keyword: raw };
}

export function authoredKeywords(): { canonical: string; aliases: string[] }[] {
  return slides.map((s) => ({ canonical: s.id, aliases: s.aliases }));
}
