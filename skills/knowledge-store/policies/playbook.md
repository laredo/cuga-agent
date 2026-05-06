---
type: playbook
name: knowledge-store-playbook
triggers:
  - type: keyword
    value: ["store this", "remember this", "save this", "add this", "keep this"]
    operator: or
priority: 1
---

## Knowledge Storage Workflow

Follow these steps whenever the user wants to store something:

1. **Identify the content type**
   - If the message contains a URL (http:// or https://): use `ingest_knowledge_url`
   - If the message contains only text: write the text to a temporary `.md` file, then use `ingest_knowledge` with that file path

2. **Extract context from the user's message**
   - Note any category or tag the user mentioned (e.g. "v3.4 feature", "architecture", "competitor analysis")
   - Use this as the filename prefix when storing (e.g. `v34-feature-async-exports.md`)

3. **Ingest with scope="agent"**
   - Always use `scope="agent"` so content persists across sessions
   - For URLs: call `ingest_knowledge_url(url=<url>, scope="agent")`
   - For text: write to `/tmp/cuga-knowledge-<slug>.md`, call `ingest_knowledge(file_path=<path>, scope="agent")`

4. **Confirm storage**
   - Reply with a short confirmation: "Stored: [brief title or description] — [category tag if provided]"
   - If ingestion returns a task_id, you may add: "Processing in background, will be searchable shortly."
   - Keep the confirmation to one line — do not repeat the full content back

5. **Do not ask clarifying questions** unless the message is completely ambiguous (no URL, no text content at all).

## Scope reminder

All knowledge is stored under `scope="agent"` — it is shared across all conversations with this agent instance and available to the bulletin skill.
