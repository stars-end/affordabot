#!/usr/bin/env python3
import json
import re
import sys

# Destructive patterns
DESTRUCTIVE_PATTERNS = [
    (r"git\s+checkout\s+--\s+", "git checkout -- discards changes."),
    (r"git\s+reset\s+--hard", "git reset --hard destroys changes."),
    (r"git\s+clean\s+-[a-z]*f", "git clean -f deletes files."),
    (r"rm\s+-[a-z]*r[a-z]*f", "rm -rf is destructive."),
]

def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
    
    command = input_data.get("tool_input", {}).get("command", "")
    if input_data.get("tool_name") != "Bash" or not command:
        sys.exit(0)

    for pattern, reason in DESTRUCTIVE_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"BLOCKED: {reason}\nCommand: {command}"
                }
            }))
            sys.exit(0)
    sys.exit(0)

if __name__ == "__main__":
    main()
