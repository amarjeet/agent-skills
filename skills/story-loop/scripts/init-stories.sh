#!/usr/bin/env bash
# story-loop init: scaffold the story-loop methodology into a project.
#
# Paths are resolved from this script's location; run it from anywhere.
# Existing files are never overwritten (only --update refreshes stories/coverage.py).
#
# Usage:
#   init-stories.sh [--target DIR] [--name NAME] [--branch NAME] [--epic KEY]
#                   [--ticket jira|github|linear|none] [--design PATH]
#                   [--specs quint|manifest|none] [--local-only] [--no-claude] [--alias NAME]
#                   [--update] [--dry-run]
#
# Defaults: target = current directory; name = directory name; branch = the checked-out
# branch; ticket system guessed from the epic key; specs detected from specs/ (quint when
# *.qnt files exist, manifest when index.yaml exists, else none); build commands detected
# from pom.xml, package.json, go.mod, Cargo.toml or pyproject.toml; Claude Code agent files
# written unless --no-claude; `--alias story` adds a /story command that calls the skill.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ASSETS="$SKILL_ROOT/assets"

die() { echo "[ERROR] $*" >&2; exit 1; }
say() { echo "[OK] $*"; }
skip() { echo "[SKIP] $*"; }

TARGET="$PWD"; NAME=""; BRANCH=""; EPIC=""; TICKET=""; DESIGN="docs/DESIGN.md"; SPECS=""
LOCAL_ONLY=0; CLAUDE=1; ALIAS=""; UPDATE=0; DRY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --name) NAME="$2"; shift 2 ;;
    --branch) BRANCH="$2"; shift 2 ;;
    --epic) EPIC="$2"; shift 2 ;;
    --ticket) TICKET="$2"; shift 2 ;;
    --design) DESIGN="$2"; shift 2 ;;
    --specs) SPECS="$2"; shift 2 ;;
    --local-only) LOCAL_ONLY=1; shift ;;
    --no-claude) CLAUDE=0; shift ;;
    --alias) ALIAS="$2"; shift 2 ;;
    --update) UPDATE=1; shift ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "Unknown option: $1" ;;
  esac
done

[[ -d "$TARGET" ]] || die "Target directory does not exist: $TARGET"
TARGET="$(cd "$TARGET" && pwd)"
[[ -d "$ASSETS/stories" ]] || die "Assets not found under $ASSETS"
command -v python3 >/dev/null || die "python3 is required"
python3 -c 'import yaml' 2>/dev/null || echo "[WARN] PyYAML is not installed; stories/coverage.py needs it (pip install pyyaml)"

# --- Defaults derived from the target ---------------------------------------
[[ -n "$NAME" ]] || NAME="$(basename "$TARGET")"
if [[ -z "$BRANCH" ]]; then
  BRANCH="$(git -C "$TARGET" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  [[ -n "$BRANCH" && "$BRANCH" != "HEAD" ]] || BRANCH="develop"
