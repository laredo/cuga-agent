export type LayoutKind =
  | 'agentShift'
  | 'centered'
  | 'left'
  | 'split'
  | 'grid'
  | 'code'
  | 'fullbleed'
  | 'live'
  | 'editor'
  | 'fallback';

export type Element =
  | { kind: 'headline'; text: string }
  | { kind: 'body'; text: string }
  | { kind: 'quote'; text: string; cite?: string }
  | { kind: 'bullets'; items: string[] }
  | { kind: 'code'; language: string; source: string; highlight?: number[] }
  | { kind: 'figure'; svg: string; caption?: string }
  | { kind: 'panel'; title: string; body: string; tag?: string; icon?: string }
  | { kind: 'chips'; items: string[] };

export type Slide = {
  id: string;
  aliases: string[];
  layout: LayoutKind;
  elements: Element[];
};
