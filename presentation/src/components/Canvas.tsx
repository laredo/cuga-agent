import { AnimatePresence, motion } from 'framer-motion';
import Centered from './slideLayouts/Centered';
import Left from './slideLayouts/Left';
import Split from './slideLayouts/Split';
import Grid from './slideLayouts/Grid';
import Code from './slideLayouts/Code';
import AgentShift from './slideLayouts/AgentShift';
import Fullbleed from './slideLayouts/Fullbleed';
import Live from './slideLayouts/Live';
import Editor from './slideLayouts/Editor';
import Fallback, { type FallbackState } from './slideLayouts/Fallback';
import { slideContainer, slideChild } from '../lib/motion';
import type { Slide } from '../slides/types';

export type CanvasState =
  | { kind: 'idle' }
  | { kind: 'slide'; slide: Slide }
  | { kind: 'fallback'; state: FallbackState };

function Idle() {
  return (
    <motion.div
      key="idle"
      variants={slideContainer}
      initial="initial"
      animate="enter"
      exit="exit"
      className="h-full w-full flex items-center justify-center px-[8vw]"
    >
      <motion.p
        variants={slideChild}
        className="text-dim font-mono text-lg tracking-[0.15em] uppercase"
      >
        type a keyword
      </motion.p>
    </motion.div>
  );
}

function renderSlide(slide: Slide) {
  switch (slide.layout) {
    case 'agentShift':
      return <AgentShift key={slide.id} slide={slide} />;
    case 'centered':
      return <Centered key={slide.id} slide={slide} />;
    case 'left':
      return <Left key={slide.id} slide={slide} />;
    case 'split':
      return <Split key={slide.id} slide={slide} />;
    case 'grid':
      return <Grid key={slide.id} slide={slide} />;
    case 'code':
      return <Code key={slide.id} slide={slide} />;
    case 'fullbleed':
      return <Fullbleed key={slide.id} slide={slide} />;
    case 'live':
      return <Live key={slide.id} />;
    case 'editor':
      return <Editor key={slide.id} />;
    case 'fallback':
      return <Centered key={slide.id} slide={slide} />;
  }
}

export default function Canvas({ state }: { state: CanvasState }) {
  return (
    <div className="canvas-root flex-1 w-full relative">
      <AnimatePresence mode="wait" initial={false}>
        {state.kind === 'idle' && <Idle />}
        {state.kind === 'slide' && renderSlide(state.slide)}
        {state.kind === 'fallback' && <Fallback state={state.state} />}
      </AnimatePresence>
    </div>
  );
}
