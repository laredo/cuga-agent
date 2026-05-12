import { motion } from 'framer-motion';
import { slideChild } from '../../lib/motion';
import type { Element } from '../../slides/types';

export function Headline({
  text,
  compact = false,
}: {
  text: string;
  compact?: boolean;
}) {
  return (
    <motion.h1
      variants={slideChild}
      className={`font-display font-semibold text-ink tracking-tight ${
        compact
          ? 'text-[clamp(2.2rem,4.8vw,4.4rem)] leading-[1.1] pb-1'
          : 'text-[clamp(3rem,7vw,6.5rem)] leading-[1.02]'
      }`}
    >
      {text}
    </motion.h1>
  );
}

export function Body({
  text,
  compact = false,
}: {
  text: string;
  compact?: boolean;
}) {
  return (
    <motion.p
      variants={slideChild}
      className={`text-dim leading-snug max-w-[48ch] ${
        compact
          ? 'text-[clamp(1.1rem,1.7vw,1.6rem)]'
          : 'text-[clamp(1.4rem,2.2vw,2.2rem)]'
      }`}
    >
      {text}
    </motion.p>
  );
}

export function Quote({ text, cite }: { text: string; cite?: string }) {
  return (
    <motion.figure variants={slideChild} className="max-w-[34ch]">
      <blockquote className="font-display italic text-ink leading-[1.12] text-[clamp(2rem,4.2vw,4rem)]">
        &ldquo;{text}&rdquo;
      </blockquote>
      {cite && (
        <figcaption className="mt-6 text-dim text-xl">— {cite}</figcaption>
      )}
    </motion.figure>
  );
}

export function Bullets({ items }: { items: string[] }) {
  return (
    <ul className="space-y-5">
      {items.map((item, i) => (
        <motion.li
          key={i}
          variants={slideChild}
          className="flex items-baseline gap-4 text-ink text-[clamp(1.4rem,2.4vw,2.6rem)] leading-tight"
        >
          <span className="text-accent/80 shrink-0">›</span>
          <span>{item}</span>
        </motion.li>
      ))}
    </ul>
  );
}

export function Code({
  language,
  source,
}: {
  language: string;
  source: string;
}) {
  return (
    <motion.pre
      variants={slideChild}
      className="font-mono text-[clamp(0.8rem,1.05vw,1.05rem)] leading-[1.45] text-ink/90 bg-white/[0.03] ring-1 ring-white/10 rounded-lg px-8 py-6 max-w-[90ch] max-h-[72vh] overflow-auto"
      data-lang={language}
    >
      <code>{source}</code>
    </motion.pre>
  );
}

export function Panel({
  title,
  body,
  tag,
  icon,
}: {
  title: string;
  body: string;
  tag?: string;
  icon?: string;
}) {
  return (
    <motion.div
      variants={slideChild}
      className="bg-white/[0.04] ring-1 ring-white/10 rounded-xl p-8 flex flex-col gap-4"
    >
      <div className="flex items-center gap-4">
        {icon && (
          <span
            className="text-accent/90 shrink-0"
            dangerouslySetInnerHTML={{ __html: icon }}
          />
        )}
        {tag && (
          <span className="text-accent/80 font-mono uppercase tracking-[0.15em] text-xs">
            {tag}
          </span>
        )}
      </div>
      <h3 className="font-display font-semibold text-ink text-[clamp(1.6rem,2.6vw,2.4rem)] leading-tight">
        {title}
      </h3>
      <p className="text-dim text-[clamp(1rem,1.5vw,1.4rem)] leading-snug">
        {body}
      </p>
    </motion.div>
  );
}

export function Chips({ items }: { items: string[] }) {
  return (
    <motion.ul
      variants={slideChild}
      className="flex flex-wrap gap-3 justify-center max-w-[60ch]"
    >
      {items.map((item, i) => (
        <li
          key={i}
          className="font-mono text-[clamp(0.9rem,1.2vw,1.15rem)] text-dim px-4 py-2 rounded-full ring-1 ring-white/15 bg-white/[0.04]"
        >
          {item}
        </li>
      ))}
    </motion.ul>
  );
}

export function Figure({ svg, caption }: { svg: string; caption?: string }) {
  return (
    <motion.figure variants={slideChild} className="flex flex-col gap-4 items-center text-accent/80">
      <div
        className="max-w-[70vw] max-h-[50vh] [&_svg]:w-auto [&_svg]:h-auto [&_svg]:max-w-full [&_svg]:max-h-full"
        dangerouslySetInnerHTML={{ __html: svg }}
      />
      {caption && <figcaption className="text-dim text-xl">{caption}</figcaption>}
    </motion.figure>
  );
}

export function RenderElement({ el }: { el: Element }) {
  switch (el.kind) {
    case 'headline':
      return <Headline text={el.text} />;
    case 'body':
      return <Body text={el.text} />;
    case 'quote':
      return <Quote text={el.text} cite={el.cite} />;
    case 'bullets':
      return <Bullets items={el.items} />;
    case 'code':
      return <Code language={el.language} source={el.source} />;
    case 'figure':
      return <Figure svg={el.svg} caption={el.caption} />;
    case 'panel':
      return <Panel title={el.title} body={el.body} tag={el.tag} icon={el.icon} />;
    case 'chips':
      return <Chips items={el.items} />;
  }
}
