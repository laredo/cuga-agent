import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type Fragment as FragmentType,
} from 'react';
import { Fragment } from 'react';
import { motion } from 'framer-motion';
import { useSidecarSkills } from '../../lib/useSkills';
import { templates } from '../../lib/skill-templates';
import { parseSkill, type SkillSections } from '../../lib/parseSkill';

// Fixed font/line geometry so brace math doesn't require measurement.
const FONT_SIZE = 14;
const LINE_HEIGHT = 24;
const PAD_X = 20;
const PAD_Y = 16;

type SectionKey = 'trigger' | 'effects' | 'prompt';

const SECTION_META: Record<
  SectionKey,
  { label: string; bg: string; text: string; stroke: string }
> = {
  trigger: {
    label: 'trigger',
    bg: 'rgba(125, 211, 252, 0.10)', // sky-300 at 10%
    text: 'rgb(186, 230, 253)', // sky-200
    stroke: 'rgb(125, 211, 252)', // sky-300
  },
  effects: {
    label: 'effects',
    bg: 'rgba(196, 181, 253, 0.10)', // violet-300 at 10%
    text: 'rgb(221, 214, 254)', // violet-200
    stroke: 'rgb(196, 181, 253)', // violet-300
  },
  prompt: {
    label: 'skill body',
    bg: 'rgba(252, 211, 77, 0.07)', // amber-300 at 7%
    text: 'rgb(253, 224, 71)', // amber-300 a bit brighter
    stroke: 'rgb(252, 211, 77)', // amber-300
  },
};

// Module-scoped so edits survive the AnimatePresence unmount when the
// presenter navigates away from the editor slide and returns. Lost on a
// full page reload, which is fine.
let memory: { source: string; selected: string | null } = {
  source: '',
  selected: null,
};

