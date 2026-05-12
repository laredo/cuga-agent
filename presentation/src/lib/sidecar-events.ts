import { useEffect, useRef, useState } from 'react';

// Mirror of the plugin's ParsedEvent. Keep in sync.
export type Trigger =
  | { kind: 'file'; path: string; glob: string }
  | {
      kind: 'github';
      target: string;
      resource: string;
      event: string;
      interval: number;
    };

export type ParsedEvent =
  | { kind: 'skill-registered'; at: string; skill: string; trigger: Trigger }
  | { kind: 'trigger'; at: string; skill: string; detail: string }
  | { kind: 'invoke'; at: string; size: number }
  | { kind: 'fired'; at: string; hook: string; effect: string; summary: string }
  | { kind: 'skipped'; at: string; hook: string; effect: string; when: string }
  | { kind: 'failed'; at: string; hook: string; effect: string; error: string }
  | { kind: 'status'; message: string };

export type SkillInfo = {
  name: string;
  trigger: Trigger;
  // Effect types observed for this skill in the session (write_file, notify,
  // github_comment, ntfy_post, ...). Built up as fired/skipped/failed events
  // arrive; preserved across sidecar restarts within one session.
  effects: string[];
};

export type SidecarState = {
  connected: boolean;
  status: string;
  skills: SkillInfo[];
  timeline: ParsedEvent[];
  lastEventAt: number; // epoch ms, for animation keys
  // Skill of the most recent 'trigger' event. Used to attribute effect
  // events (fired/skipped/failed) — which don't carry a skill field — to
  // whichever skill is currently being dispatched.
  trailingSkill: string | null;
};

const TIMELINE_CAP = 400;

// EventSource does not emit a reliable "connected" event; we derive it from
// the first message arriving and from readyState. On error we mark disconnected.
export function useSidecarEvents(
  url = '/api/sidecar-events',
): SidecarState {
  const [state, setState] = useState<SidecarState>({
    connected: false,
    status: 'connecting',
    skills: [],
    timeline: [],
    lastEventAt: 0,
    trailingSkill: null,
  });
  const reconnect = useRef<number | null>(null);

  useEffect(() => {
    let es: EventSource | null = null;
    let closed = false;

    function open() {
      if (closed) return;
      es = new EventSource(url);

      es.onopen = () => {
        setState((s) => ({ ...s, connected: true, status: 'connected' }));
      };

      es.onmessage = (evt) => {
        let parsed: ParsedEvent;
        try {
          parsed = JSON.parse(evt.data) as ParsedEvent;
        } catch {
          return;
        }
        setState((s) => applyEvent(s, parsed));
      };

      es.onerror = () => {
        setState((s) => ({ ...s, connected: false, status: 'disconnected' }));
        es?.close();
        if (closed) return;
        if (reconnect.current) window.clearTimeout(reconnect.current);
        reconnect.current = window.setTimeout(open, 2000);
      };
    }

    open();

    return () => {
      closed = true;
      if (reconnect.current) window.clearTimeout(reconnect.current);
      es?.close();
    };
  }, [url]);

  return state;
}

function applyEvent(s: SidecarState, ev: ParsedEvent): SidecarState {
  if (ev.kind === 'status') {
    return { ...s, status: ev.message };
  }

  let skills = s.skills;
  let trailingSkill = s.trailingSkill;

  if (ev.kind === 'skill-registered') {
    const existing = skills.findIndex((sk) => sk.name === ev.skill);
    if (existing >= 0) {
      // Preserve observed effects across re-registrations within one session.
      skills = [...skills];
      skills[existing] = { ...skills[existing], trigger: ev.trigger };
    } else {
      skills = [
        ...skills,
        { name: ev.skill, trigger: ev.trigger, effects: [] },
      ];
    }
    skills.sort((a, b) => a.name.localeCompare(b.name));
  }

  if (ev.kind === 'trigger') {
    trailingSkill = ev.skill;
  }

  if (
    ev.kind === 'fired' ||
    ev.kind === 'skipped' ||
    ev.kind === 'failed'
  ) {
    if (trailingSkill) {
      const idx = skills.findIndex((sk) => sk.name === trailingSkill);
      if (idx >= 0 && !skills[idx].effects.includes(ev.effect)) {
        skills = [...skills];
        skills[idx] = {
          ...skills[idx],
          effects: [...skills[idx].effects, ev.effect],
        };
      }
    }
  }

  const timeline = [...s.timeline, ev];
  if (timeline.length > TIMELINE_CAP) {
    timeline.splice(0, timeline.length - TIMELINE_CAP);
  }

  return {
    ...s,
    skills,
    timeline,
    trailingSkill,
    lastEventAt: Date.now(),
  };
}
