import { AnimatePresence, motion } from 'framer-motion';
import { useEffect, useMemo, useState } from 'react';
import { slideChild, slideContainer } from '../../lib/motion';
import { parseSkill, type SkillSections } from '../../lib/parseSkill';
import { Body, Headline, Quote } from './Elements';
import type { Slide } from '../../slides/types';

const FONT_SIZE = 14;
const LINE_HEIGHT = 24;
const PAD_X = 20;
const PAD_Y = 16;

type SectionKey = 'trigger' | 'effects' | 'prompt';
type Chunk = {
  id: string;
  section: SectionKey | null;
  text: string;
  lineCount: number;
};

const SECTION_META: Record<
  SectionKey,
  { label: string; bg: string; text: string; stroke: string }
> = {
  trigger: {
    label: 'trigger',
    bg: 'rgba(125, 211, 252, 0.10)',
    text: 'rgb(186, 230, 253)',
    stroke: 'rgb(125, 211, 252)',
  },
  effects: {
    label: 'effects',
    bg: 'rgba(196, 181, 253, 0.10)',
    text: 'rgb(221, 214, 254)',
    stroke: 'rgb(196, 181, 253)',
  },
  prompt: {
    label: 'skill body',
    bg: 'rgba(252, 211, 77, 0.07)',
    text: 'rgb(253, 224, 71)',
    stroke: 'rgb(252, 211, 77)',
  },
};

export default function Code({ slide }: { slide: Slide }) {
  const headline = slide.elements.find((e) => e.kind === 'headline');
  const code = slide.elements.find((e) => e.kind === 'code');
  const caption = slide.elements.find(
    (e) => e.kind === 'body' || e.kind === 'quote',
  );
  return (
    <motion.div
      key={slide.id}
      variants={slideContainer}
      initial="initial"
      animate="enter"
      exit="exit"
      className="h-full w-full overflow-hidden flex flex-col items-center justify-start gap-3 px-[4vw] pt-[3vh] pb-[2vh]"
    >
      {headline?.kind === 'headline' && (
        <Headline text={headline.text} compact />
      )}
      {code?.kind === 'code' && <SkillCode source={code.source} />}
      {caption?.kind === 'body' && <Body text={caption.text} compact />}
      {caption?.kind === 'quote' && (
        <Quote text={caption.text} cite={caption.cite} />
      )}
    </motion.div>
  );
}

function SkillCode({ source }: { source: string }) {
  const [stage, setStage] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    const requested = params.get('skillStage');
    return requested ? Math.max(0, Math.min(2, Number(requested))) : 0;
  });
  const displaySource = useMemo(
    () => buildSkillStageSource(source, stage),
    [source, stage],
  );
  const sections = parseSkill(displaySource);
  const totalLines = displaySource.split('\n').length;
  const contentHeight = totalLines * LINE_HEIGHT + 2 * PAD_Y;
  const chunks = useMemo(() => chunkBySection(source, parseSkill(source)), [
    source,
  ]);

  function advance({ refocusInput = false } = {}) {
    setStage((current) => Math.min(2, current + 1));
    if (refocusInput) {
      requestAnimationFrame(() => {
        document.querySelector<HTMLInputElement>('input[type="text"]')?.focus();
      });
    }
  }

  useEffect(() => {
    if (stage >= 2) return;

    function onKeyDown(event: KeyboardEvent) {
      const target = event.target;
      if (
        event.key === 'Enter' &&
        (target instanceof HTMLInputElement ||
          target instanceof HTMLTextAreaElement)
      ) {
        return;
      }
      if (
        event.key === ' ' ||
        event.key === 'Enter' ||
        event.key === 'ArrowRight' ||
        event.key === 'ArrowDown' ||
        event.key === 'PageDown'
      ) {
        event.preventDefault();
        event.stopPropagation();
        advance();
      }
    }

    window.addEventListener('keydown', onKeyDown, { capture: true });
    return () =>
      window.removeEventListener('keydown', onKeyDown, { capture: true });
  }, [stage]);

  return (
    <motion.div
      variants={slideChild}
      className="w-full max-w-[94ch]"
    >
      <div
        role="button"
        tabIndex={-1}
        onClick={() => advance({ refocusInput: true })}
        className="flex h-[min(52vh,30rem)] w-full overflow-auto rounded-lg bg-white/[0.03] text-left ring-1 ring-white/10 outline-none"
        aria-label="Reveal skill trigger and effects"
      >
        <BraceColumn sections={sections} totalHeight={contentHeight} />
        <motion.div
          layout
          transition={{ duration: 0.42, ease: [0.22, 1, 0.36, 1] }}
          className="flex-1 min-w-0 font-mono whitespace-pre-wrap break-normal"
          style={{
            minHeight: contentHeight,
            fontSize: FONT_SIZE,
            lineHeight: `${LINE_HEIGHT}px`,
            padding: `${PAD_Y}px ${PAD_X}px`,
            color: 'rgba(245, 245, 240, 0.92)',
          }}
        >
          <AnimatePresence initial={false}>
            {chunks.map((chunk) =>
              isChunkVisible(chunk.section, stage) ? (
                <CodeChunk key={chunk.id} chunk={chunk} />
              ) : null,
            )}
          </AnimatePresence>
        </motion.div>
      </div>
      <div className="mt-3 flex justify-center gap-2">
        {[0, 1, 2].map((step) => (
          <span
            key={step}
            className={`h-1.5 w-8 rounded-full transition-colors ${step <= stage ? 'bg-accent/70' : 'bg-white/10'
              }`}
          />
        ))}
      </div>
    </motion.div>
  );
}

