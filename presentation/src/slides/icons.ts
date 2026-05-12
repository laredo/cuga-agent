// Inline SVGs for slide visuals. All stroke-based, use currentColor so they
// pick up the accent or ink color from Tailwind.

export const CHAT_EXCHANGE = `
<svg viewBox="0 0 280 110" width="340" height="134" fill="none"
     stroke="currentColor" stroke-width="1.6"
     stroke-linejoin="round" stroke-linecap="round">
  <rect x="14" y="14" width="100" height="56" rx="14"/>
  <path d="M32 70 L40 86 L58 70"/>
  <circle cx="42" cy="42" r="2.2" fill="currentColor"/>
  <circle cx="64" cy="42" r="2.2" fill="currentColor"/>
  <circle cx="86" cy="42" r="2.2" fill="currentColor"/>
  <rect x="166" y="14" width="100" height="56" rx="14"/>
  <path d="M222 70 L230 86 L248 70"/>
  <circle cx="194" cy="42" r="2.2" fill="currentColor"/>
  <circle cx="216" cy="42" r="2.2" fill="currentColor"/>
  <circle cx="238" cy="42" r="2.2" fill="currentColor"/>
  <path d="M122 34 L158 34 M152 30 L158 34 L152 38" opacity="0.55"/>
  <path d="M158 54 L122 54 M128 50 L122 54 L128 58" opacity="0.55"/>
</svg>`;

export const RADAR_PULSE = `
<svg viewBox="0 0 180 180" width="240" height="240" fill="none"
     stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
  <circle cx="90" cy="90" r="80" opacity="0.08"/>
  <circle cx="90" cy="90" r="64" opacity="0.14"/>
  <circle cx="90" cy="90" r="48" opacity="0.22"/>
  <circle cx="90" cy="90" r="32" opacity="0.4"/>
  <circle cx="90" cy="90" r="18" opacity="0.7"/>
  <circle cx="90" cy="90" r="4" fill="currentColor"/>
  <circle cx="32" cy="40" r="2" fill="currentColor" opacity="0.6"/>
  <circle cx="150" cy="58" r="2" fill="currentColor" opacity="0.6"/>
  <circle cx="154" cy="138" r="2" fill="currentColor" opacity="0.6"/>
  <circle cx="28" cy="134" r="2" fill="currentColor" opacity="0.6"/>
</svg>`;

export const ICON_BULLETIN = `
<svg viewBox="0 0 24 24" width="28" height="28" fill="none"
     stroke="currentColor" stroke-width="1.6"
     stroke-linecap="round" stroke-linejoin="round">
  <path d="M14 3 H6 V21 H18 V7 Z"/>
  <path d="M14 3 V7 H18"/>
  <line x1="9" y1="12" x2="15" y2="12" opacity="0.55"/>
  <line x1="9" y1="15" x2="15" y2="15" opacity="0.55"/>
  <line x1="9" y1="18" x2="13" y2="18" opacity="0.55"/>
</svg>`;

export const ICON_SCOUT = `
<svg viewBox="0 0 24 24" width="28" height="28" fill="none"
     stroke="currentColor" stroke-width="1.6"
     stroke-linecap="round" stroke-linejoin="round">
  <circle cx="11" cy="11" r="7"/>
  <line x1="16.5" y1="16.5" x2="21" y2="21"/>
</svg>`;

export const ICON_DIGEST = `
<svg viewBox="0 0 24 24" width="28" height="28" fill="none"
     stroke="currentColor" stroke-width="1.6"
     stroke-linecap="round" stroke-linejoin="round">
  <rect x="3" y="4" width="18" height="16" rx="3"/>
  <line x1="7"  y1="9"  x2="17" y2="9"  opacity="0.7"/>
  <line x1="7"  y1="13" x2="14" y2="13" opacity="0.5"/>
  <line x1="7"  y1="17" x2="11" y2="17" opacity="0.35"/>
</svg>`;

export const ICON_SWARM = `
<svg viewBox="0 0 24 24" width="28" height="28" fill="none"
     stroke="currentColor" stroke-width="1.6"
     stroke-linecap="round" stroke-linejoin="round">
  <circle cx="5"  cy="12" r="2.2"/>
  <circle cx="19" cy="6"  r="2.2"/>
  <circle cx="19" cy="18" r="2.2"/>
  <line x1="7"  y1="11" x2="17" y2="7"/>
  <line x1="7"  y1="13" x2="17" y2="17"/>
</svg>`;

