import { motion } from 'framer-motion';
import { slideContainer } from '../../lib/motion';
import { RenderElement } from './Elements';
import type { Slide } from '../../slides/types';

export default function Fullbleed({ slide }: { slide: Slide }) {
  return (
    <motion.div
      key={slide.id}
      variants={slideContainer}
      initial="initial"
      animate="enter"
      exit="exit"
      className="h-full w-full flex flex-col items-center justify-center gap-8 px-[4vw]"
    >
      {slide.elements.map((el, i) => (
        <RenderElement key={i} el={el} />
      ))}
    </motion.div>
  );
}