fi
if [[ -z "$TICKET" ]]; then
  if [[ "$EPIC" =~ ^[A-Z][A-Z0-9]+-[0-9]+$ ]]; then TICKET="jira"
  elif [[ "$EPIC" =~ ^#?[0-9]+$ ]]; then TICKET="github"
  elif [[ -n "$EPIC" ]]; then TICKET="linear"
  else TICKET="none"; fi
fi
case "$TICKET" in jira|github|linear|none) ;; *) die "--ticket must be jira, github, linear or none" ;; esac
TICKET_PROJECT=""
[[ "$EPIC" =~ ^([A-Z][A-Z0-9]+)-[0-9]+$ ]] && TICKET_PROJECT="${BASH_REMATCH[1]}"
if [[ -z "$SPECS" ]]; then
  if ls "$TARGET"/specs/*.qnt >/dev/null 2>&1; then SPECS="quint"
  elif [[ -f "$TARGET/specs/index.yaml" ]]; then SPECS="manifest"
  else SPECS="none"; fi
fi
case "$SPECS" in quint|manifest|none) ;; *) die "--specs must be quint, manifest or none" ;; esac
SPECS_DIR="specs/"; SPECS_GATE=""
[[ "$SPECS" == "quint" ]] && SPECS_GATE="scripts/check-specs.sh"
BUILD_FULL="TODO: the full build and test command"; BUILD_SCOPED="TODO: the build and test command for the changed modules only"
if [[ -f "$TARGET/pom.xml" ]]; then BUILD_FULL="mvn -B verify"; BUILD_SCOPED="mvn -B -pl {modules} -amd verify"
elif [[ -f "$TARGET/package.json" ]]; then BUILD_FULL="npm test"; BUILD_SCOPED="npm test -- {paths}"
elif [[ -f "$TARGET/go.mod" ]]; then BUILD_FULL="go test ./..."; BUILD_SCOPED="go test {packages}"
elif [[ -f "$TARGET/Cargo.toml" ]]; then BUILD_FULL="cargo test"; BUILD_SCOPED="cargo test -p {crate}"
elif [[ -f "$TARGET/pyproject.toml" ]]; then BUILD_FULL="pytest"; BUILD_SCOPED="pytest {paths}"; fi
LOCAL_ONLY_VALUE=false; [[ $LOCAL_ONLY -eq 1 ]] && LOCAL_ONLY_VALUE=true
DATE="$(date +%Y-%m-%d)"

# --- Rendering ---------------------------------------------------------------
esc() { printf '%s' "$1" | sed -e 's/[\/&|]/\\&/g'; }
render() {  # render <src> -> stdout, placeholders substituted
  sed -e "s|{{PROJECT_NAME}}|$(esc "$NAME")|g" \
      -e "s|{{BRANCH}}|$(esc "$BRANCH")|g" \
      -e "s|{{EPIC}}|$(esc "$EPIC")|g" \
      -e "s|{{TICKET_SYSTEM}}|$(esc "$TICKET")|g" \
      -e "s|{{TICKET_PROJECT}}|$(esc "$TICKET_PROJECT")|g" \
      -e "s|{{DESIGN}}|$(esc "$DESIGN")|g" \
      -e "s|{{SPECS_KIND}}|$(esc "$SPECS")|g" \
      -e "s|{{SPECS_DIR}}|$(esc "$SPECS_DIR")|g" \
      -e "s|{{SPECS_GATE}}|$(esc "$SPECS_GATE")|g" \
      -e "s|{{BUILD_FULL}}|$(esc "$BUILD_FULL")|g" \
      -e "s|{{BUILD_SCOPED}}|$(esc "$BUILD_SCOPED")|g" \
      -e "s|{{LOCAL_ONLY}}|$(esc "$LOCAL_ONLY_VALUE")|g" \
      -e "s|{{DATE}}|$(esc "$DATE")|g" \
      -e "s|{{ALIAS}}|$(esc "${ALIAS:-story-loop}")|g" \
      "$1"
}
put() {  # put <src> <relative dst> [verbatim|rendered|prepend:<file>]
  local src="$1" dst="$TARGET/$2" mode="${3:-rendered}"
  if [[ -e "$dst" ]]; then
    if [[ $UPDATE -eq 1 && "$2" == "stories/coverage.py" ]]; then
      [[ $DRY -eq 1 ]] && { echo "[DRY] update $2"; return; }
      cp "$src" "$dst"; say "updated $2"; return
    fi
    skip "$2 exists (kept)"; return
  fi
  [[ $DRY -eq 1 ]] && { echo "[DRY] write $2 ($mode)"; return; }
  mkdir -p "$(dirname "$dst")"
  case "$mode" in
    verbatim) cp "$src" "$dst" ;;
    rendered) render "$src" > "$dst" ;;
    prepend:*) { render "${mode#prepend:}"; echo; render "$src"; } > "$dst" ;;
  esac
  [[ "$dst" == *.sh || "$dst" == *.py ]] && chmod +x "$dst"
  say "wrote $2"
}

echo "story-loop init"
echo "  target: $TARGET"
echo "  name: $NAME  branch: $BRANCH  epic: ${EPIC:-none}  ticket: $TICKET  specs: $SPECS  design: $DESIGN"
echo "  local-only: $LOCAL_ONLY_VALUE  claude: $CLAUDE  alias: ${ALIAS:-none}  build: $BUILD_FULL"
git -C "$TARGET" rev-parse --git-dir >/dev/null 2>&1 || echo "[WARN] $TARGET is not a git repository; the loop is commit-based"

# --- Process files -----------------------------------------------------------
[[ $DRY -eq 1 ]] || mkdir -p "$TARGET/stories/reviews" "$TARGET/stories/agents"
put "$ASSETS/stories/README.md"      stories/README.md
put "$ASSETS/stories/TEMPLATE.md"    stories/TEMPLATE.md
put "$ASSETS/stories/tracker.yaml"   stories/tracker.yaml
put "$SCRIPT_DIR/coverage.py"        stories/coverage.py verbatim
put "$ASSETS/stories/agents/story-implementer.md" stories/agents/story-implementer.md
put "$ASSETS/stories/agents/story-verifier.md"    stories/agents/story-verifier.md
put "$ASSETS/docs/DESIGN.md"         "$DESIGN"
case "$SPECS" in
  quint)
    put "$ASSETS/specs/README.md"        specs/README.md
    put "$ASSETS/specs/check-specs.sh"   scripts/check-specs.sh ;;
  manifest)
    put "$ASSETS/specs/README.md"        specs/README.md
    put "$ASSETS/specs/index.yaml"       specs/index.yaml ;;
esac

# --- Harness adapters --------------------------------------------------------
put "$ASSETS/harness/AGENTS.snippet.md"     stories/harness/AGENTS.snippet.md
put "$ASSETS/harness/CLAUDE.local.md"       stories/harness/CLAUDE.local.snippet.md
put "$ASSETS/harness/cursor-rule.mdc"       stories/harness/story-loop.mdc
if [[ $CLAUDE -eq 1 ]]; then
  put "$ASSETS/stories/agents/story-implementer.md" .claude/agents/story-implementer.md "prepend:$ASSETS/harness/claude/implementer-frontmatter.md"
  put "$ASSETS/stories/agents/story-verifier.md"    .claude/agents/story-verifier.md    "prepend:$ASSETS/harness/claude/verifier-frontmatter.md"
  put "$ASSETS/harness/CLAUDE.local.md" CLAUDE.local.md
  if [[ -n "$ALIAS" ]]; then
    put "$ASSETS/harness/claude/command.md" ".claude/commands/$ALIAS.md"
  fi
fi

# --- Local-only exclusions ---------------------------------------------------
if [[ $LOCAL_ONLY -eq 1 ]]; then
  EXCLUDE="$TARGET/.git/info/exclude"
  if [[ -d "$TARGET/.git" ]] || git -C "$TARGET" rev-parse --git-dir >/dev/null 2>&1; then
    EXCLUDE="$(git -C "$TARGET" rev-parse --git-path info/exclude)"
    [[ "$EXCLUDE" = /* ]] || EXCLUDE="$TARGET/$EXCLUDE"
    if grep -qs '^# story-loop local-only' "$EXCLUDE"; then
      skip "local-only exclusions already in $(basename "$(dirname "$EXCLUDE")")/exclude"
    elif [[ $DRY -eq 1 ]]; then
      echo "[DRY] append local-only exclusions to .git/info/exclude"
    else
      mkdir -p "$(dirname "$EXCLUDE")"
      {
        echo "# story-loop local-only process material (never pushed)"
        echo "stories/"; echo "$(dirname "$DESIGN")/"; echo "CLAUDE.local.md"; echo ".claude/agents/story-implementer.md"
        echo ".claude/agents/story-verifier.md"
        [[ -n "$ALIAS" ]] && echo ".claude/commands/$ALIAS.md"
        [[ "$SPECS" != "none" ]] && echo "specs/"
        [[ "$SPECS" == "quint" ]] && echo "scripts/check-specs.sh"
      } >> "$EXCLUDE"
      say "appended local-only exclusions to .git/info/exclude"
    fi
  else
    echo "[WARN] not a git repository; add the local-only exclusions by hand"
  fi
fi

# --- Validate ----------------------------------------------------------------
if [[ $DRY -eq 0 ]]; then
  if (cd "$TARGET" && python3 stories/coverage.py >/dev/null); then say "stories/tracker.yaml validates; stories/coverage.md rendered"
  else echo "[WARN] python3 stories/coverage.py failed; fix the tracker header before the first story"; fi
fi

cat <<NEXT

Next steps:
  1. Write or point at the design document: $DESIGN
  2. Fill the house rules in stories/agents/story-implementer.md and story-verifier.md
     (build commands, conventions, forbidden things), and the project block in stories/tracker.yaml
  3. Cut the first stories into stories/tracker.yaml (see stories/TEMPLATE.md), then
     python3 stories/coverage.py
  4. Run the loop: /story-loop next (Claude Code) or follow stories/README.md on another harness
NEXT
