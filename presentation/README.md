# presentation

Keyword-driven slide app for the sidecar hackathon talk. Type a word at the top — the matching slide animates in. Unknown keywords fall through to an LLM and come back as a generated slide.

This is only the **talk half**. The live demo (real sidecar + real GitHub + real toasts) runs separately on your desktop; this webapp never touches it.

## Quick start

```bash
cd presentation
npm install
npm run dev       # http://localhost:5173
```

For the LLM fallback: copy `.env.example` → `.env` and fill in `VITE_OPENAI_API_KEY` (and the base URL + model if you're not using the defaults). Without a key, authored slides still work; unknown keywords show a friendly "no fallback configured" message.

```bash
cp .env.example .env
# edit .env
```

## How to use it on stage

Just type. As soon as what you've typed matches an authored keyword (or alias), the slide animates in. The text stays in the input — keep typing or start a new word. Empty the input to return to idle. Off-script keyword? Press `Enter` to send it to the LLM.

| Key | What it does |
|---|---|
| _any printable_ | Live-matches authored keywords on every keystroke |
| `Enter` | Send the current text to the LLM fallback (only needed for off-script words) |
| `PgDn` / `PgUp` | Step through authored slides in script order — pairs with any presenter clicker |
| `→` / `↓` / `←` / `↑` | Also step through, but only when the input is empty (otherwise they move the caret) |
| `Esc` | Close the hint overlay if open; otherwise just refocus the input (no clearing) |
| `Cmd-K` / `Ctrl-K` | Focus the input from anywhere |
| `Cmd-/` / `Ctrl-/` | Toggle the overlay listing all authored keywords |
| `F11` | Browser-native fullscreen |

Built-in reset tokens: `clear`, `reset`, `.`, `blank` — typing any of them returns the canvas to idle without pressing Esc.

## The authored slides

Seven pre-authored slides, tuned to the 2-minute script:

| Keyword | Aliases | When to type it |
|---|---|---|
| `pen pal` | `penpal`, `problem`, `pen-pal` | Opening — the problem with reactive agents |
| `ambient` | `value`, `ambient agents`, `watch` | The value claim |
| `skill` | `skill file`, `one file`, `one skill`, `dx`, `the file` | Show the actual `issue-triage.md` on screen |
| `weather` | `backdrop`, `ambience` | When calling out that the demo is background weather |
| `four` | `four skills`, `skills`, `running`, `fleet` | Roll call of the four skills |
| `close` | `pitch`, `end`, `done`, `final` | The closer |
| `clear` | `reset`, `.`, `blank` | Blank the canvas between beats |

## Authoring a new slide

Edit `src/slides/content.ts`. Vite HMR picks up changes live. One entry:

```ts
{
  id: 'my keyword',
  aliases: ['another-keyword'],
  layout: 'centered',                // centered | split | grid | code | fullbleed
  elements: [
    { kind: 'headline', text: 'Say this loud.' },
    { kind: 'body', text: 'Say this smaller.' },
  ],
},
```

Element kinds: `headline`, `body`, `quote`, `bullets`, `code`, `panel`, `figure`. See `src/slides/types.ts` for the full shape of each. Each layout picks what it renders — e.g. `grid` expects one `headline` plus any number of `panel`s.

## LLM fallback

Any unknown keyword triggers an OpenAI-compatible `/v1/chat/completions` call. Same wire format CUGA uses, so you can point at the same LiteLLM proxy with the same credentials. The model returns `{ title, bullets }` and a fallback layout renders them with a shimmer placeholder while it waits.

Env vars (same names CUGA uses, prefixed with `VITE_` so Vite exposes them to the browser):

| Var | Default |
|---|---|
| `VITE_OPENAI_API_KEY` | (required for fallback to work) |
| `VITE_OPENAI_BASE_URL` | `https://api.openai.com/v1` |
| `VITE_MODEL_NAME` | `aws/claude-haiku-4-5` |

For IBM's LiteLLM proxy, the defaults in `.env.example` already work:

```
VITE_OPENAI_API_KEY=sk-...
VITE_OPENAI_BASE_URL=https://ete-litellm.bx.cloud9.ibm.com
VITE_MODEL_NAME=aws/claude-haiku-4-5
```

Base URL handling follows the OpenAI SDK: a trailing `/v1` is optional — `https://foo/v1` and `https://foo` both resolve to `https://foo/v1/chat/completions`.

### Security note

The API key is bundled into the JS at build time and visible in devtools. **Do not deploy a built version anywhere public** with a real key. This app is meant to run locally on the presenter's laptop and be closed when the talk is over. Regenerate or revoke the key if the machine is ever compromised.

### CORS

The browser makes the request directly to your proxy. If the proxy doesn't set permissive CORS headers for `http://localhost:5173`, you'll see a CORS error in devtools. IBM's ete-litellm instance currently allows it; if yours doesn't, either enable CORS on the proxy or add a Vite dev-server proxy in `vite.config.ts`.

## Production build

```bash
npm run build     # outputs dist/
npm run preview   # serve dist/ on localhost:4173
```

Useful as a backup: if the dev server misbehaves on stage, `npm run preview` serves a static snapshot.

## Keeping the `skill` slide in sync

The code-layout slide embeds the actual `sidecar/skills/issue-triage.md` content inline in `src/slides/content.ts` (as a template literal). If the real skill file changes, update the template literal too. The audience should see the real artifact, not a stale copy.

## Layout

```
presentation/
  src/
    App.tsx                       composition + hotkeys
    components/
      KeywordInput.tsx            sticky top input
      Canvas.tsx                  AnimatePresence wrapper
      HintOverlay.tsx             '?' overlay
      slideLayouts/
        Centered / Split / Grid / Code / Fullbleed / Fallback  one per layout
        Elements.tsx              shared element renderers
    slides/
      content.ts                  authored slides (edit me)
      index.ts                    resolve(keyword) + authoredKeywords()
      types.ts                    Slide, Element, LayoutKind
    lib/
      normalize.ts                keyword normalization
      motion.ts                   Framer Motion variants
      anthropic.ts                LLM fallback
```
