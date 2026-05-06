# Timesheet Domain Knowledge

## Project Code Mapping

In a real deployment, project codes are configured per organization. For this demo:
- "PROJ-001" → Development work (Jira tickets tagged as FEAT or BUG)
- "PROJ-002" → Meetings & Collaboration (calendar events with multiple attendees)
- "PROJ-003" → Admin & Training (1:1 meetings, onboarding, HR tasks)

## Timesheet Rules

- Standard working week: Monday–Friday, 8 hours/day (40h/week)
- Minimum entry granularity: 0.5 hours
- Entries must sum to total hours worked (no over/under booking without explanation)
- Public holidays: check the `get_company_holidays` tool before filling

## Mock Data Notes

This skill uses mock tools that return sample data:
- `get_calendar_events`: returns a hardcoded set of meetings for the demo week
- `get_jira_tickets`: returns sample PROJ-101, PROJ-102, PROJ-103 tickets
- `submit_timesheet`: logs the submission to stdout (no real API call)
