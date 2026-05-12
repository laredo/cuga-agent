// Off-script keyword → generated slide. Uses an OpenAI-compatible
// /v1/chat/completions endpoint, so it works against the real
// OpenAI API or a LiteLLM proxy (same env-var shape CUGA uses).
//
// Non-streaming: Haiku through LiteLLM is ~1-2s, and the shimmer
// placeholder covers the round-trip.

export type FallbackContent = { title: string; bullets: string[] };

type Env = {
  apiKey: string | undefined;
  baseUrl: string;
  model: string;
};

function readEnv(): Env {
  return {
    apiKey: import.meta.env.VITE_OPENAI_API_KEY,
    baseUrl:
      import.meta.env.VITE_OPENAI_BASE_URL || 'https://api.openai.com/v1',
    model: import.meta.env.VITE_MODEL_NAME || 'aws/claude-haiku-4-5',
  };
}

// Accept base URLs with or without a trailing /v1, matching the
// OpenAI Python/JS SDK behavior. Strips any trailing slashes first.
function endpoint(baseUrl: string): string {
  const trimmed = baseUrl.replace(/\/+$/, '');
  const path = trimmed.endsWith('/v1')
    ? '/chat/completions'
    : '/v1/chat/completions';
  return trimmed + path;
}

const SYSTEM_PROMPT = `You are helping a live presenter who is demoing a project called "sidecar" — \
a trigger-driven skills runtime that makes an agent (CUGA) react to events \
(file drops, GitHub issues, calendar invites, etc.) and perform side effects \
(write files, post comments, fire desktop notifications).

The talk is framed around two ideas:
 1. AMBIENT AGENTS — agents that watch the world and act, not pen-pals you type to.
 2. ONE MARKDOWN FILE PER SKILL — trigger + skill body + effects all in one short file.

The presenter types a keyword at the top of their slide tool. Unknown keywords \
come to you. Improvise a short "slide" of content that would support the talk.

Respond with ONLY a JSON object — no prose, no code fences — of this shape:
{
  "title": "<a short display-font title, under 9 words>",
  "bullets": ["<bullet 1, under 12 words>", "<bullet 2>", ..., "<bullet 5 max>"]
}
At least 3 bullets, at most 5. Punchy, presentation-tone, no hedging.`;

export class MissingApiKeyError extends Error {
  constructor() {
    super('No VITE_OPENAI_API_KEY set; fallback disabled.');
  }
}

export async function improviseSlide(
  keyword: string,
  signal?: AbortSignal,
): Promise<FallbackContent> {
  const { apiKey, baseUrl, model } = readEnv();
  if (!apiKey) throw new MissingApiKeyError();

  const res = await fetch(endpoint(baseUrl), {
    method: 'POST',
    signal,
    headers: {
      'content-type': 'application/json',
      authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model,
      max_tokens: 400,
      messages: [
        { role: 'system', content: SYSTEM_PROMPT },
        { role: 'user', content: `Keyword: ${keyword}` },
      ],
    }),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`LLM ${res.status}: ${text.slice(0, 200)}`);
  }

  const json = (await res.json()) as {
    choices?: { message?: { content?: string } }[];
  };
  const raw = json.choices?.[0]?.message?.content ?? '';
  return parseFallback(raw);
}

function parseFallback(raw: string): FallbackContent {
  const cleaned = raw
    .trim()
    .replace(/^```(?:json)?\s*/i, '')
    .replace(/\s*```$/i, '')
    .trim();

  let parsed: unknown;
  try {
    parsed = JSON.parse(cleaned);
  } catch {
    throw new Error('model returned non-JSON');
  }

  if (
    !parsed ||
    typeof parsed !== 'object' ||
    typeof (parsed as { title?: unknown }).title !== 'string' ||
    !Array.isArray((parsed as { bullets?: unknown }).bullets)
  ) {
    throw new Error('model JSON missing fields');
  }

  const { title, bullets } = parsed as { title: string; bullets: unknown[] };
  return {
    title,
    bullets: bullets
      .filter((b): b is string => typeof b === 'string')
      .slice(0, 5),
  };
}
