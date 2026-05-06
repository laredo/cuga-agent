---
name: file-reader
description: "Read and summarize files from the local filesystem"
version: "0.1.0"
author: "cuga-personal"
platforms: [cli]
requires_tools: [filesystem]
commands: ["/read", "/summarize"]
triggers:
  - type: keyword
    value: ["read file", "summarize file", "open file", "show file"]
    operator: or
enterprise:
  category: utility
  approval_required: false
  data_classification: internal
---

# File Reader Skill

Reads and summarizes files from a specified workspace directory.

Uses CUGA's built-in filesystem MCP server (configured in `mcp_servers.yaml`).

## Usage

- `/read /path/to/file.txt`
- "summarize file /path/to/report.pdf"
- "read file config.yaml and explain it"

## Notes

Only reads files within the configured workspace directory (enforced by the filesystem MCP).
