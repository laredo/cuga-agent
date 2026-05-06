---
type: playbook
name: product-scout-playbook
triggers:
  - type: keyword
    value: ["scout", "search for updates", "find product news", "web scout"]
    operator: or
priority: 1
---

## Product Scout Workflow

Follow these steps to find, filter, and store recent product updates.

1. **Clarify the topic**
   - If the user's message already names a product or topic (e.g. "scout for updates about CUGA"), use that as the search subject.
   - If no topic is specified, ask: "Which product or topic should I scout for? (e.g. 'CUGA agent', 'LangGraph', 'our mobile app')"
   - Wait for the user's answer before proceeding.

2. **Run web searches**
   - Call `web_search` with 2–3 targeted queries, for example:
     - `"[topic] new features release 2025"`
     - `"[topic] product update announcement"`
     - `"[topic] changelog what's new"`
   - Collect all results into a candidate list.

3. **Filter for relevance**
   For each candidate result, ask yourself:
   - Is this **directly about** the specified product or topic? (not just a passing mention)
   - Is this **new information** — a feature, release, announcement, or meaningful update?
   - Is it dated within the **last 30 days** (prefer recent; exclude obvious evergreen content)?
   
   Discard results that fail any of these. Keep only results that pass all three.

4. **Deduplicate against existing knowledge**
   For each result that passed filtering:
   - Call `search_knowledge(query="[result title or key phrase]")`
   - If a very similar entry already exists in the knowledge base, skip this result.
   - If it's genuinely new, keep it.

5. **Store — cap at 3 per run**
   - Store at most 3 new items in this run (prioritise the most recent and most impactful).
   - For each item to store, call `ingest_knowledge_text` with:
     - `title`: a short descriptive title, e.g. "CUGA v3.1 — dark mode support"
     - `text`: 2–4 sentence summary of the update, written in plain language. Include the source URL at the end.
   - Do NOT store the raw scraped text — summarise it.

6. **Report back**
   After storing, summarise what was done:
   ```
   🔍 Scout complete — [topic]

   Searched [N] results, stored [M] new items:
   • [Title 1]
   • [Title 2]
   • [Title 3]

   These will be included in the next bulletin. Run /bulletin (or trigger the bulletin skill) to draft one now.
   ```
   If nothing new was found: "No new relevant updates found for '[topic]' this run. The knowledge base is already up to date."

## Important constraints

- Never store more than 3 items per run — quality over quantity
- Summaries only — do not dump raw HTML or full article text
- If `web_search` is unavailable (no API key), tell the user: "Web search requires a TAVILY_API_KEY environment variable. Add it to your .env and restart."
- Do not store opinion pieces, social media posts, or content that is not directly about the product
