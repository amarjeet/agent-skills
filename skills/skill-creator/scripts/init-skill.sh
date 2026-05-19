#!/usr/bin/env bash
# Initialize a new skill directory with a SKILL.md template.
#
# Paths are resolved from this script's location, not the caller's CWD.
# New skills are always created under the canonical skills root (parent of
# skill-creator/), never in .cursor/skills or .claude/skills symlinks.
#
# Usage:
#   init-skill.sh <skill-name> [--resources scripts,references,assets] [--profile minimal|full]
#
# Examples:
#   skills/skill-creator/scripts/init-skill.sh my-skill
#   skills/skill-creator/scripts/init-skill.sh api-helper --resources scripts,references
#   skills/skill-creator/scripts/init-skill.sh smoke-test --profile minimal

set -euo pipefail

SCRIPT_PATH="${BASH_SOURCE[0]}"
# shellcheck source=lib/paths.sh
source "$(cd "$(dirname "$SCRIPT_PATH")" && pwd)/lib/paths.sh"

die() { echo "[ERROR] $*" >&2; exit 1; }

skill_creator_resolve_paths "$SCRIPT_PATH"
OUTPUT_DIR="$(skill_creator_resolve_output_dir "")"

# --- Parse arguments ---
[[ $# -lt 1 ]] && die "Usage: init-skill.sh <skill-name> [--resources scripts,references,assets] [--profile minimal|full]"

RAW_NAME="$1"
RESOURCES=""
PROFILE="full"

shift
while [[ $# -gt 0 ]]; do
  case "$1" in
    --resources) RESOURCES="$2"; shift 2 ;;
    --profile)
      PROFILE="$2"
      [[ "$PROFILE" == "minimal" || "$PROFILE" == "full" ]] || die "--profile must be 'minimal' or 'full'"
      shift 2
      ;;
    *) die "Unknown option: $1" ;;
  esac
done

# --- Normalize name ---
NAME=$(echo "$RAW_NAME" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g; s/--*/-/g; s/^-//; s/-$//')
[[ -z "$NAME" ]] && die "Skill name must include at least one letter or digit."
[[ ${#NAME} -lt 2 ]] && die "Skill name too short (${#NAME} char, min 2)."
[[ ${#NAME} -gt 64 ]] && die "Skill name too long (${#NAME} chars, max 64)."
if ! echo "$NAME" | grep -qE '^[a-z0-9][a-z0-9-]*[a-z0-9]$'; then
  die "Name '$NAME' must use kebab-case and start/end with a letter or digit."
fi
[[ "$NAME" != "$RAW_NAME" ]] && echo "Note: Normalized skill name to '$NAME'."

SKILL_DIR="$OUTPUT_DIR/$NAME"
[[ -d "$SKILL_DIR" ]] && die "Directory already exists: $SKILL_DIR"

# --- Create skill directory ---
mkdir -p "$SKILL_DIR"
echo "[OK] Created $SKILL_DIR"
echo "[OK] Skills root: $SKILLS_ROOT"
echo "[OK] Repo root:   $REPO_ROOT"

# --- Create SKILL.md ---
TITLE=$(echo "$NAME" | sed 's/-/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) substr($i,2)}1')

if [[ "$PROFILE" == "minimal" ]]; then
  cat > "$SKILL_DIR/SKILL.md" << TEMPLATE
---
name: $NAME
description: "TODO - One sentence on what this skill does. Triggers: phrase one, phrase two."
---

# $TITLE

## Overview

TODO: One sentence.

## Instructions

TODO: Numbered imperative steps. Only encode what the model does not already know.
TEMPLATE
else
  cat > "$SKILL_DIR/SKILL.md" << TEMPLATE
---
name: $NAME
description: "TODO - Describe what this skill does and when to use it. Triggers: phrase one, phrase two, phrase three."
---

# $TITLE

## Overview

TODO: 1-2 sentences explaining what this skill enables.

## Instructions

TODO: Write concise, imperative instructions. Only include what the model doesn't already know.

### Workflow

1. TODO: First step
2. TODO: Second step

### Edge Cases

- If TODO condition, then TODO action.

## Example

User: "TODO trigger phrase"

Response: TODO expected behavior.

## Testing

Run validation from anywhere:

\`\`\`bash
skills/skill-creator/scripts/validate-skill.sh $NAME
\`\`\`
TEMPLATE
fi

echo "[OK] Created SKILL.md (profile: $PROFILE)"

# --- Create resource directories ---
if [[ -n "$RESOURCES" ]]; then
  IFS=',' read -ra DIRS <<< "$RESOURCES"
  for DIR in "${DIRS[@]}"; do
    DIR=$(echo "$DIR" | tr -d ' ')
    case "$DIR" in
      scripts|references|assets)
        mkdir -p "$SKILL_DIR/$DIR"
        echo "[OK] Created $DIR/"
        ;;
      *) echo "[WARN] Skipping unknown resource type: $DIR" ;;
    esac
  done
fi

echo ""
echo "[OK] Skill '$NAME' initialized at $SKILL_DIR"
echo ""
echo "Next steps:"
echo "  1. Edit $SKILL_DIR/SKILL.md — replace all TODO placeholders"
echo "  2. Add resources to scripts/, references/, assets/ as needed"
echo "  3. Validate:"
echo "     skills/skill-creator/scripts/validate-skill.sh $NAME"
