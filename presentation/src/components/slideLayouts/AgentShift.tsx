import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { CHAT_EXCHANGE, RADAR_PULSE } from '../../slides/icons';
import type { Slide } from '../../slides/types';

const ease = [0.22, 1, 0.36, 1] as const;
const chatBullets = [
  'You notice the work.',
  'You carry the context.',
  'The answer stays in chat.',
];
const ambientBullets = [
  'Issues open.',
  'PRs change.',
  'Transcripts land.',
];

export default function AgentShift({ slide }: { slide: Slide }) {
  const [revealed, setRevealed] = useState(() =>
    window.location.hash.includes('revealed'),
  );

  useEffect(() => {
    if (revealed) return;

    function onKeyDown(event: KeyboardEvent) {
      if (
        event.key === ' ' ||
        event.key === 'Enter' ||
        event.key === 'ArrowRight' ||
        event.key === 'ArrowDown' ||
        event.key === 'PageDown'
      ) {
        event.preventDefault();
        event.stopPropagation();
        setRevealed(true);
      }
    }

    window.addEventListener('keydown', onKeyDown, { capture: true });
    return () =>
      window.removeEventListener('keydown', onKeyDown, { capture: true });
  }, [revealed]);

  return (
    <motion.button
      key={slide.id}
      type="button"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.25 }}
      onClick={() => setRevealed(true)}
      className="h-full w-full text-left px-[6vw] py-[6vh] outline-none cursor-pointer"
      aria-label="Reveal ambient agent contrast"
    >
      <div className="relative h-full w-full overflow-hidden">
        <motion.section
          initial={false}
          animate={
            revealed
              ? {
                  width: '42%',
                  x: 0,
                  justifyContent: 'center',
                  alignItems: 'flex-start',
                }
              : {
                  width: '100%',
                  x: 0,
                  justifyContent: 'center',
                  alignItems: 'center',
                }
          }
          transition={{ duration: 0.75, ease }}
          className="absolute inset-y-0 left-0 flex flex-col gap-4"
        >
          <motion.div
            initial={false}
            animate={{
              scale: revealed ? 1 : 1,
              opacity: revealed ? 0.78 : 0.9,
            }}
            transition={{ duration: 0.75, ease }}
            className={`${revealed ? 'h-[4.5rem]' : 'h-[8.5rem]'} flex items-center ${revealed ? 'justify-start' : 'justify-center'} text-accent/80 [&_svg]:h-full [&_svg]:w-auto [&_svg]:max-w-full`}
          >
            <span
              className="[&_svg]:h-full [&_svg]:w-auto"
              dangerouslySetInnerHTML={{ __html: CHAT_EXCHANGE }}
            />
          </motion.div>

          <div>
            <motion.p
              initial={false}
              animate={{ opacity: revealed ? 1 : 0.7 }}
              transition={{ duration: 0.45, ease }}
              className="font-mono uppercase tracking-[0.2em] text-sm text-dim mb-4"
            >
              chat-based
            </motion.p>
            <motion.h1
              initial={false}
              animate={{
                fontSize: revealed
                  ? 'clamp(2.25rem, 3.2vw, 3.7rem)'
                  : 'clamp(3.6rem, 7vw, 7rem)',
              }}
              transition={{ duration: 0.75, ease }}
              className={`font-display font-semibold text-ink leading-[1.02] ${revealed ? 'max-w-[11ch]' : ''}`}
            >
              Agents are pen-pals.
            </motion.h1>
            <motion.p
              initial={false}
              animate={{
                opacity: revealed ? 0 : 1,
                fontSize: revealed
                  ? 'clamp(1rem, 1.35vw, 1.35rem)'
                  : 'clamp(1.4rem, 2.2vw, 2.2rem)',
                height: revealed ? 0 : 'auto',
              }}
              transition={{ duration: 0.75, ease }}
              className="mt-6 overflow-hidden text-dim leading-snug max-w-[32ch]"
            >
              You type. They reply. Work waits for you.
            </motion.p>
            <BulletList
              items={chatBullets}
              revealed={revealed}
              tone="muted"
              delayBase={0.72}
            />
          </div>
        </motion.section>

        <motion.svg
          viewBox="0 0 160 40"
          initial={false}
          animate={{
            opacity: revealed ? 1 : 0,
          }}
          transition={{ delay: revealed ? 0.32 : 0, duration: 0.62, ease }}
          className="absolute left-1/2 top-1/2 w-[5.5rem] -translate-x-1/2 -translate-y-1/2 text-accent/75"
          fill="none"
          aria-hidden
        >
          <motion.path
            d="M8 20 H145 M128 7 L145 20 L128 33"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: revealed ? 1 : 0 }}
            transition={{ delay: revealed ? 0.32 : 0, duration: 0.62, ease }}
          />
        </motion.svg>

        <motion.section
          initial={false}
          animate={{
            opacity: revealed ? 1 : 0,
            x: revealed ? 0 : 64,
            filter: revealed ? 'blur(0px)' : 'blur(8px)',
          }}
          transition={{ delay: revealed ? 0.38 : 0, duration: 0.65, ease }}
          className="absolute inset-y-0 right-0 w-[42%] flex flex-col justify-center gap-4 pointer-events-none"
        >
          <div className="h-[4.5rem] flex items-center justify-start text-accent/90 [&_svg]:h-full [&_svg]:w-auto [&_svg]:max-w-full">
            <span
              className="[&_svg]:h-full [&_svg]:w-auto"
              dangerouslySetInnerHTML={{ __html: RADAR_PULSE }}
            />
          </div>
          <div>
            <p className="font-mono uppercase tracking-[0.2em] text-sm text-accent mb-4">
              ambient · event-based
            </p>
            <h2 className="font-display font-semibold text-ink leading-[1.03] text-[clamp(2.25rem,3.2vw,3.7rem)] max-w-[17ch]">
              Agents wake up when work arrives.
            </h2>
            <BulletList
              items={ambientBullets}
              revealed={revealed}
              tone="accent"
              delayBase={0.72}
            />
          </div>
        </motion.section>

        {!revealed && (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.55 }}
            transition={{ delay: 0.7, duration: 0.4 }}
            className="absolute bottom-0 left-1/2 -translate-x-1/2 font-mono uppercase tracking-[0.18em] text-xs text-dim"
          >
            click to reveal
          </motion.p>
        )}
      </div>
    </motion.button>
  );
}

function BulletList({
  items,
  revealed,
  tone,
  delayBase,
}: {
  items: string[];
  revealed: boolean;
  tone: 'muted' | 'accent';
  delayBase: number;
}) {
  return (
    <ul className="mt-4 space-y-2">
      {items.map((item, index) => (
        <motion.li
          key={item}
          initial={false}
          animate={{
            opacity: revealed ? 1 : 0,
            y: revealed ? 0 : 16,
          }}
          transition={{
            delay: revealed ? delayBase + index * 0.1 : 0,
            duration: 0.4,
            ease,
          }}
          className="flex items-baseline gap-3 text-ink/90 text-[clamp(0.95rem,1.15vw,1.15rem)] leading-snug"
        >
          <span className={tone === 'accent' ? 'text-accent' : 'text-dim/75'}>
            ›
          </span>
          <span>{item}</span>
        </motion.li>
      ))}
    </ul>
  );
}