function isChunkVisible(section: SectionKey | null, stage: number): boolean {
  if (section === 'trigger') return stage >= 1;
  if (section === 'effects') return stage >= 2;
  return true;
}

function buildSkillStageSource(source: string, stage: number): string {
  const originalSections = parseSkill(source);
  const lines = source.split('\n');

  return lines
    .filter((_, index) => {
      if (
        stage < 1 &&
        originalSections.trigger &&
        index >= originalSections.trigger.start &&
        index <= originalSections.trigger.end
      ) {
        return false;
      }
      if (
        stage < 2 &&
        originalSections.effects &&
        index >= originalSections.effects.start &&
        index <= originalSections.effects.end
      ) {
        return false;
      }
      return true;
    })
    .join('\n');
}

function chunkBySection(source: string, sections: SkillSections): Chunk[] {
  const lines = source.split('\n');

  function sectionAt(i: number): SectionKey | null {
    if (
      sections.trigger &&
      i >= sections.trigger.start &&
      i <= sections.trigger.end
    )
      return 'trigger';
    if (
      sections.effects &&
      i >= sections.effects.start &&
      i <= sections.effects.end
    )
      return 'effects';
    if (
      sections.prompt &&
      i >= sections.prompt.start &&
      i <= sections.prompt.end
    )
      return 'prompt';
    return null;
  }

  const chunks: Chunk[] = [];
  if (lines.length === 0) return chunks;

  let startIdx = 0;
  let current = sectionAt(0);
  for (let i = 1; i < lines.length; i++) {
    const next = sectionAt(i);
    if (next !== current) {
      chunks.push(makeChunk(startIdx, i, current, lines));
      startIdx = i;
      current = next;
    }
  }
  chunks.push(makeChunk(startIdx, lines.length, current, lines));
  return chunks;
}

function makeChunk(
  start: number,
  end: number,
  section: SectionKey | null,
  lines: string[],
): Chunk {
  return {
    id: `${section ?? 'plain'}-${start}-${end}`,
    section,
    text: lines.slice(start, end).join('\n'),
    lineCount: end - start,
  };
}

function CodeChunk({ chunk }: { chunk: Chunk }) {
  const meta = chunk.section ? SECTION_META[chunk.section] : null;
  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 24, height: 0 }}
      animate={{
        opacity: 1,
        x: 0,
        height: chunk.lineCount * LINE_HEIGHT,
      }}
      exit={{ opacity: 0, x: 16, height: 0 }}
      transition={{ duration: 0.42, ease: [0.22, 1, 0.36, 1] }}
      style={{
        overflow: 'hidden',
        backgroundColor: meta?.bg,
        boxDecorationBreak: 'clone',
        WebkitBoxDecorationBreak: 'clone',
      }}
    >
      {chunk.text}
    </motion.div>
  );
}

function BraceColumn({
  sections,
  totalHeight,
}: {
  sections: SkillSections;
  totalHeight: number;
}) {
  const WIDTH = 122;
  const ARM = 6;
  const BRACE_X = WIDTH - 6;
  const LABEL_X = BRACE_X - 10;

  const entries: { key: SectionKey; start: number; end: number }[] = [];
  (['trigger', 'effects', 'prompt'] as const).forEach((key) => {
    const range = sections[key];
    if (range) entries.push({ key, start: range.start, end: range.end });
  });

  return (
    <div
      className="relative shrink-0 border-r border-white/5"
      style={{ width: WIDTH, minHeight: totalHeight }}
    >
      <svg
        className="absolute left-0 top-0"
        style={{
          width: WIDTH,
          height: totalHeight,
          fontFamily: 'JetBrains Mono, ui-monospace, monospace',
        }}
        overflow="visible"
      >
        {entries.map(({ key, start, end }) => {
          const top = PAD_Y + start * LINE_HEIGHT + 2;
          const bottom = PAD_Y + (end + 1) * LINE_HEIGHT - 2;
          const mid = (top + bottom) / 2;
          const meta = SECTION_META[key];
          return (
            <g key={key}>
              <line
                x1={BRACE_X}
                y1={top}
                x2={BRACE_X}
                y2={bottom}
                stroke={meta.stroke}
                strokeWidth={1.3}
              />
              <line
                x1={BRACE_X}
                y1={top}
                x2={BRACE_X + ARM}
                y2={top}
                stroke={meta.stroke}
                strokeWidth={1.3}
              />
              <line
                x1={BRACE_X}
                y1={bottom}
                x2={BRACE_X + ARM}
                y2={bottom}
                stroke={meta.stroke}
                strokeWidth={1.3}
              />
              <line
                x1={BRACE_X}
                y1={mid}
                x2={BRACE_X - 8}
                y2={mid}
                stroke={meta.stroke}
                strokeWidth={1.3}
              />
              <text
                x={LABEL_X}
                y={mid}
                fill={meta.text}
                dominantBaseline="central"
                textAnchor="end"
                fontSize={11}
                letterSpacing="0.12em"
                style={{ textTransform: 'uppercase' }}
              >
                {meta.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
