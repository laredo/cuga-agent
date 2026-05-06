---
type: playbook
name: bulletin-playbook
triggers:
  - type: keyword
    value: ["bulletin", "weekly update", "customer update", "what did we ship"]
    operator: or
priority: 1
---

## Bulletin Drafting Workflow

Follow these steps to compile and deliver the product bulletin:

1. **Query the knowledge base**
   - Call `search_knowledge(query="product features updates shipped release", scope="agent")`
   - Also call `search_knowledge(query="new capabilities improvements announcements", scope="agent")`
   - Deduplicate results by source URL or filename if overlapping

2. **Synthesize into bulletin format**
   Draft the bulletin using this exact structure:

   ```
   📬 CUGA Product Update — [current week, e.g. "Week of May 6"]

   Here's what's new:

   • [Feature/update 1 — customer-framed, benefit-led, 1 sentence]
   • [Feature/update 2 — customer-framed, benefit-led, 1 sentence]
   • [Feature/update 3 — customer-framed, benefit-led, 1 sentence]

   What's next: [One forward-looking sentence about upcoming work]

   — The CUGA Team
   ```

   Rules for bullet points:
   - Lead with the customer benefit, not the technical mechanism
   - Keep each to one sentence
   - Skip items that are internal-only or not customer-relevant
   - Maximum 4 bullets — pick the most impactful

3. **Present for approval**
   - Show the full draft to the user
   - Ask: "Ready to post to #product-updates? Reply **approve** to post, **discard** to cancel, or tell me what to change."
   - Do NOT post anywhere until the user explicitly approves

4. **On approval**
   - Confirm: "Posted to #product-updates ✓"
   - If running via CLI/test mode, print the final bulletin and confirm it would be posted

5. **On rejection or edit request**
   - If the user says discard/cancel/skip: confirm cancellation, do nothing
   - If the user requests changes: apply them and re-present the draft (return to step 3)

## Important constraints

- Never post externally without explicit user approval
- If the knowledge base returns no results: respond "No stored updates found for this period. Forward some product updates first with /store."
- The tone should be warm and concise — written for customers, not engineers