// KB accumulation: three sources → shared KB → sanity check
export const KB_FLOW = `
<svg viewBox="0 0 520 180" width="560" height="194" fill="none"
     stroke="currentColor" stroke-width="1.5"
     stroke-linecap="round" stroke-linejoin="round">
  <defs>
    <marker id="kbArrow" viewBox="0 0 10 10" refX="8" refY="5"
            markerWidth="7" markerHeight="7" orient="auto">
      <path d="M0 1 L9 5 L0 9 Z" fill="currentColor" stroke="none" opacity="0.65"/>
    </marker>
  </defs>
  <g transform="translate(0 14)">
    <rect x="0" y="0" width="128" height="36" rx="10" opacity="0.12"/>
    <rect x="0" y="0" width="128" height="36" rx="10"/>
    <text x="64" y="22" text-anchor="middle" font-family="JetBrains Mono, monospace"
          font-size="11" fill="currentColor" stroke="none">product-scout</text>
  </g>
  <g transform="translate(0 72)">
    <rect x="0" y="0" width="128" height="36" rx="10" opacity="0.12"/>
    <rect x="0" y="0" width="128" height="36" rx="10"/>
    <text x="64" y="22" text-anchor="middle" font-family="JetBrains Mono, monospace"
          font-size="11" fill="currentColor" stroke="none">channel-digest</text>
  </g>
  <g transform="translate(0 130)">
    <rect x="0" y="0" width="128" height="36" rx="10" opacity="0.12"/>
    <rect x="0" y="0" width="128" height="36" rx="10"/>
    <text x="64" y="22" text-anchor="middle" font-family="JetBrains Mono, monospace"
          font-size="11" fill="currentColor" stroke="none">research-swarm</text>
  </g>
  <line x1="130" y1="32"  x2="196" y2="80"  opacity="0.5" marker-end="url(#kbArrow)"/>
  <line x1="130" y1="90"  x2="196" y2="90"  opacity="0.5" marker-end="url(#kbArrow)"/>
  <line x1="130" y1="148" x2="196" y2="100" opacity="0.5" marker-end="url(#kbArrow)"/>
  <g transform="translate(198 62)">
    <rect x="0" y="0" width="110" height="56" rx="14" opacity="0.18"/>
    <rect x="0" y="0" width="110" height="56" rx="14"/>
    <text x="55" y="27" text-anchor="middle" font-family="Inter, sans-serif"
          font-size="13" fill="currentColor" stroke="none">shared KB</text>
    <text x="55" y="44" text-anchor="middle" font-family="JetBrains Mono, monospace"
          font-size="10" fill="currentColor" stroke="none" opacity="0.6">SQLite</text>
  </g>
  <line x1="310" y1="90" x2="376" y2="90" opacity="0.5" marker-end="url(#kbArrow)"/>
  <g transform="translate(378 62)">
    <rect x="0" y="0" width="128" height="56" rx="14" opacity="0.18"/>
    <rect x="0" y="0" width="128" height="56" rx="14"/>
    <text x="64" y="27" text-anchor="middle" font-family="Inter, sans-serif"
          font-size="13" fill="currentColor" stroke="none">sanity check</text>
    <text x="64" y="44" text-anchor="middle" font-family="JetBrains Mono, monospace"
          font-size="10" fill="currentColor" stroke="none" opacity="0.6">reads all namespaces</text>
  </g>
</svg>`;

// Swarm fan-out: dispatcher → two concurrent workers → NOTIFY_SLACK
export const SWARM_FANOUT = `
<svg viewBox="0 0 480 180" width="520" height="194" fill="none"
     stroke="currentColor" stroke-width="1.5"
     stroke-linecap="round" stroke-linejoin="round">
  <defs>
    <marker id="swarmArrow" viewBox="0 0 10 10" refX="8" refY="5"
            markerWidth="7" markerHeight="7" orient="auto">
      <path d="M0 1 L9 5 L0 9 Z" fill="currentColor" stroke="none" opacity="0.65"/>
    </marker>
  </defs>
  <g transform="translate(10 68)">
    <rect x="0" y="0" width="112" height="44" rx="12" opacity="0.16"/>
    <rect x="0" y="0" width="112" height="44" rx="12"/>
    <text x="56" y="28" text-anchor="middle" font-family="JetBrains Mono, monospace"
          font-size="11" fill="currentColor" stroke="none">dispatcher</text>
  </g>
  <line x1="124" y1="82"  x2="192" y2="44"  opacity="0.55" marker-end="url(#swarmArrow)"/>
  <line x1="124" y1="98"  x2="192" y2="136" opacity="0.55" marker-end="url(#swarmArrow)"/>
  <g transform="translate(194 16)">
    <rect x="0" y="0" width="140" height="44" rx="12" opacity="0.14"/>
    <rect x="0" y="0" width="140" height="44" rx="12"/>
    <text x="70" y="28" text-anchor="middle" font-family="JetBrains Mono, monospace"
          font-size="11" fill="currentColor" stroke="none">internal_auditor</text>
  </g>
  <g transform="translate(194 120)">
    <rect x="0" y="0" width="140" height="44" rx="12" opacity="0.14"/>
    <rect x="0" y="0" width="140" height="44" rx="12"/>
    <text x="70" y="28" text-anchor="middle" font-family="JetBrains Mono, monospace"
          font-size="11" fill="currentColor" stroke="none">ext_benchmarker</text>
  </g>
  <line x1="336" y1="38"  x2="372" y2="38"  opacity="0.45" marker-end="url(#swarmArrow)"/>
  <line x1="336" y1="142" x2="372" y2="142" opacity="0.45" marker-end="url(#swarmArrow)"/>
  <text x="376" y="35" font-family="JetBrains Mono, monospace"
        font-size="10" fill="currentColor" stroke="none" opacity="0.7">🏛️ audit</text>
  <text x="376" y="50" font-family="JetBrains Mono, monospace"
        font-size="9"  fill="currentColor" stroke="none" opacity="0.45">NOTIFY_SLACK</text>
  <text x="376" y="139" font-family="JetBrains Mono, monospace"
        font-size="10" fill="currentColor" stroke="none" opacity="0.7">🌐 benchmark</text>
  <text x="376" y="154" font-family="JetBrains Mono, monospace"
        font-size="9"  fill="currentColor" stroke="none" opacity="0.45">NOTIFY_SLACK</text>
  <text x="264" y="96" font-family="Inter, sans-serif"
        font-size="11" fill="currentColor" stroke="none" opacity="0.4"
        font-style="italic" text-anchor="middle">concurrent</text>
</svg>`;
