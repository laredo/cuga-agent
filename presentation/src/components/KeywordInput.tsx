import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';
import { motion, useAnimation } from 'framer-motion';

type Props = {
  value: string;
  onChange: (value: string) => void;
  onEnter: (value: string) => void;
};

export type KeywordInputHandle = {
  focus: () => void;
};

const IDLE_FADE_MS = 6000;

const KeywordInput = forwardRef<KeywordInputHandle, Props>(function KeywordInput(
  { value, onChange, onEnter },
  ref,
) {
  const controls = useAnimation();
  const inputRef = useRef<HTMLInputElement>(null);
  const timer = useRef<number | null>(null);

  useImperativeHandle(ref, () => ({
    focus: () => inputRef.current?.focus(),
  }));

  function bump() {
    controls.start({ opacity: 1, transition: { duration: 0.15 } });
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      controls.start({ opacity: 0.18, transition: { duration: 0.6 } });
    }, IDLE_FADE_MS);
  }

  useEffect(() => {
    bump();
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <motion.div
      animate={controls}
      initial={{ opacity: 1 }}
      className="sticky top-0 z-10 px-[4vw] pt-6 pb-4 bg-canvas/80 backdrop-blur-sm"
      onMouseMove={bump}
    >
      <div className="flex items-baseline gap-4">
        <span className="text-accent/70 font-mono uppercase tracking-[0.2em] text-sm">
          ›
        </span>
        <input
          ref={inputRef}
          autoFocus
          type="text"
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            bump();
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              onEnter(value);
              bump();
            }
          }}
          placeholder="start typing…"
          spellCheck={false}
          autoComplete="off"
          className="flex-1 bg-transparent outline-none border-none text-ink font-mono text-[clamp(1.6rem,3vw,3rem)] leading-none placeholder:text-dim/40 caret-accent"
        />
      </div>
      <div className="h-px bg-white/10 mt-3" />
    </motion.div>
  );
});

export default KeywordInput;
