#!/usr/bin/env bash
# Validate a skill directory for structural issues.
#
# Paths are resolved from this script's location, not the caller's CWD.
# Accepts a skill name (looked up under the skills root) or a path.
#
# Usage:
#   validate-skill.sh <skill-name-or-path> [--strict]
#
# Examples:
#   skills/skill-creator/scripts/validate-skill.sh my-skill
#   skills/skill-creator/scripts/validate-skill.sh skills/my-skill --strict

set -euo pipefail

SCRIPT_PATH="${BASH_SOURCE[0]}"
# shellcheck source=lib/paths.sh
source "$(cd "$(dirname "$SCRIPT_PATH")" && pwd)/lib/paths.sh"

die() { echo "FAIL: $*"; exit 1; }
warn() { echo "WARN: $*"; }

STRICT=0
SKILL_ARG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --strict) STRICT=1; shift ;;
    -*) die "Unknown option: $1" ;;
    *)
      [[ -z "$SKILL_ARG" ]] || die "Usage: validate-skill.sh <skill-name-or-path> [--strict]"
      SKILL_ARG="$1"
      shift
      ;;
  esac
done

[[ -n "$SKILL_ARG" ]] || die "Usage: validate-skill.sh <skill-name-or-path> [--strict]"

skill_creator_resolve_paths "$SCRIPT_PATH"
SKILL_DIR="$(skill_creator_resolve_skill_dir "$SKILL_ARG")"
SKILL_MD="$SKILL_DIR/SKILL.md"

[[ -f "$SKILL_MD" ]] || die "SKILL.md not found in $SKILL_DIR"

CONTENT=$(<"$SKILL_MD")

# Check frontmatter delimiters
if [[ "$CONTENT" != ---* ]]; then
  FIRST3=$(echo "$CONTENT" | head -c 12)
  if echo "$FIRST3" | LC_ALL=C grep -qP '[\x{2010}-\x{2015}\x{FE58}\x{FE63}\x{FF0D}]' 2>/dev/null; then
    die "SKILL.md starts with typographic dashes (em-dash/en-dash) instead of ASCII hyphens. Replace the opening and closing frontmatter delimiters with plain --- (three ASCII hyphens, U+002D)"
  fi
  die "SKILL.md must start with --- (YAML frontmatter)"
fi

FRONTMATTER=$(echo "$CONTENT" | awk '/^---$/{n++; next} n==1')
[[ -n "$FRONTMATTER" ]] || die "Empty or malformed frontmatter"

BODY=$(echo "$CONTENT" | awk '/^---$/{n++; next} n>=2')
BODY_TRIMMED=$(echo "$BODY" | sed '/^[[:space:]]*$/d')
[[ -n "$BODY_TRIMMED" ]] || die "SKILL.md body is empty (no content after frontmatter)"

NAME=$(echo "$FRONTMATTER" | grep -m1 '^name:' | sed 's/^name:[[:space:]]*//')
[[ -n "$NAME" ]] || die "Missing 'name' in frontmatter"

[[ ${#NAME} -ge 2 ]] || die "Name '$NAME' is too short (min 2 characters)"
[[ ${#NAME} -le 64 ]] || die "Name '$NAME' is too long (${#NAME} chars, max 64)"
if ! echo "$NAME" | grep -qE '^[a-z0-9][a-z0-9-]*[a-z0-9]$'; then
  die "Name '$NAME' must use only lowercase letters (a-z), digits (0-9), and hyphens (-), and must start and end with a letter or digit (e.g. 'my-skill')"
fi

DIR_NAME=$(basename "$SKILL_DIR")
[[ "$NAME" == "$DIR_NAME" ]] || die "Frontmatter name '$NAME' does not match directory name '$DIR_NAME'"

DESC_LINE=$(echo "$FRONTMATTER" | grep -m1 '^description:')
[[ -n "$DESC_LINE" ]] || die "Missing 'description' in frontmatter"
DESCRIPTION=$(echo "$DESC_LINE" | sed 's/^description:[[:space:]]*//')

if [[ "$DESCRIPTION" =~ ^\"(.*)\"$ ]] || [[ "$DESCRIPTION" =~ ^\'(.*)\'$ ]]; then
  DESCRIPTION="${BASH_REMATCH[1]}"
fi

[[ -n "$DESCRIPTION" ]] || die "Missing 'description' in frontmatter"

RAW_VALUE=$(echo "$DESC_LINE" | sed 's/^description:[[:space:]]*//')
if echo "$RAW_VALUE" | grep -q ': ' && [[ ! "$RAW_VALUE" =~ ^\" ]] && [[ ! "$RAW_VALUE" =~ ^\' ]]; then
  die "Description contains ': ' (colon-space) which breaks YAML parsing. Wrap the value in quotes, e.g.: description: \"$RAW_VALUE\""
fi

if echo "$DESCRIPTION" | grep -qi 'TODO'; then
  die "Description is still a TODO placeholder"
fi

DESC_LEN=${#DESCRIPTION}
[[ "$DESC_LEN" -le 1024 ]] || die "Description is too long ($DESC_LEN chars, max 1024)"

if ! echo "$DESCRIPTION" | grep -qi 'trigger'; then
  if [[ "$STRICT" -eq 1 ]]; then
    die "Description should include trigger phrases (contain 'trigger' or 'Triggers:')"
  else
    warn "Description has no obvious trigger phrases (consider adding 'Triggers: ...')"
  fi
fi

if ! echo "$BODY" | grep -qE '^##[[:space:]]+(Overview|Instructions)'; then
  if [[ "$STRICT" -eq 1 ]]; then
    die "SKILL.md body must include ## Overview and/or ## Instructions sections"
  else
    warn "SKILL.md body is missing ## Overview or ## Instructions headings"
  fi
fi

if echo "$BODY" | grep -qE '^[[:space:]]*TODO[: -]'; then
  if [[ "$STRICT" -eq 1 ]]; then
    die "SKILL.md body still contains TODO placeholders"
  else
    warn "SKILL.md body still contains TODO placeholders"
  fi
fi

if [[ -d "$SKILL_DIR/scripts" ]]; then
  shopt -s nullglob
  scripts=("$SKILL_DIR/scripts"/*)
  shopt -u nullglob
  if [[ ${#scripts[@]} -eq 0 ]]; then
    warn "scripts/ directory exists but is empty"
  fi
fi

LINE_COUNT=$(echo "$CONTENT" | wc -l | tr -d ' ')
if [[ "$LINE_COUNT" -gt 500 ]]; then
  warn "SKILL.md is $LINE_COUNT lines (recommended max 500). Move content to references/."
fi

echo "OK: Skill '$NAME' is valid ($LINE_COUNT lines)"
echo "    Path: $SKILL_DIR"
echo "    Skills root: $SKILLS_ROOT"