export default function Editor() {
  const sidecar = useSidecarSkills();
  const [source, setSourceState] = useState(memory.source);
  const [selected, setSelectedState] = useState<string | null>(
    memory.selected,
  );

  function setSource(next: string) {
    memory = { ...memory, source: next };
    setSourceState(next);
  }
  function setSelected(next: string | null) {
    memory = { ...memory, selected: next };
    setSelectedState(next);
  }

  // First-ever open: load the first template so the editor starts
  // populated. On subsequent visits, memory is already primed.
  useEffect(() => {
    if (selected === null && source === '' && templates.length > 0) {
      const first = templates[0];
      setSelected(`template:${first.name}`);
      setSource(first.source);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function loadSidecar(name: string) {
    const s = sidecar.skills.find((x) => x.name === name);
    if (!s) return;
    setSelected(`sidecar:${name}`);
    setSource(s.source);
  }

  function loadTemplate(name: string) {
    const t = templates.find((x) => x.name === name);
    if (!t) return;
    setSelected(`template:${name}`);
    setSource(t.source);
  }

  return (
    <motion.div
      key="editor"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.25 }}
      className="h-full w-full flex flex-col gap-5 px-[3vw] pt-4 pb-6"
    >
      <header className="flex items-baseline justify-between border-b border-white/10 pb-3">
        <div className="flex items-baseline gap-5">
          <h1 className="font-display font-semibold text-ink text-[clamp(2rem,3.4vw,2.8rem)] leading-none">
            Skill editor
          </h1>
          <span className="font-mono uppercase tracking-[0.2em] text-sm text-dim">
            edits live. nothing is saved.
          </span>
        </div>
        <Legend />
      </header>

      <div className="grid grid-cols-[minmax(0,14rem)_minmax(0,1fr)] gap-6 flex-1 min-h-0">
        <Sidebar
          sidecarLoading={sidecar.loading}
          sidecarError={sidecar.error}
          sidecarSkills={sidecar.skills}
          selected={selected}
          onLoadSidecar={loadSidecar}
          onLoadTemplate={loadTemplate}
        />
        <SkillEditor source={source} onChange={setSource} />
      </div>
    </motion.div>
  );
}

function Legend() {
  return (
    <div className="flex items-center gap-4 font-mono text-xs text-dim">
      {(Object.keys(SECTION_META) as SectionKey[]).map((k) => (
        <span key={k} className="flex items-center gap-2">
          <span
            className="w-3 h-3 rounded"
            style={{ backgroundColor: SECTION_META[k].bg }}
          />
          <span style={{ color: SECTION_META[k].text }}>
            {SECTION_META[k].label}
          </span>
        </span>
      ))}
    </div>
  );
}

function Sidebar({
  sidecarLoading,
  sidecarError,
  sidecarSkills,
  selected,
  onLoadSidecar,
  onLoadTemplate,
}: {
  sidecarLoading: boolean;
  sidecarError: string | null;
  sidecarSkills: { name: string; filename: string; source: string }[];
  selected: string | null;
  onLoadSidecar: (name: string) => void;
  onLoadTemplate: (name: string) => void;
}) {
  return (
    <aside className="flex flex-col gap-5 overflow-y-auto pr-1">
      <section>
        <h2 className="font-mono uppercase tracking-[0.15em] text-xs text-accent mb-2">
          templates
        </h2>
        <ul className="flex flex-col gap-1">
          {templates.map((t) => {
            const id = `template:${t.name}`;
            return (
              <li key={t.name}>
                <SidebarButton
                  active={selected === id}
                  onClick={() => onLoadTemplate(t.name)}
                  primary={t.name}
                  secondary={t.blurb}
                />
              </li>
            );
          })}
        </ul>
      </section>

      <section>
        <h2 className="font-mono uppercase tracking-[0.15em] text-xs text-accent mb-2">
          from sidecar
        </h2>
        {sidecarLoading && (
          <p className="font-mono text-dim text-xs">loading…</p>
        )}
        {sidecarError && (
          <p className="font-mono text-rose-400/80 text-xs">
            {sidecarError}
          </p>
        )}
        <ul className="flex flex-col gap-1">
          {sidecarSkills.map((s) => {
            const id = `sidecar:${s.name}`;
            return (
              <li key={s.name}>
                <SidebarButton
                  active={selected === id}
                  onClick={() => onLoadSidecar(s.name)}
                  primary={s.name}
                  secondary={s.filename}
                />
              </li>
            );
          })}
        </ul>
      </section>
    </aside>
  );
}

function SidebarButton({
  active,
  onClick,
  primary,
  secondary,
}: {
  active: boolean;
  onClick: () => void;
  primary: string;
  secondary: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full text-left px-3 py-2 rounded-md transition-colors ${active
        ? 'bg-accent/10 ring-1 ring-accent/40'
        : 'hover:bg-white/[0.05] ring-1 ring-transparent'
        }`}
    >
      <div
        className={`font-mono text-sm truncate ${active ? 'text-ink' : 'text-ink/85'}`}
      >
        {primary}
      </div>
      <div className="font-mono text-[0.7rem] text-dim truncate">
        {secondary}
      </div>
    </button>
  );
}

function SkillEditor({
  source,
  onChange,
}: {
  source: string;
  onChange: (value: string) => void;
}) {
  const sections = useMemo(() => parseSkill(source), [source]);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const overlayRef = useRef<HTMLPreElement>(null);
  const [scrollTop, setScrollTop] = useState(0);

  // Sync overlay scroll with textarea scroll.
  useLayoutEffect(() => {
    if (overlayRef.current) {
      overlayRef.current.scrollTop = scrollTop;
    }
  }, [scrollTop]);

  const totalLines = source.split('\n').length;
  const contentHeight = totalLines * LINE_HEIGHT + 2 * PAD_Y;

  return (
    <div className="flex min-h-0 bg-white/[0.03] ring-1 ring-white/10 rounded-lg overflow-hidden">
      {/* Brace column — on the left, arms point right into the text */}
      <BraceColumn
        sections={sections}
        totalHeight={contentHeight}
        scrollTop={scrollTop}
      />

      {/* Editor column */}
      <div className="flex-1 min-w-0 relative overflow-hidden">
        {/* Highlight overlay — paints section backgrounds behind the text */}
        <pre
          ref={overlayRef}
          aria-hidden
          className="absolute inset-0 overflow-auto pointer-events-none font-mono whitespace-pre-wrap break-words"
          style={{
            fontSize: FONT_SIZE,
            lineHeight: `${LINE_HEIGHT}px`,
            padding: `${PAD_Y}px ${PAD_X}px`,
            color: 'rgba(245, 245, 240, 0.92)',
          }}
        >
          <SectionedText source={source} sections={sections} />
        </pre>

        {/* Editable textarea — transparent text, visible caret */}
        <textarea
          ref={taRef}
          value={source}
          onChange={(e) => onChange(e.target.value)}
          onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)}
          spellCheck={false}
          className="absolute inset-0 w-full h-full bg-transparent outline-none resize-none font-mono whitespace-pre-wrap break-words"
          style={{
            fontSize: FONT_SIZE,
            lineHeight: `${LINE_HEIGHT}px`,
            padding: `${PAD_Y}px ${PAD_X}px`,
            color: 'transparent',
            caretColor: '#7dd3fc',
          }}
        />
      </div>
    </div>
  );
}

type Chunk = { section: SectionKey | null; text: string };

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
    const s = sectionAt(i);
    if (s !== current) {
      chunks.push({
        section: current,
        text: lines.slice(startIdx, i).join('\n'),
      });
      startIdx = i;
      current = s;
    }
  }
  chunks.push({
    section: current,
    text: lines.slice(startIdx).join('\n'),
  });
  return chunks;
}

function SectionedText({
  source,
  sections,
}: {
  source: string;
  sections: SkillSections;
}): ReturnType<typeof FragmentType> {
  const chunks = chunkBySection(source, sections);
  return (
    <>
      {chunks.map((c, i) => (
        <Fragment key={i}>
          {c.section ? (
            <span
              style={{
                backgroundColor: SECTION_META[c.section].bg,
                // Stretch the background across full line width via
                // box-decoration-break so multi-line chunks look like a
                // single colored block rather than per-line rectangles.
                boxDecorationBreak: 'clone',
                WebkitBoxDecorationBreak: 'clone',
              }}
            >
              {c.text}
            </span>
          ) : (
            c.text
          )}
          {i < chunks.length - 1 && '\n'}
        </Fragment>
      ))}
    </>
  );
}

function BraceColumn({
  sections,
  totalHeight,
  scrollTop,
}: {
  sections: SkillSections;
  totalHeight: number;
  scrollTop: number;
}) {
  // Braces sit immediately to the left of the editor. Stem hugs the right
  // edge of this column; arms extend rightward toward the text; labels are
  // to the left of the stem, right-aligned flush against it.
  const WIDTH = 122;
  const ARM = 6;
  const BRACE_X = WIDTH - 6;
  const LABEL_X = BRACE_X - 10;

  const entries: { key: SectionKey; start: number; end: number }[] = [];
  (['trigger', 'effects', 'prompt'] as const).forEach((k) => {
    const r = sections[k];
    if (r) entries.push({ key: k, start: r.start, end: r.end });
  });

  return (
    <div
      className="relative shrink-0 border-r border-white/5"
      style={{ width: WIDTH }}
    >
      <svg
        className="absolute left-0 top-0"
        style={{
          width: WIDTH,
          height: totalHeight,
          transform: `translateY(${-scrollTop}px)`,
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
              {/* Vertical stem */}
              <line
                x1={BRACE_X}
                y1={top}
                x2={BRACE_X}
                y2={bottom}
                stroke={meta.stroke}
                strokeWidth={1.3}
              />
              {/* Top arm — extends right into editor's left padding */}
              <line
                x1={BRACE_X}
                y1={top}
                x2={BRACE_X + ARM}
                y2={top}
                stroke={meta.stroke}
                strokeWidth={1.3}
              />
              {/* Bottom arm */}
              <line
                x1={BRACE_X}
                y1={bottom}
                x2={BRACE_X + ARM}
                y2={bottom}
                stroke={meta.stroke}
                strokeWidth={1.3}
              />
              {/* Middle tick toward the label on the left */}
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
