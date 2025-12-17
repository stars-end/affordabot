"""
Generate a context prompt for a Jules agent based on a Beads issue.
Usage: python scripts/generate_jules_context.py --issue <ISSUE_ID> --prompt <OPTIONAL_EXTRA_PROMPT>
"""

import argparse
import json
import os
import subprocess
from pathlib import Path

CONTEXT_DIR = Path("scripts/prompts/contexts")

def get_issue(issue_id):
    """Fetch issue details from Beads CLI."""
    try:
        result = subprocess.run(
            ["bd", "show", issue_id, "--json"],
            capture_output=True,
            text=True,
            check=True
        )
        data = json.loads(result.stdout)
        if isinstance(data, list):
            return data[0] if data else {}
        return data
    except subprocess.CalledProcessError as e:
        print(f"Error fetching issue {issue_id}: {e.stderr}")
        exit(1)

def generate_prompt(issue, extra_prompt):
    """Construct the prompt content."""
    prompt = f"# Task: {issue['title']} ({issue['id']})\n\n"
    prompt += f"## Description\n{issue['description']}\n\n"
    
    if extra_prompt:
        prompt += f"## Additional Instructions\n{extra_prompt}\n\n"
        
    prompt += "## Context\n"
    prompt += "You are a Jules agent working on the Affordabot codebase.\n"
    prompt += "Please implement the requested changes and verify them locally.\n"
    
    return prompt

def main():
    parser = argparse.ArgumentParser(description="Generate Jules Context")
    parser.add_argument("--issue", required=True, help="Beads Issue ID (e.g., affordabot-123)")
    parser.add_argument("--prompt", help="Optional extra prompt instructions")
    args = parser.parse_args()

    # Ensure output directory exists
    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Get Issue
    issue = get_issue(args.issue)
    
    # 2. Generate Content
    content = generate_prompt(issue, args.prompt)
    
    # 3. Write to File
    filename = CONTEXT_DIR / f"{args.issue}_context.md"
    with open(filename, "w") as f:
        f.write(content)
        
    print(f"Generated context: {filename}")
    print(filename) # Output filename for the skill to capture

if __name__ == "__main__":
    main()
