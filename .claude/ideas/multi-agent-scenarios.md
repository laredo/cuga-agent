# Multi-Agent Showcase Ideas

Evaluation criteria: (1) hard or impossible with a single agent, (2) the P2P split clicks immediately when you describe it.

**Status:** Option C is **deployed** as `skills/swarms/sanity-check/`. Options A, B, D remain brainstormed but not built.

---

## Option A: Competitive Pre-Brief *(brainstormed — not built)*

**Trigger:** Maya needs a competitor pulse before a VP meeting.

> `@cuga give me a competitor pulse before my 2pm`

**Agents:**
- `market_sentinel` (entry) — web search, finds what competitors shipped in the last 2 weeks
- `product_strategist` (exit) — reads KB, cross-references competitor intel against Maya's roadmap, produces a battle card

**Why two agents:** `market_sentinel` has live web access but no product context. `product_strategist` has the KB but no web access. Neither can do the other's job.

**Wow moment:** `product_strategist` catches that CompetitorX just shipped something that directly overlaps an unreleased roadmap item — a finding neither agent could surface alone.

**Builds on:** product-scout KB + web search tools already in place.

**Weakness:** A single agent with both tools could technically do this. The "why two" story requires explanation.

---

## Option B: On-Call Incident Triage *(brainstormed — not built)*

**Trigger:** Something broke. Maya needs to understand what happened fast.

> `@cuga what caused the outage at 5pm?`

**Agents:**
- `signal_reader` — scans Slack channels for deploys, errors, config changes in the time window. Builds a factual "what changed" timeline.
- `runbook_matcher` — searches KB for past incidents, known failure modes, runbooks. Given the timeline, identifies what this looks like and what to do.

**Why it clicks immediately:** "The person triaging and the person who remembers all past incidents are rarely the same. You always call someone." That call is the P2P pattern.

**Why it's hard alone:** A single agent blends the two investigations — it anchors on a familiar pattern early and stops looking at the signals objectively. The P2P structure forces `signal_reader` to be unbiased about the evidence *before* `runbook_matcher` applies pattern recognition. The handoff is the discipline.

**Genuine back-and-forth:** `runbook_matcher` can say "given this pattern, look specifically for X in the timeline" — `signal_reader` goes back to Slack to verify. True P2P, not just sequential.

**Audience:** Strongest for technical audiences (engineers, on-call folks).

---

## Option C: Pre-Decision Sanity Check ✅ **DEPLOYED** (`skills/swarms/sanity-check/`)

**Trigger:** Maya is about to propose a major initiative — roadmap pivot, new feature direction, process change — and wants a reality check before she pitches it.

> `@cuga sanity check this before I send it — [paste proposal]`

**Agents:**
- `internal_auditor` — searches KB and channel digests for internal history: have we tried this before? What happened? What was decided and why?
- `external_benchmarker` — web-searches: how has the industry approached this? What have others learned the hard way?

**Why it clicks immediately:** "Inside view and outside view. You always want both before a big decision — someone who knows your history and someone who knows the market. One person almost never has both."

**Why it's hard alone:** A single agent rationalizes. Give it both KB and web access and ask it to evaluate a proposal — it finds supporting evidence from both sources. The *adversarial* split (auditor is skeptical of the past, benchmarker is skeptical of the market) only works when they're separate entities.

**Wow moment:** `internal_auditor` surfaces "we tried this in Q2 2023 and it stalled because of X." `external_benchmarker` finds "Notion solved exactly X by doing Y." Combined output: "Your proposal has a known failure mode — here's the fix the industry found." Neither agent alone could produce that sentence.

**Demo arc:** Act 1 — KB is built up over the week via product-scout and channel-digest. Act 2 — sanity check draws on that KB as institutional memory. Act 1 becomes retroactively valuable.

**Requires:** KB from channel-digest/product-scout (already built), web search (already built). No new tools.

**Demo prompts (working):**
- `@bot sanity check our proposal to build a custom multi-agent orchestration layer on top of PydanticAI instead of using LangGraph.`
- `@bot sanity check: we should migrate our entire backend to a serverless architecture next quarter.`
- `@bot what do we know about agentic frameworks?` *(Knowledge Mode — internal_auditor only)*

---

## Option D: Partner / Stakeholder Meeting Prep *(brainstormed — not built)*

**Trigger:** Maya has a high-stakes external meeting.

> `@cuga prep me for my meeting with Sarah Chen, Head of Product at Acme, Monday 2pm`

**Agents:**
- `audience_researcher` — web-searches the person and company: public statements, recent news, announced priorities.
- `brief_writer` — reads KB for your product's relevant capabilities, past interactions with this account, current constraints.

**Why it clicks immediately:** "A great meeting prep requires someone who knows them and someone who knows you. That's always been two people — an assistant who researches the counterparty, and someone who knows the internal context. You compare notes."

**Why it's hard alone:** A single agent either goes deep on the audience and produces generic internal content, or knows the internal context but doesn't adapt to the audience. The output quality is strictly worse — it satisfies neither job.

**Wow moment:** `audience_researcher` finds that the counterparty just published a blog post about a problem your team solved last month. `brief_writer` pulls the relevant KB entry. The brief opens with: "Sarah just wrote about X — you shipped the answer to that in your last sprint."

**Requires:** Web search (already built), KB (already built). No new tools.

---

## Comparison

| | Clicks immediately | Hard alone | New skills needed | Demo arc |
|---|---|---|---|---|
| A: Competitive Pre-Brief | ★★★ | ★★ | none | good |
| B: Incident Triage | ★★★★★ (technical audience) | ★★★★★ | channel-history | needs incident setup |
| C: Pre-Decision Sanity Check | ★★★★★ | ★★★★★ | none | strong (uses Act 1 KB) |
| D: Meeting Prep | ★★★★★ | ★★★★ | none | moderate |
