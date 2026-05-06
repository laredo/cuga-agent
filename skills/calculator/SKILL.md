---
name: calculator
description: "Perform arithmetic calculations using a safe expression evaluator"
version: "0.1.0"
author: "cuga-personal"
platforms: [slack, cli]
requires_tools: []
commands: ["/calc", "/calculate"]
triggers:
  - type: keyword
    value: ["calculate", "compute", "what is", "how much"]
    operator: or
enterprise:
  category: utility
  approval_required: false
  data_classification: public
---

# Calculator Skill

A simple arithmetic skill — useful as a reference implementation for skill development.

Demonstrates:
- A skill with no external tool dependencies
- Pure in-process computation
- Keyword-based dispatch

## Usage

- `/calc 2 + 2`
- "calculate 15% of 240"
- "what is 1234 * 5678"
