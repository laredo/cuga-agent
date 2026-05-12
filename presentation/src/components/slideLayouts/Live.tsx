import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  useSidecarEvents,
  type ParsedEvent,
  type SkillInfo,
} from '../../lib/sidecar-events';

export default function Live() {
  const { connected, status, skills, timeline } = useSidecarEvents();
  const [filter, setFilter] = useState<string | null>(null);

  // Hide raw 'status' entries from the timeline — they're surfaced in
  // the header dot + text, and they don't read well as event rows.
  const events = timeline.filter((e) => e.kind !== 'status');
  const filteredEvents = filter ? filterForSkill(events, filter) : events;

  function toggleFilter(skillName: string) {
    setFilter((cur) => (cur === skillName ? null : skillName));
  }

  // If the active filter points at a skill that no longer exists (the
  // sidecar restarted with a different set), drop the filter.
  useEffect(() => {
    if (filter && skills.length > 0 && !skills.some((s) => s.name === filter)) {
      setFilter(null);
    }
  }, [filter, skills]);

  return (
    <motion.div
      key="live"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.25 }}
      className="h-full w-full flex flex-col gap-6 px-[4vw] pt-4 pb-6"
    >
      <Header
        connected={connected}
        status={status}
        skillCount={skills.length}
        filter={filter}
        onClearFilter={() => setFilter(null)}
      />

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)] gap-10 flex-1 min-h-0">
        <SkillsColumn
          skills={skills}
          filter={filter}
          onToggle={toggleFilter}
        />
        <StreamColumn events={filteredEvents} />
      </div>
    </motion.div>
  );
}

// Associates an event with the most recent preceding trigger's skill.
// Lets effects (invoke / fired / skipped / failed — which don't carry a
// skill field themselves) get attributed for filtering. Fails on parallel
// skills on the same trigger event, but acceptable for display.
function filterForSkill(events: ParsedEvent[], filter: string): ParsedEvent[] {
  let trailing: string | null = null;
  const out: ParsedEvent[] = [];
  for (const ev of events) {
    if (ev.kind === 'trigger') {
      trailing = ev.skill;
      if (ev.skill === filter) out.push(ev);
    } else if (ev.kind === 'skill-registered') {
      if (ev.skill === filter) out.push(ev);
    } else if (ev.kind !== 'status') {
      if (trailing === filter) out.push(ev);
    }
  }
  return out;
}

function Header({
  connected,
  status,
  skillCount,
  filter,
  onClearFilter,
}: {
  connected: boolean;
  status: string;
  skillCount: number;
  filter: string | null;
  onClearFilter: () => void;
}) {
  return (
    <header className="flex items-baseline justify-between border-b border-white/10 pb-4">
      <div className="flex items-baseline gap-5 min-w-0">
        <h1 className="font-display font-semibold text-ink text-[clamp(2rem,3.6vw,3rem)] leading-none">
          Live
        </h1>
        <span className="font-mono uppercase tracking-[0.2em] text-sm text-dim">
          {skillCount} skill{skillCount === 1 ? '' : 's'} running
        </span>
        {filter && (
          <button
            type="button"
            onClick={onClearFilter}
            className="font-mono text-sm text-accent hover:text-ink transition-colors truncate"
            title="clear filter"
          >
            filter: {filter} ✕
          </button>
        )}
      </div>
      <div className="flex items-center gap-3 font-mono text-sm text-dim">
        <span
          className={`w-2.5 h-2.5 rounded-full ${
            connected ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'
          }`}
        />
        <span>{status}</span>
      </div>
    </header>
  );
}

function SkillsColumn({
  skills,
  filter,
  onToggle,
}: {
  skills: SkillInfo[];
  filter: string | null;
  onToggle: (name: string) => void;
}) {
  return (
    <section className="flex flex-col gap-4 min-h-0">
      <h2 className="font-mono uppercase tracking-[0.2em] text-sm text-accent">
        skills
        <span className="text-dim normal-case tracking-normal ml-3">
          click to filter the stream
        </span>
      </h2>
      <div className="grid grid-cols-1 gap-3 overflow-y-auto pr-2">
        {skills.length === 0 && (
          <p className="font-mono text-dim text-sm">
            no skills found in the log
          </p>
        )}
        {skills.map((s) => (
          <SkillCard
            key={s.name}
            skill={s}
            active={filter === s.name}
            dimmed={filter !== null && filter !== s.name}
            onClick={() => onToggle(s.name)}
          />
        ))}
      </div>
    </section>
  );
}

