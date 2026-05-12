// Shallow structural parse of a skill .md file: finds the YAML frontmatter
// block and, within it, the `triggers:` and `hooks:` sections. Everything
// after the closing `---` is the prompt body. Ranges are inclusive,
// 0-indexed line numbers.
//
// Not a real YAML parser — we only need top-level section boundaries.
// Detects a top-level key by a line that starts with `<word>:` at column 0.

export type Range = { start: number; end: number };

export type SkillSections = {
  frontmatter: Range | null;
  trigger: Range | null;
  effects: Range | null;
  prompt: Range | null;
};

export function parseSkill(source: string): SkillSections {
  const lines = source.split('\n');

  // Find the YAML frontmatter delimiters.
  const fmStart = lines.findIndex((l) => l.trim() === '---');
  if (fmStart === -1) {
    return emptyResult(lines.length);
  }
  const fmEnd = lines.findIndex(
    (l, i) => i > fmStart && l.trim() === '---',
  );
  if (fmEnd === -1) {
    return emptyResult(lines.length);
  }

  // Inside the frontmatter, find each top-level key's range.
  const topLevelKey = /^([A-Za-z_][\w-]*)\s*:/;
  const keyLines: { key: string; line: number }[] = [];
  for (let i = fmStart + 1; i < fmEnd; i++) {
    const m = lines[i].match(topLevelKey);
    if (m) keyLines.push({ key: m[1], line: i });
  }

  function rangeFor(name: string): Range | null {
    const idx = keyLines.findIndex((k) => k.key === name);
    if (idx === -1) return null;
    const start = keyLines[idx].line;
    const end =
      idx + 1 < keyLines.length ? keyLines[idx + 1].line - 1 : fmEnd - 1;
    return { start, end };
  }

  const trigger = rangeFor('triggers');
  const effects = rangeFor('hooks');

  // Prompt: everything after the closing ---, trimmed of trailing blank lines.
  let promptStart = fmEnd + 1;
  while (promptStart < lines.length && lines[promptStart].trim() === '') {
    promptStart++;
  }
  let promptEnd = lines.length - 1;
  while (promptEnd > promptStart && lines[promptEnd].trim() === '') {
    promptEnd--;
  }
  const prompt =
    promptStart <= promptEnd ? { start: promptStart, end: promptEnd } : null;

  return {
    frontmatter: { start: fmStart, end: fmEnd },
    trigger,
    effects,
    prompt,
  };
}

function emptyResult(totalLines: number): SkillSections {
  return {
    frontmatter: null,
    trigger: null,
    effects: null,
    prompt: totalLines > 0 ? { start: 0, end: totalLines - 1 } : null,
  };
}
