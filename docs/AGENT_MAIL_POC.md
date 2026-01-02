# Agent Mail POC Documentation

## Overview

This document records the successful Proof of Concept (POC) for **Agent Mail** - a mail-like coordination layer for coding agents that enables cross-machine agent coordination.

## POC Participants

| Agent | Codename | Machine | IDE |
|:------|:---------|:--------|:----|
| Coordinator | SunnyMoose | homedesktop-wsl | Antigravity |
| Worker | RedMoose | macmini | Claude Code |

## Architecture

```
┌─────────────────────────────┐     ┌─────────────────────────────┐
│     homedesktop-wsl         │     │         macmini             │
│                             │     │                             │
│  🤖 SunnyMoose (Antigravity) │     │  🤖 RedMoose (Claude Code)   │
└──────────────┬──────────────┘     └──────────────┬──────────────┘
               │                                   │
               │ localhost:8765                    │ localhost:8765
               │                                   │ (via SSH tunnel)
               │  ┌─────────────────────────────┐  │
               └──┤   Agent Mail Server        ├──┘
                  │   (on homedesktop-wsl)     │
                  └─────────────────────────────┘
```

## Verified Features

- ✅ **Cross-machine messaging** via SSH tunnel
- ✅ **Bidirectional communication** (both directions work)
- ✅ **File reservations** with conflict detection
- ✅ **Task assignment** via Agent Mail threads
- ✅ **Beads integration** (thread_id = affordabot-x77z)

## Setup Requirements

1. **Agent Mail Server** running on homedesktop-wsl (port 8765)
2. **SSH Tunnel**: `ssh -R 8765:localhost:8765 macmini`
3. **Shared project_key**: All agents use server's local path

## POC Completed

- **Date**: 2026-01-02
- **Issue**: affordabot-x77z
- **Outcome**: Successfully demonstrated Agent Mail coordination
