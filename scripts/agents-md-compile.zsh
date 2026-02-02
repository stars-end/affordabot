#!/bin/zsh
set -euo pipefail

# Affordabot AGENTS.md Compiler (V5)
# Combines:
# 1. Universal Baseline (unmodified)
# 2. Repo Addendum (custom rules)
# 3. Context Skills Index (auto-generated)

OUTPUT="AGENTS.md"
FRAGMENTS_DIR="fragments"
SKILLS_DIR=".claude/skills"

echo "🔨 Compiling $OUTPUT..."

{
  # 1. Header
  echo "<!-- AUTO-GENERATED - DO NOT EDIT DIRECTLY -->"
  echo "<!-- Generated at: $(date -u +'%Y-%m-%dT%H:%M:%SZ') -->"
  echo ""

  # 2. Universal Baseline
  if [[ -f "$FRAGMENTS_DIR/universal-baseline.md" ]]; then
    cat "$FRAGMENTS_DIR/universal-baseline.md"
  else
    echo "❌ ERROR: $FRAGMENTS_DIR/universal-baseline.md missing!" >&2
    exit 1
  fi

  echo ""
  echo "---"
  echo ""

  # 3. Repo Addendum
  if [[ -f "$FRAGMENTS_DIR/repo-addendum.md" ]]; then
    cat "$FRAGMENTS_DIR/repo-addendum.md"
  else
    echo "⚠️  WARNING: $FRAGMENTS_DIR/repo-addendum.md missing" >&2
  fi

  echo ""
  echo "---"
  echo ""

  # 4. Context Skills Index
  echo "## Context Skills Index"
  echo ""
  echo "| Skill | Purpose |"
  echo "|-------|---------|"
  
  # Find all SKILL.md files in .claude/skills
  for skill_file in $(find "$SKILLS_DIR" -name "SKILL.md" | sort); do
    # Extract name and description from YAML frontmatter using python for safety
    python3 - <<EOF
import yaml
import sys
try:
    with open("$skill_file", "r") as f:
        content = f.read()
        if content.startswith("---"):
            _, frontmatter, _ = content.split("---", 2)
            data = yaml.safe_load(frontmatter)
            name = data.get("name", "Unknown")
            desc = data.get("description", "No description provided.")
            # Clean up desc (remove newlines, etc)
            desc = desc.replace("\n", " ").strip()
            print(f"| [\`{name}\`]({skill_file}) | {desc} |")
except Exception as e:
    pass # Skip invalid files
EOF
  done

} > "$OUTPUT"

echo "✅ $OUTPUT ready ($(wc -l < "$OUTPUT") lines)"
