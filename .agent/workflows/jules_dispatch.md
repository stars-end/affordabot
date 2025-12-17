---
description: Dispatches work to Jules agents via the CLI. Automatically generates context-rich prompts from Beads issues and spawns async sessions. Use when user says "send to jules", "assign to jules", "dispatch task", or "run in cloud".
---

# Jules Dispatch

Orchestrates asynchronous work by dispatching tasks to Jules agents.

## Usage

```bash
/jules_dispatch [issue_id] [optional_prompt]
```

## Workflow

1.  **Context Generation**:
    -   Reads the Beads issue (`issue_id`).
    -   Scans the codebase for relevant files based on the issue description.
    -   Generates a comprehensive prompt file in `scripts/prompts/contexts/`.

2.  **Dispatch**:
    -   Calls `jules session start` with the generated prompt.
    -   Records the Session ID in `.jules/sessions.jsonl`.

3.  **Notification**:
    -   Updates the Beads issue with the Session ID and status "Dispatched".

## Implementation

// turbo-all

1.  **Generate Context**
    ```bash
    python scripts/generate_jules_context.py --issue $1 --prompt "$2"
    ```

2.  **Start Session**
    ```bash
    # Capture the output to parse Session ID
    jules session start --prompt-file "scripts/prompts/contexts/$1_context.md" > .jules/last_session.log 2>&1
    cat .jules/last_session.log
    ```

3.  **Log Session**
    ```bash
    python scripts/log_jules_session.py --issue $1 --log-file .jules/last_session.log
    ```
