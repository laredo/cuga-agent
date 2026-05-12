import { AnimatePresence, motion } from 'framer-motion';
import { authoredKeywords } from '../slides';

type Props = {
  open: boolean;
  onSelect: (keyword: string) => void;
};

// 1..9 → indices 0..8; 0 → index 9. Anything beyond shows no shortcut.
export function shortcutFor(index: number): string | null {
  if (index < 9) return String(index + 1);
  if (index === 9) return '0';
  return null;
}

export default function HintOverlay({ open, onSelect }: Props) {
  const keywords = authoredKeywords();
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="hints"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-20 bg-canvas/85 backdrop-blur-md flex items-center justify-center px-[6vw] py-[5vh]"
        >
          <div className="max-w-[88ch] w-full">
            <h2 className="font-mono uppercase tracking-[0.2em] text-xs text-accent mb-4">
              click, or press the number
            </h2>
            <ul className="space-y-0.5">
              {keywords.map(({ canonical, aliases }, i) => {
                const key = shortcutFor(i);
                return (
                  <li key={canonical}>
                    <button
                      type="button"
                      onClick={() => onSelect(canonical)}
                      className="group w-full text-left px-3 py-2 rounded-md hover:bg-white/[0.06] ring-1 ring-transparent hover:ring-white/15 transition-colors flex items-baseline gap-3"
                    >
                      <span
                        className={`font-mono text-xs w-6 h-6 flex items-center justify-center rounded shrink-0 ${
                          key
                            ? 'bg-accent/15 text-accent ring-1 ring-accent/30'
                            : 'bg-white/[0.04] text-dim/60 ring-1 ring-white/5'
                        }`}
                      >
                        {key ?? '·'}
                      </span>
                      <span className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 min-w-0">
                        <span className="font-mono text-ink text-[clamp(0.9rem,1.2vw,1.15rem)] group-hover:text-accent transition-colors">
                          {canonical}
                        </span>
                        {aliases.length > 0 && (
                          <span className="text-dim font-mono text-xs">
                            {aliases.join(' · ')}
                          </span>
                        )}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
            <p className="mt-6 font-mono text-dim text-xs tracking-wider">
              number to jump · click to pick · type to search · esc to refocus · cmd/ctrl-/ · F1 · cmd/ctrl-p — toggle
            </p>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
