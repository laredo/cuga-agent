import type { Slide } from './types';
import {
  ICON_BULLETIN,
  ICON_SCOUT,
  ICON_DIGEST,
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
enable_knowledge = true   # reads the KB built by skills

[[agents]]
id    = "external_benchmarker"
role  = "worker"
[[agents.mcp_servers]]
name  = "cuga-web"        # live web search

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
    aliases: ['opening', 'problem', 'the gap', 'consumer', 'enterprise'],
    layout: 'left',
    elements: [
      { kind: 'headline', text: 'CUGA is powerful.\nGetting to it isn\'t.' },
      {
        kind: 'body',
        text: 'Consumer agents are everywhere. They listen on your channels, run on a schedule, and coordinate when needed. CUGA was missing all three.',
      },
      {
        kind: 'chips',
        items: ['channel connectivity', 'event scheduling', 'multi-agent swarms'],
      },
    ],
  },

  // ── 2. Maya ───────────────────────────────────────────────────────────────
  {
    id: 'maya',
    aliases: ['meet maya', 'maya', 'persona', 'user', 'the problem'],
    layout: 'centered',
    elements: [
      { kind: 'headline', text: 'Meet Maya.' },
      {
        kind: 'body',
        text: 'Competitor pulse. Sanity check on her proposal. Weekly update drafted. Twenty minutes. One tool: Slack.',
      },
    ],
  },

  // ── 3. Three skills ───────────────────────────────────────────────────────
  {
    id: 'skills',
    aliases: ['three skills', 'skills', 'always on', 'background', 'daily'],
    layout: 'grid',
    elements: [
      { kind: 'headline', text: 'Three skills run every day.' },
      {
        kind: 'panel',
        icon: ICON_BULLETIN,
        title: 'bulletin',
        body: 'Drafts the weekly update on schedule. Posts to Slack for your approval before it goes anywhere.',
        tag: 'scheduled',
      },
      {
        kind: 'panel',
        icon: ICON_SCOUT,
        title: 'product-scout',
        body: 'Searches the web for product news. Stores vetted findings in the knowledge base.',
        tag: 'web → KB',
      },
      {
        kind: 'panel',
        icon: ICON_DIGEST,
        title: 'channel-digest',
        body: 'Summarises Slack channel history day by day. Triggered on a schedule or on demand.',
        tag: 'Slack → KB',
      },
    ],
  },

  // ── 4. Act 1: KB builds up ────────────────────────────────────────────────
  {
    id: 'arc',
    aliases: ['act one', 'act 1', 'context', 'accumulates', 'knowledge', 'kb'],
    layout: 'split',
    elements: [
      { kind: 'headline', text: 'Act 1: context accumulates.' },
      { kind: 'figure', svg: KB_FLOW },
      {
        kind: 'bullets',
        items: [
          'product-scout stores findings as product-scout::<title>',
          'channel-digest stores summaries as channel-digest::<date>',
          'All writes go to a shared SQLite KB.',
        ],
      },
    ],
  },

  // ── 5. Act 2: Sanity check swarm ─────────────────────────────────────────
  {
    id: 'swarm',
    aliases: ['act two', 'act 2', 'sanity', 'adversarial', 'concurrent', 'review'],
    layout: 'split',
    elements: [
      { kind: 'headline', text: 'Act 2: adversarial review.' },
      { kind: 'figure', svg: SWARM_FANOUT },
      {
        kind: 'bullets',
        items: [
          'internal_auditor searches the KB Maya\'s skills built.',
          'external_benchmarker searches the live web.',
          'Both run at the same time. Both post to the same Slack thread.',
        ],
      },
    ],
  },

  // ── 6. Why two agents ─────────────────────────────────────────────────────
  {
    id: 'why',
    aliases: ['why two', 'why', 'rationalise', 'rationalize', 'adversarial split'],
    layout: 'centered',
    elements: [
      { kind: 'headline', text: 'One agent rationalises.' },
      {
        kind: 'quote',
        text: 'Give it both KB and web access — it finds supporting evidence from everywhere. The adversarial split only works when the agents are separate.',
      },
    ],
  },

  // ── 7. Topology ───────────────────────────────────────────────────────────
  {
    id: 'toml',
    aliases: ['topology', 'toml', 'config', 'one file', 'declare', 'technology'],
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

  // ── 8. Close ──────────────────────────────────────────────────────────────
  {
    id: 'close',
    aliases: ['done', 'end', 'final', 'pitch', 'close', 'closing'],
    layout: 'left',
    elements: [
      { kind: 'headline', text: 'Skills remember.\nSwarms reason.' },
      {
        kind: 'body',
        text: 'Context builds every day. One message deploys a team.',
      },
    ],
  },

];

export const CLEAR_KEYWORDS = new Set(['clear', 'reset', '.', 'blank']);
