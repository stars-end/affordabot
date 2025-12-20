# Visual Audit Trace Guide
**ID:** affordabot-29f.4

## Overview
The Visual Audit system (UISmokeAgent) captures step-by-step evidence of the application's UI state during verification runs. This prevents "black screen" false positives and ensures data integrity.

## Directory Structure
Traces are saved in `.traces/evidence/` (or the configured evidence dir):
- `step_id.png`: Final screenshot for the step.
- `step_id.html`: Full DOM source for debugging.
- `debug_step_id_iteration.png/html`: Intermediate state captures during agent multi-turn interaction.

## Interpreting Results
- **Pass:** The agent successfully reached the target state AND strict visual verification confirmed all required text markers were visible.
- **Fail:** 
    - **Timeout:** Page didn't load or was blank.
    - **Verification Error:** LLM claimed success, but secondary OCR-check failed to find required text.
    - **Safety/Block:** Vision model triggered a safety flag (handled by automatic backoff to fallback model).

## Troubleshooting
If you see blank screenshots in `.traces`:
1. Check the `.html` file to see if content is rendered in the DOM.
2. If DOM is full but screenshot is black, increase the `asyncio.sleep` buffer in `capture_visual_proof.py`.
