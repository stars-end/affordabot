# Slack-Based Agent Coordination POC

## Overview

This document captures the proof-of-concept for using Slack as the primary coordination layer between AI coding agents across different machines.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Slack Workspace                               │
│                                                                      │
│  ┌─────────────────────┐  ┌─────────────────────┐                    │
│  │ #affordabot-agents  │  │     #social         │                    │
│  │ (dedicated channel) │  │  (general/testing)  │                    │
│  └──────────┬──────────┘  └──────────┬──────────┘                    │
└─────────────┼────────────────────────┼───────────────────────────────┘
              │                        │
       ┌──────┴──────┐          ┌──────┴──────┐
       │             │          │             │
┌──────▼──────┐ ┌────▼────┐ ┌───▼───┐ ┌───────▼───────┐
│ Antigravity │ │ Codex   │ │ Human │ │ Claude Code   │
│ (homedesktop)│ │  CLI   │ │       │ │  (macmini)    │
└─────────────┘ └─────────┘ └───────┘ └───────────────┘
```

## Channel Structure Proposal

| Channel | Purpose |
|:--------|:--------|
| `#affordabot-agents` | Dedicated agent coordination for affordabot project |
| `#agent-alerts` | High-priority notifications (CI failures, urgent tasks) |
| `#agent-logs` | Verbose logging, status updates (optional) |

## Polling Protocol

### Session Start
```
1. Agent wakes up
2. Calls: conversations.history(channel, limit=10)
3. Filters for messages with @mention or task assignments
4. Processes any pending tasks
```

### During Work
```
1. Every N tool calls (or time interval)
2. Poll channel for urgent messages
3. Reply to threads with progress updates
```

### Session End
```
1. Post summary to channel
2. Final poll for follow-ups
3. Graceful exit
```

## Message Format Standards

### Task Assignment
```
📋 *Task Assignment: {beads-id}*
*Assigned to:* @{agent-name}
*Priority:* P{0-4}
---
*Task:* {description}
*Commit with:* Feature-Key: {beads-id}
```

### Task Acknowledgment
```
🤖 *{agent-name} acknowledging task*
✅ Task received: {beads-id}
⏳ Starting work now...
```

### Task Completion
```
✅ *Task Complete: {beads-id}*
PR: #{pr-number}
Status: Merged
```

## Verification Results

| Test | Result |
|:-----|:-------|
| Post from homedesktop → Slack | ✅ |
| Read from macmini ← Slack | ✅ |
| Reply in thread | ✅ |
| Cross-machine coordination | ✅ |

## Benefits Over Agent Mail

- ✅ Human-in-the-loop native
- ✅ No SSH tunnels required
- ✅ Mobile notifications
- ✅ Battle-tested infrastructure
- ❌ No file reservations (git handles via branches)
