---
name: mock-timesheet
description: "Demo skill: fill a mock weekly timesheet based on calendar events and Jira tickets"
version: "0.1.0"
author: "cuga-personal"
platforms: [slack, cli]
requires_tools: [mock_calendar, mock_jira, mock_timesheet_api]
commands: ["/timesheet"]
triggers:
  - type: keyword
    value: ["timesheet", "time sheet", "fill time", "log hours", "submit hours"]
    operator: or
  - type: natural_language
    value: ["fill my weekly hours", "submit timesheet", "log my time"]
schedule_hint: "0 16 * * 5"
enterprise:
  category: hr
  approval_required: false
  data_classification: internal
---

# Mock Timesheet Skill

Demonstrates automated timesheet filling using mock data.

In production this skill would connect to:
- Your calendar API (Google Calendar, Outlook) to fetch meeting/event data
- Your issue tracker (Jira, Linear, etc.) to fetch tickets worked on
- Your timesheet system API to submit hours

## What this demo does

Uses a mock calendar and mock Jira tools that return hard-coded sample data.
Calls a mock timesheet API endpoint to demonstrate the submission flow.

## Prerequisites

No real credentials needed for the demo — all tools return mock data.
