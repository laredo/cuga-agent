---
type: tool_approval
name: timesheet-submit-approval
triggers:
  - type: tool_name
    value: ["submit_timesheet"]
description: "Require explicit user confirmation before submitting a timesheet"
---

Before calling `submit_timesheet`, always:
1. Show the complete list of time entries to the user
2. Ask: "Shall I submit these entries? (yes/no)"
3. Only proceed if the user confirms with "yes" or equivalent