function SkillCard({
  skill,
  active,
  dimmed,
  onClick,
}: {
  skill: SkillInfo;
  active: boolean;
  dimmed: boolean;
  onClick: () => void;
}) {
  const t = skill.trigger;

  const base =
    'text-left rounded-lg p-4 flex flex-col gap-3 transition-all duration-150 cursor-pointer';
  const tone = active
    ? 'bg-accent/10 ring-2 ring-accent/60'
    : dimmed
      ? 'bg-white/[0.02] ring-1 ring-white/5 opacity-50 hover:opacity-80'
      : 'bg-white/[0.04] ring-1 ring-white/10 hover:bg-white/[0.07] hover:ring-white/20';

  return (
    <motion.button
      type="button"
      layout
      onClick={onClick}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className={`${base} ${tone}`}
    >
      <div className="font-mono text-ink text-[clamp(0.95rem,1.25vw,1.15rem)] leading-tight">
        {skill.name}
      </div>

      <div className="flex flex-col gap-1.5">
        <SectionLabel>trigger</SectionLabel>
        <div className="flex items-center gap-2 flex-wrap">
          <TriggerBadge kind={t.kind} />
          <TriggerDetail trigger={t} />
        </div>
      </div>

      <EffectsRow effects={skill.effects} />
    </motion.button>
  );
}

function SectionLabel({ children }: { children: string }) {
  return (
    <span className="font-mono uppercase tracking-[0.12em] text-[0.6rem] text-dim">
      {children}
    </span>
  );
}

function TriggerBadge({ kind }: { kind: 'file' | 'github' }) {
  const tone =
    kind === 'file'
      ? 'bg-sky-400/15 text-sky-200 ring-sky-400/30'
      : 'bg-violet-400/15 text-violet-200 ring-violet-400/30';
  return (
    <span
      className={`font-mono uppercase tracking-[0.12em] text-[0.65rem] px-2 py-[0.2rem] rounded-full ring-1 ${tone}`}
    >
      {kind}
    </span>
  );
}

function TriggerDetail({ trigger }: { trigger: SkillInfo['trigger'] }) {
  if (trigger.kind === 'file') {
    return (
      <span className="font-mono text-dim text-xs">
        <span className="text-ink">{trigger.glob}</span>
        <span className="mx-1.5">in</span>
        <span>{shortenPath(trigger.path)}</span>
      </span>
    );
  }
  return (
    <span className="font-mono text-dim text-xs">
      <span className="text-ink">{trigger.resource}</span>
      <span className="mx-1.5">·</span>
      <span>{trigger.event}</span>
      <span className="mx-1.5">·</span>
      <span>every {trigger.interval}s</span>
    </span>
  );
}

