---
type: playbook
name: timesheet-filling-playbook
triggers:
  - type: keyword
    value: ["timesheet", "time sheet", "fill time"]
    operator: or
priority: 1
---

## Timesheet Filling Workflow

Follow these steps when filling a timesheet:

1. **Determine the week** — confirm which week to fill (default: current week Mon-Fri)
2. **Fetch calendar events** — call `get_calendar_events` for the target week
3. **Fetch Jira tickets** — call `get_jira_tickets` to find tickets worked on
4. **Map to project codes** — match calendar events and Jira tickets to timesheet project codes
5. **Show summary** — present the planned timesheet entries to the user for confirmation
6. **Submit** — call `submit_timesheet` with the confirmed entries
7. **Confirm** — report the submission result

Always ask for confirmation before submitting. Never submit without user approval.
