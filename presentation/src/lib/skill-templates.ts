// Hand-rolled starter templates the presenter can pull up alongside the
// real sidecar skills. Kept short so they fit on a single screen and read
// well when the section highlights animate in.

export type TemplateSkill = {
  name: string;
  source: string;
  blurb: string;
};

export const templates: TemplateSkill[] = [
  {
    name: 'audit inbound',
    blurb: 'on_start · archive events before they run.',
    source: `---
name: audit-inbound
description: >
  Archive every inbound GitHub issue to disk before the agent runs,
  so we have a trail of what arrived even if the agent fails.
triggers:
  - type: github
    repo: your-org/your-repo
    resource: issues
    event: opened
hooks:
  on_start:
    - type: write_file
      path: "~/audit/{{ event.issue.number }}.json"
      content: "{{ event | tojson }}"
  on_answer:
    - type: notify
      title: "Processed #{{ event.issue.number }}"
      body:  "{{ result | truncate(120) }}"
---
One-line summary of this issue for the audit log:

  #{{ event.issue.number }}  {{ event.issue.title }}
  {{ event.issue.body }}

Just the summary, no preamble.
`,
  },

  {
    name: 'heartbeat',
    blurb: 'on_error · alert when the agent is down.',
    source: `---
name: heartbeat
description: >
  Ping the agent every 5 minutes. On a healthy reply write a timestamp;
  on any error notify the desktop and post to #ops so on-call knows.
triggers:
  - type: cron
    schedule: "*/5 * * * *"
hooks:
  on_answer:
    - type: write_file
      path: "~/.heartbeat"
      content: "{{ event.date }}"
  on_error:
    - type: notify
      title: "⚠ Agent unhealthy"
      body:  "{{ exception_type }}: {{ error | truncate(140) }}"
    - type: slack_post
      channel: "#ops"
      text:    "Heartbeat failed at {{ event.date }}: {{ error }}"
---
Reply with just the word "ok". Nothing else.
`,
  },

  {
    name: 'track skips',
    blurb: 'on_skip · keep every skipped decision.',
    source: `---
name: triage-with-audit
description: >
  Classify each new issue as urgent or not. Notify only on urgent ones,
  and keep a markdown record of every non-urgent decision so nothing
  is silently dropped.
triggers:
  - type: github
    repo: your-org/your-repo
    resource: issues
    event: opened
hooks:
  on_answer:
    - type: notify
      when: "{{ result_json.urgent }}"
      title: "Urgent: #{{ event.issue.number }}"
      body:  "{{ result_json.summary }}"
  on_skip:
    - type: write_file
      path: "~/skipped/{{ event.issue.number }}-{{ skipped.type }}.md"
      content: |
        # Skipped {{ skipped.type }}
        Issue #{{ event.issue.number }}: {{ event.issue.title }}
        Condition: {{ skipped.when_expr }} → {{ skipped.when_rendered }}
---
Decide whether this issue is urgent:

  #{{ event.issue.number }}  {{ event.issue.title }}
  {{ event.issue.body }}

Reply as JSON: {"urgent": bool, "summary": "one line why"}.
`,
  },

  {
    name: 'watch a folder',
    blurb: 'Drop a file, get a summary.',
    source: `---
name: watch-folder
description: >
  Watch an inbox folder for new markdown files. Summarize each one and
  write the summary alongside the original, plus a desktop toast.
triggers:
  - type: file
    path: ~/Documents/Inbox
    glob: "*.md"
hooks:
  on_answer:
    - type: write_file
      path: "{{ event.file_path }}.summary.md"
      content: "{{ result }}"
    - type: notify
      title: "Summarized {{ event.file_name }}"
      body:  "{{ result | truncate(120) }}"
---
You're the desktop summarizer. Read the file below and return a short
bulleted summary, no preamble.

{{ event.file_contents }}
`,
  },

  {
    name: 'poll a repo',
    blurb: 'Flag issues you would care about.',
    source: `---
name: poll-github
description: >
  Poll a repo for newly opened issues. Ask the agent to judge relevance
  against a topic list; toast only the relevant ones.
triggers:
  - type: github
    repo: your-org/your-repo
    resource: issues
    event: opened
    interval: 30
hooks:
  on_answer:
    - type: notify
      when: "{{ result_json.relevant }}"
      title: "Heads up"
      body:  "#{{ event.issue.number }}: {{ result_json.one_liner }}"
---
New issue in {{ event.repo }}:

  #{{ event.issue.number }}  {{ event.issue.title }}
  {{ event.issue.body }}

Decide if it's relevant to me. I care about: {{ topics | join(', ') }}.

Reply with JSON: { "relevant": bool, "one_liner": "why" }.
`,
  },

  {
    name: 'cron brief',
    blurb: 'A daily summary at 09:00.',
    source: `---
name: daily-brief
description: >
  Produce a three-bullet morning brief every weekday at 9am —
  yesterday, today, and one decision to make — and drop it in Slack
  and the local briefs folder.
triggers:
  - type: cron
    schedule: "0 9 * * *"
hooks:
  on_answer:
    - type: write_file
      path: "~/briefs/{{ event.date }}.md"
      content: "{{ result }}"
    - type: slack_post
      channel: "#morning-brief"
      text: "{{ result | truncate(300) }}"
---
Produce a three-bullet brief for {{ event.date }}:
  1. What happened yesterday
  2. What I should focus on today
  3. One decision I should make by end of day

Keep it under 80 words total.
`,
  },
];
