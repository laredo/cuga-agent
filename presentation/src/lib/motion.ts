import type { Variants } from 'framer-motion';

export const slideContainer: Variants = {
  initial: { opacity: 0, x: 32 },
  enter: {
    opacity: 1,
    x: 0,
    transition: {
      staggerChildren: 0.09,
      delayChildren: 0.05,
      when: 'beforeChildren',
      duration: 0.48,
      ease: [0.22, 1, 0.36, 1],
    },
  },
  exit: {
    opacity: 0,
    x: -20,
    transition: { duration: 0.2, ease: 'easeIn' },
  },
};

export const slideChild: Variants = {
  initial: { opacity: 0, y: 20, filter: 'blur(5px)' },
  enter: {
    opacity: 1,
    y: 0,
    filter: 'blur(0px)',
    transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] },
  },
  exit: {
    opacity: 0,
    filter: 'blur(3px)',
    transition: { duration: 0.16, ease: 'easeOut' },
  },
};
