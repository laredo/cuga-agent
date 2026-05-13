import type { Slide } from './types';
import {
  ICON_BULLETIN,
  ICON_SCOUT,
  ICON_DIGEST,
  ICON_SWARM,
  KB_FLOW,
  SWARM_FANOUT,
} from './icons';

const sanitycheckToml = `[configuration]
name    = "sanity_check_swarm"
pattern = "swarm"

[[agents]]
id    = "dispatcher"
role  = "entry"
peers = ["internal_auditor", "external_benchmarker"]

[[agents]]
id               = "internal_auditor"
role             = "worker"
enable_knowledge = true   # reads KB built by background skills

[[agents]]
id    = "external_benchmarker"
role  = "worker"
[[agents.mcp_servers]]
name  = "cuga-web"        # live web access

[[edges]]
from = "dispatcher"
to   = "internal_auditor"
mode = "one_way"

[[edges]]
from = "dispatcher"
to   = "external_benchmarker"
mode = "one_way"`;

export const slides: Slide[] = [

  // ── 1. The gap ────────────────────────────────────────────────────────────
  {
    id: 'gap',
    aliases: ['opening', 'start', 'problem', 'the gap', 'consumer', 'enterprise'],
    layout: 'left',
    elements: [
      { kind: 'headline', text: 'CUGA is powerful.\nGetting to it isn\'t.' },
      {
        kind: 'body',
        text: 'Consumer agents are everywhere. They listen on your channels, act on a schedule, and can field a team when needed. CUGA was enterprise-grade but missing all three.',
      },
      {
        kind: 'chips',
        items: ['channel connectivity', 'scheduled execution', 'multi-agent coordination'],
      },
    ],
  },

  // ── 2. Two builders ───────────────────────────────────────────────────────
  {
    id: 'two',
    aliases: ['two builders', 'two visions', 'instincts', 'personal vs swarm', 'origin'],
    layout: 'centered',
    elements: [
      { kind: 'headline', text: 'Two builders. Two instincts.' },
      {
        kind: 'body',
        text: 'One wanted a personal assistant — background skills that quietly build context. The other wanted a coordination layer — a team of agents that reasons together on demand.',
      },
      {
        kind: 'body',
        text: 'Same platform. Different mental models. That tension is where the interesting parts came from.',
      },
    ],
  },

  // ── 3. Common foundation ──────────────────────────────────────────────────
  {
    id: 'foundation',
    aliases: ['common', 'shared', 'foundation', 'what we needed', 'overlap', 'both'],
    layout: 'grid',
    elements: [
      { kind: 'headline', text: 'What both paths needed.' },
      {
        kind: 'panel',
        icon: ICON_DIGEST,
        title: 'Slack gateway',
        body: 'A persistent connection where events arrive and results post back. Both sides start and end here.',
        tag: 'shared channel',
      },
      {
        kind: 'panel',
        icon: ICON_SCOUT,
        title: 'Knowledge base',
        body: 'Skills write. Swarms read. One SQLite store lets passive work inform active reasoning.',
        tag: 'shared memory',
      },
      {
        kind: 'panel',
        icon: ICON_SWARM,
        title: 'Agent topology',
        body: 'Whether it\'s one skill or a team of four, both declare agents, roles, and tools the same way.',
        tag: 'shared format',
      },
    ],
  },

  // ── 4. Maya ───────────────────────────────────────────────────────────────
  {
    id: 'maya',
    aliases: ['meet maya', 'maya', 'persona', 'user story', 'the user'],
    layout: 'centered',
    elements: [
      { kind: 'headline', text: 'Meet Maya.' },
      {
        kind: 'body',
        text: 'Competitor pulse. Sanity check on her proposal. Weekly update drafted. Twenty minutes, one tool: Slack.',
      },
      {
        kind: 'body',
        text: 'The personal skills build her context every day. The swarm uses it the moment she asks.',
      },
    ],
  },

  // ── 5. Three skills ───────────────────────────────────────────────────────
  {
    id: 'skills',
    aliases: ['three skills', 'skills', 'always on', 'background', 'personal layer'],
    layout: 'grid',
    elements: [
      { kind: 'headline', text: 'Three skills. Always on.' },
      {
        kind: 'panel',
        icon: ICON_BULLETIN,
        title: 'bulletin',
        body: 'Drafts the weekly update on a schedule. Posts to Slack for approval before sending anywhere.',
        tag: 'cron → approval gate',
      },
      {
        kind: 'panel',
        icon: ICON_SCOUT,
        title: 'product-scout',
        body: 'Searches the web for product news. Fact-checks sources and scores them 1–5 before storing.',
        tag: 'web → KB',
      },
      {
        kind: 'panel',
        icon: ICON_DIGEST,
        title: 'channel-digest',
        body: 'Summarises Slack channel history day by day. Triggered on schedule or on demand.',
        tag: 'Slack → KB',
      },
    ],
  },

  // ── 6. Act 1: KB builds ───────────────────────────────────────────────────
  {
    id: 'arc',
    aliases: ['act one', 'act 1', 'context', 'accumulates', 'knowledge', 'kb', 'builds'],
    layout: 'split',
    elements: [
      { kind: 'headline', text: 'Act 1: context accumulates.' },
      { kind: 'figure', svg: KB_FLOW },
      {
        kind: 'bullets',
        items: [
          'product-scout stores vetted findings as product-scout::<title>',
          'channel-digest stores daily summaries as channel-digest::<date>',
          'A research swarm can fact-check and score before storing',
          'All writes land in one shared SQLite KB',
        ],
      },
    ],
  },

  // ── 7. Act 2: Sanity check ────────────────────────────────────────────────
  {
    id: 'swarm',
    aliases: ['act two', 'act 2', 'sanity', 'adversarial', 'concurrent', 'review', 'swarm'],
    layout: 'split',
    elements: [
      { kind: 'headline', text: 'Act 2: adversarial review.' },
      { kind: 'figure', svg: SWARM_FANOUT },
      {
        kind: 'bullets',
        items: [
          '"@bot sanity check this proposal" — one message, one swarm',
          'internal_auditor searches the KB Maya\'s skills built',
          'external_benchmarker searches the live web',
          'Both post findings to the same Slack thread',
        ],
      },
    ],
  },

  // ── 8. Why two agents ─────────────────────────────────────────────────────
  {
    id: 'why',
    aliases: ['why two', 'why', 'rationalise', 'rationalize', 'adversarial split', 'one agent'],
    layout: 'centered',
    elements: [
      { kind: 'headline', text: 'One agent rationalises.' },
      {
        kind: 'quote',
        text: 'Give it both KB and web access — it finds supporting evidence from everywhere. The adversarial split only works when the agents are separate.',
      },
    ],
  },

  // ── 9. TOML ───────────────────────────────────────────────────────────────
  {
    id: 'toml',
    aliases: ['topology', 'toml', 'config', 'one file', 'declare', 'technology', 'format'],
    layout: 'code',
    elements: [
      { kind: 'headline', text: 'One TOML file. Two agents.' },
      {
        kind: 'code',
        language: 'toml',
        source: sanitycheckToml,
      },
      {
        kind: 'body',
        text: 'Declare the pattern, the agents, and the edges. The runtime wires the rest.',
      },
    ],
  },

  // ── 10. Dev approach ─────────────────────────────────────────────────────
  {
    id: 'approach',
    aliases: ['how we built it', 'dev approach', 'process', 'converge', 'merge', 'reconcile', 'vibe'],
    layout: 'left',
    elements: [
      { kind: 'headline', text: 'How we built it.' },
      {
        kind: 'bullets',
        items: [
          'Started from the same idea. Coded independently.',
          'Parallel solutions to the same problems: the KB client, the event loop, the Slack adapter.',
          'Some deliberate reuse. Some vibe-coded duplication that did the same thing twice.',
          'Merged the two branches. Kept the best of each side.',
        ],
      },
    ],
  },

  // ── 11. Close ─────────────────────────────────────────────────────────────
  {
    id: 'close',
    aliases: ['done', 'end', 'final', 'pitch', 'close', 'closing'],
    layout: 'left',
    elements: [
      { kind: 'headline', text: 'Skills remember.\nSwarms reason.' },
      {
        kind: 'body',
        text: 'Context builds quietly every day. One message deploys a team that uses it.',
      },
    ],
  },

];

export const CLEAR_KEYWORDS = new Set(['clear', 'reset', '.', 'blank']);
