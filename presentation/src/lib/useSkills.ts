import { useEffect, useState } from 'react';

export type SidecarSkillFile = {
  name: string;
  filename: string;
  source: string;
};

export type UseSkillsState = {
  loading: boolean;
  error: string | null;
  skills: SidecarSkillFile[];
};

export function useSidecarSkills(): UseSkillsState {
  const [state, setState] = useState<UseSkillsState>({
    loading: true,
    error: null,
    skills: [],
  });

  useEffect(() => {
    let cancelled = false;
    fetch('/api/skills')
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data: { skills: SidecarSkillFile[] }) => {
        if (cancelled) return;
        setState({ loading: false, error: null, skills: data.skills });
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setState({ loading: false, error: err.message, skills: [] });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
