import { motion } from 'framer-motion';
import { slideContainer } from '../../lib/motion';
import { RenderElement } from './Elements';
import type { Slide } from '../../slides/types';

export default function Grid({ slide }: { slide: Slide }) {
  const headline = slide.elements.find((e) => e.kind === 'headline');
  const panels = slide.elements.filter((e) => e.kind !== 'headline');
  return (
    <motion.div
      key={slide.id}
      variants={slideContainer}
      initial="initial"
      animate="enter"
      exit="exit"
      className="h-full w-full flex flex-col justify-center gap-8 px-[6vw] overflow-hidden"
    >
      {headline && <RenderElement el={headline} />}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {panels.map((el, i) => (
          <RenderElement key={i} el={el} />
        ))}
      </div>
    </motion.div>
  );
}
