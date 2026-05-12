import { motion } from 'framer-motion';
import { slideContainer } from '../../lib/motion';
import { RenderElement } from './Elements';
import type { Slide, Element } from '../../slides/types';

const LEFT_KINDS: Element['kind'][] = ['headline', 'figure', 'quote'];

export default function Split({ slide }: { slide: Slide }) {
  const left = slide.elements.filter((e) => LEFT_KINDS.includes(e.kind));
  const right = slide.elements.filter((e) => !LEFT_KINDS.includes(e.kind));

  return (
    <motion.div
      key={slide.id}
      variants={slideContainer}
      initial="initial"
      animate="enter"
      exit="exit"
      className="h-full w-full grid grid-cols-1 lg:grid-cols-2 gap-16 items-center px-[6vw]"
    >
      <div className="flex flex-col gap-8 items-start">
        {left.map((el, i) => (
          <RenderElement key={`l-${i}`} el={el} />
        ))}
      </div>
      <div className="flex flex-col gap-8">
        {right.map((el, i) => (
          <RenderElement key={`r-${i}`} el={el} />
        ))}
      </div>
    </motion.div>
  );
}
