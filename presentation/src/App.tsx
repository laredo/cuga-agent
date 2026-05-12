import { useCallback, useEffect, useRef, useState } from 'react';
import KeywordInput, { type KeywordInputHandle } from './components/KeywordInput';
import Canvas, { type CanvasState } from './components/Canvas';
import HintOverlay from './components/HintOverlay';
import { resolve } from './slides';
import { slides } from './slides/content';
import { improviseSlide, MissingApiKeyError } from './lib/llm';

export default function App() {
  const [value, setValue] = useState('');
  const [canvas, setCanvas] = useState<CanvasState>({ kind: 'idle' });
  const [hintsOpen, setHintsOpen] = useState(false);
  const inputRef = useRef<KeywordInputHandle>(null);
  const inflight = useRef<AbortController | null>(null);
  // Index into the `slides` array for whichever authored slide is showing.
  // -1 = idle or fallback; PageDown from here advances to slide 0.
  const currentIndex = useRef(-1);

  // Live-match on every keystroke.
  const handleChange = useCallback((raw: string) => {
    setValue(raw);
    if (raw.trim() === '') {
      setCanvas({ kind: 'idle' });
      currentIndex.current = -1;
      return;
    }
    const result = resolve(raw);
    if (result.kind === 'clear') {
      setCanvas({ kind: 'idle' });
      currentIndex.current = -1;
      return;
    }
    if (result.kind === 'slide') {
      const idx = slides.findIndex((s) => s.id === result.slide.id);
      currentIndex.current = idx;
      setCanvas((prev) =>
        prev.kind === 'slide' && prev.slide.id === result.slide.id
          ? prev
          : { kind: 'slide', slide: result.slide },
      );
    }
  }, []);

  const handleEnter = useCallback(async (raw: string) => {
    const result = resolve(raw);
    if (result.kind === 'clear' || raw.trim() === '') {
      setCanvas({ kind: 'idle' });
      currentIndex.current = -1;
      return;
    }
    if (result.kind === 'slide') return;

    if (inflight.current) inflight.current.abort();
    const keyword = result.keyword;
    setCanvas({ kind: 'fallback', state: { status: 'loading', keyword } });
    currentIndex.current = -1;

    const ctrl = new AbortController();
    inflight.current = ctrl;
    try {
      const { title, bullets } = await improviseSlide(keyword, ctrl.signal);
      if (ctrl.signal.aborted) return;
      setCanvas({
        kind: 'fallback',
        state: { status: 'ready', keyword, title, bullets },
      });
    } catch (e) {
      if (ctrl.signal.aborted) return;
      const message =
        e instanceof MissingApiKeyError
          ? 'No fallback configured. Set VITE_OPENAI_API_KEY in .env.'
          : e instanceof Error
            ? e.message
            : 'unknown error';
      setCanvas({
        kind: 'fallback',
        state: { status: 'error', keyword, message },
      });
    }
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const slide = params.get('slide');
    if (slide) handleChange(slide);
  }, [handleChange]);

  // Navigate through authored slides in script order (content.ts order).
  // Clamps at the ends — no wrap-around, since a surprise jump back to the
  // start mid-talk would be disorienting.
  const navigate = useCallback((delta: number) => {
    const total = slides.length;
    const from = currentIndex.current;
    let next: number;
    if (from < 0) {
      // No authored slide is showing; delta=1 → first slide, delta=-1 → last.
      next = delta > 0 ? 0 : total - 1;
    } else {
      next = Math.max(0, Math.min(total - 1, from + delta));
      if (next === from) return;
    }
    const slide = slides[next];
    // Drive the input as the source of truth; handleChange will sync the
    // canvas and currentIndex.
    handleChange(slide.id);
  }, [handleChange]);

  // Global hotkeys.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      // Digit shortcut: when the hint overlay is open, 1-9 jump to the
      // Nth authored slide and 0 jumps to the 10th.
      if (hintsOpen && /^[0-9]$/.test(e.key) && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        const n = e.key === '0' ? 10 : Number(e.key);
        if (n >= 1 && n <= slides.length) {
          const target = slides[n - 1];
          setHintsOpen(false);
          handleChange(target.id);
          inputRef.current?.focus();
        }
        return;
      }

      // Presenter clicker / explicit next-prev. PageDown/PageUp are what
      // the vast majority of remotes emit.
      if (e.key === 'PageDown') {
        e.preventDefault();
        navigate(1);
        return;
      }
      if (e.key === 'PageUp') {
        e.preventDefault();
        navigate(-1);
        return;
      }

      // Arrow keys also navigate, but ONLY when the input is empty — so they
      // don't interfere with caret movement while typing.
      if ((e.key === 'ArrowRight' || e.key === 'ArrowDown') && value === '') {
        e.preventDefault();
        navigate(1);
        return;
      }
      if ((e.key === 'ArrowLeft' || e.key === 'ArrowUp') && value === '') {
        e.preventDefault();
        navigate(-1);
        return;
      }

      if (e.key === 'Escape') {
        if (hintsOpen) {
          setHintsOpen(false);
          return;
        }
        // Refocus the input, but keep the current slide and input text
        // intact — nothing destructive, just a "get me back to typing".
        inputRef.current?.focus();
        return;
      }

      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
        return;
      }

      // Toggle the authored-keyword cheatsheet. Three bindings so the
      // presenter can reach it no matter which one sticks in memory:
      //   Cmd/Ctrl-/  — standard help
      //   F1          — universal help key
      //   Cmd/Ctrl-P  — command-palette convention
      if (
        ((e.metaKey || e.ctrlKey) && e.key === '/') ||
        e.key === 'F1' ||
        ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'p')
      ) {
        e.preventDefault();
        setHintsOpen((v) => !v);
        return;
      }
    }

    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [hintsOpen, navigate, handleChange, value]);

  return (
    <div className="h-full flex flex-col">
      <KeywordInput
        ref={inputRef}
        value={value}
        onChange={handleChange}
        onEnter={handleEnter}
      />
      <Canvas state={canvas} />
      <HintOverlay
        open={hintsOpen}
        onSelect={(keyword) => {
          setHintsOpen(false);
          handleChange(keyword);
          inputRef.current?.focus();
        }}
      />
      <HintBadge open={hintsOpen} onClick={() => setHintsOpen((v) => !v)} />
    </div>
  );
}

function HintBadge({
  open,
  onClick,
}: {
  open: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`fixed bottom-4 right-4 z-30 font-mono text-[0.7rem] uppercase tracking-[0.15em] px-3 py-1.5 rounded-full transition-all ${
        open
          ? 'bg-accent/20 text-accent ring-1 ring-accent/50'
          : 'bg-white/[0.05] text-dim ring-1 ring-white/10 hover:bg-white/[0.1] hover:text-ink'
      }`}
      title="press ⌘/ or F1"
    >
      {open ? 'close' : '?  pages'}
    </button>
  );
}
