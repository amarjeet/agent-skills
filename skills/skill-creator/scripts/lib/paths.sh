#!/usr/bin/env bash
# Shared path resolution for skill-creator scripts.
# Source from other scripts in this directory — do not execute directly.

_skill_creator_die() {
  echo "[ERROR] $*" >&2
  exit 1
}

# Resolve canonical directories from the calling script's location.
# CWD is intentionally ignored for output paths.
skill_creator_resolve_paths() {
  local caller_source="${1:?caller source path required}"

  SKILL_CREATOR_SCRIPTS_DIR="$(cd "$(dirname "$caller_source")" && pwd)"
  SKILL_CREATOR_ROOT="$(cd "$SKILL_CREATOR_SCRIPTS_DIR/.." && pwd)"
  SKILLS_ROOT="$(cd "$SKILL_CREATOR_ROOT/.." && pwd)"
  REPO_ROOT="$(cd "$SKILLS_ROOT/.." && pwd)"
}

# Resolve the directory where new skills must be created.
# Only the canonical skills root (parent of skill-creator/) is allowed.
skill_creator_resolve_output_dir() {
  local requested="${1:-}"

  if [[ -z "$requested" ]]; then
    echo "$SKILLS_ROOT"
    return 0
  fi

  local resolved
  if [[ "$requested" = /* ]]; then
    resolved="$(cd "$requested" 2>/dev/null && pwd)" || _skill_creator_die "Output directory does not exist: $requested"
  else
    resolved="$(cd "$REPO_ROOT" && cd "$requested" 2>/dev/null && pwd)" || _skill_creator_die "Output directory not found relative to repo root ($REPO_ROOT): $requested"
  fi

  if [[ "$resolved" != "$SKILLS_ROOT" ]]; then
    _skill_creator_die "Refusing to write outside canonical skills root.
  Expected: $SKILLS_ROOT
  Got:      $resolved

  Skills must live next to skill-creator/, not in .cursor/skills or .claude/skills symlinks.
  Omit the output-directory argument to use the default, or pass: skills"
  fi

  echo "$resolved"
}

# Resolve a skill directory from a name or path.
# Names are looked up under SKILLS_ROOT; paths must be absolute or repo-relative.
skill_creator_resolve_skill_dir() {
  local arg="${1:?skill name or path required}"

  if [[ "$arg" = /* ]]; then
    cd "$arg" 2>/dev/null && pwd && return 0
    _skill_creator_die "Skill directory does not exist: $arg"
  fi

  if [[ "$arg" == */* ]]; then
    local resolved
    resolved="$(cd "$REPO_ROOT" && cd "$arg" 2>/dev/null && pwd)" || _skill_creator_die "Skill path not found relative to repo root ($REPO_ROOT): $arg"
    echo "$resolved"
    return 0
  fi

  local skill_dir="$SKILLS_ROOT/$arg"
  [[ -d "$skill_dir" ]] || _skill_creator_die "Skill not found: $skill_dir (lookup by name under skills root)"
  echo "$skill_dir"
}
