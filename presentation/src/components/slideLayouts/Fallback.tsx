import { motion } from 'framer-motion';
import { slideContainer, slideChild } from '../../lib/motion';

export type FallbackState =
  | { status: 'loading'; keyword: string }
  | { status: 'ready'; keyword: string; title: string; bullets: string[] }
  | { status: 'error'; keyword: string; message: string };

export default function Fallback({ state }: { state: FallbackState }) {
  return (
    <motion.div
      key={`fallback:${state.keyword}:${state.status}`}
      variants={slideContainer}
      initial="initial"
      animate="enter"
      exit="exit"
      className="h-full w-full flex flex-col justify-center gap-10 px-[8vw]"
    >
      <motion.div
        variants={slideChild}
        className="flex items-center gap-4 text-dim font-mono uppercase tracking-[0.2em] text-sm"
      >
        <span className="text-accent">improvising</span>
        <span className="text-dim/60">›</span>
        <span>{state.keyword}</span>
      </motion.div>

      {state.status === 'loading' && (
        <motion.div variants={slideChild} className="flex flex-col gap-5 max-w-[40ch]">
          <div className="shimmer h-10 w-2/3 rounded" />
          <div className="shimmer h-7 w-4/5 rounded" />
          <div className="shimmer h-7 w-3/5 rounded" />
          <div className="shimmer h-7 w-2/4 rounded" />
        </motion.div>
      )}

      {state.status === 'ready' && (
        <>
          <motion.h1
            variants={slideChild}
            className="font-display font-semibold text-ink leading-[1.05] text-[clamp(2.6rem,5.5vw,5rem)]"
          >
            {state.title}
          </motion.h1>
          <ul className="space-y-4">
            {state.bullets.map((b, i) => (
              <motion.li
                key={i}
                variants={slideChild}
                className="flex items-baseline gap-4 text-ink text-[clamp(1.2rem,2vw,2.2rem)] leading-tight"
              >
                <span className="text-accent/80 shrink-0">›</span>
                <span>{b}</span>
              </motion.li>
            ))}
          </ul>
        </>
      )}

      {state.status === 'error' && (
        <motion.div variants={slideChild} className="flex flex-col gap-4 max-w-[50ch]">
          <p className="text-ink text-[clamp(1.4rem,2.4vw,2.4rem)] leading-tight">
            {state.message}
          </p>
          <p className="text-dim font-mono text-sm">
            press esc and try another keyword
          </p>
        </motion.div>
      )}
    </motion.div>
  );
}
