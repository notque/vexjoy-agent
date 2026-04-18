---
name: perses-onboard
description: "First-time Perses setup: server, MCP, project."
version: 1.0.0
user-invocable: true
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
  - Write
  - Edit
  - Agent
routing:
  triggers:
    - perses onboard
    - perses setup
    - perses install
    - setup perses
    - configure perses
  category: meta-tooling
  complexity: Medium
---

# perses-onboard

First-time Perses onboarding: discover or deploy a Perses server, configure the Perses MCP server for Claude Code integration, create initial project and datasources, verify connectivity.

## Usage

```
/do onboard perses
/do setup perses for the first time
```

## What It Does

1. Discover or deploy a Perses server
2. Configure the Perses MCP server for Claude Code integration
3. Create initial project and datasources
4. Verify connectivity