function EffectsRow({ effects }: { effects: string[] }) {
  return (
    <div className="flex flex-col gap-1.5">
      <SectionLabel>effects</SectionLabel>
      {effects.length === 0 ? (
        <span className="font-mono text-dim/50 text-[0.7rem] italic">
          none observed yet
        </span>
      ) : (
        <div className="flex items-center gap-1.5 flex-wrap">
          {effects.map((e) => (
            <span
              key={e}
              className="font-mono text-[0.7rem] px-1.5 py-[0.1rem] rounded bg-white/[0.06] text-ink/80 ring-1 ring-white/10"
            >
              {e}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function StreamColumn({ events }: { events: ParsedEvent[] }) {
  // Tag each event with the skill of its nearest preceding trigger so that
  // effects (invoke / fired / skipped / failed — which don't carry a skill
  // field) can still display attribution. Walk forward, then reverse for
  // newest-on-top display.
  const tagged: { ev: ParsedEvent; skill: string | null }[] = [];
  let trailing: string | null = null;
  for (const ev of events) {
    if (ev.kind === 'trigger') trailing = ev.skill;
    const own =
      ev.kind === 'trigger' || ev.kind === 'skill-registered' ? ev.skill : null;
    tagged.push({ ev, skill: own ?? trailing });
  }
  const rows = [...tagged].reverse();

  return (
    <section className="flex flex-col gap-4 min-h-0">
      <h2 className="font-mono uppercase tracking-[0.2em] text-sm text-accent">
        stream
        <span className="text-dim normal-case tracking-normal ml-3">
          {events.length} event{events.length === 1 ? '' : 's'}
        </span>
      </h2>
      <div className="overflow-y-auto pr-2 flex flex-col gap-2 min-h-0">
        {rows.length === 0 && (
          <p className="font-mono text-dim text-sm">
            no events match
          </p>
        )}
        <AnimatePresence initial={false}>
          {rows.map(({ ev, skill }, i) => (
            <EventRow
              key={`${events.length - i}-${'at' in ev ? ev.at : ''}-${ev.kind}`}
              ev={ev}
              skill={skill}
            />
          ))}
        </AnimatePresence>
      </div>
    </section>
  );
}

function EventRow({
  ev,
  skill,
}: {
  ev: ParsedEvent;
  skill: string | null;
}) {
  if (ev.kind === 'status') return null;
  const time = timeOnly(ev.at);
  let glyph = '·';
  let glyphTone = 'text-dim';
  let label: string = ev.kind;
  let detail = '';

  switch (ev.kind) {
    case 'skill-registered':
      glyph = '+';
      glyphTone = 'text-accent';
      label = 'registered';
      detail =
        ev.trigger.kind === 'file'
          ? `watching ${ev.trigger.glob}`
          : `polling ${ev.trigger.target} / ${ev.trigger.resource}`;
      break;
    case 'trigger':
      glyph = '›';
      glyphTone = 'text-accent';
      label = 'event';
      detail = ev.detail;
      break;
    case 'invoke':
      glyph = '…';
      glyphTone = 'text-dim';
      label = 'invoking cuga';
      detail = `${ev.size} chars`;
      break;
    case 'fired':
      glyph = '✓';
      glyphTone = 'text-emerald-400';
      label = `fired · ${ev.effect}`;
      detail = `[${ev.hook}] ${ev.summary}`;
      break;
    case 'skipped':
      glyph = '⊘';
      glyphTone = 'text-amber-300/80';
      label = `skipped · ${ev.effect}`;
      detail = `[${ev.hook}] when=${ev.when}`;
      break;
    case 'failed':
      glyph = '✗';
      glyphTone = 'text-rose-400';
      label = `failed · ${ev.effect}`;
      detail = `[${ev.hook}] ${ev.error}`;
      break;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="group grid grid-cols-[auto_auto_minmax(0,max-content)_minmax(0,1fr)] items-baseline gap-3 font-mono text-[clamp(0.75rem,1vw,0.95rem)] rounded px-1.5 -mx-1.5 hover:bg-white/[0.04] transition-colors"
    >
      <span className="text-dim/60 tabular-nums">{time}</span>
      <span className={`${glyphTone} shrink-0 w-3 text-center`}>{glyph}</span>
      <span
        className={`${skill ? 'text-accent/90' : 'text-dim/40'} shrink-0 truncate group-hover:whitespace-normal group-hover:overflow-visible max-w-[18ch] group-hover:max-w-none group-hover:break-words`}
      >
        {skill ?? '—'}
      </span>
      <span className="min-w-0 truncate group-hover:whitespace-normal group-hover:overflow-visible group-hover:break-words">
        <span className="text-ink">{label}</span>
        {detail && <span className="text-dim"> — {detail}</span>}
      </span>
    </motion.div>
  );
}

function timeOnly(ts: string): string {
  // "2026-05-08 10:09:47" → "10:09:47"
  const i = ts.indexOf(' ');
  return i >= 0 ? ts.slice(i + 1) : ts;
}

function shortenPath(p: string): string {
  const parts = p.split('/').filter(Boolean);
  if (parts.length <= 3) return p;
  return `…/${parts.slice(-3).join('/')}`;
}
