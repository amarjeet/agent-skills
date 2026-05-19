# Agent Skills

A collection of portable agent skills that work across Cursor, Claude, Codex, and other compatible AI coding assistants. Each skill is a self-contained directory under [`skills/`](skills/) with a `SKILL.md` file (instructions + frontmatter), optional `scripts/` for deterministic helpers, and optional `references/` for on-demand documentation.

## Repository layout

```
agent-skills/
├── skills/                     canonical storage — write skills HERE
│   ├── skill-creator/
│   ├── glyph-canvas/
│   └── ...
├── .cursor/skills  ->  ../skills    symlink (Cursor discovery)
└── .claude/skills  ->  ../skills    symlink (Claude discovery)
```

The symlinks let multiple agent platforms discover the same skill set from a single source of truth. Always create and edit skills under `skills/`; never write into the symlinked paths.

## How agents use these skills

Each `SKILL.md` has YAML frontmatter that the host agent reads at session start:

```yaml
---
name: my-skill
description: "What the skill does. Triggers: phrase one, phrase two, phrase three."
---
```

The `description` field — especially the `Triggers:` list — is what the agent matches user requests against. When a request fits, the agent reads the full `SKILL.md` and follows its instructions.

## Available skills

### [skill-creator](skills/skill-creator/)

End-to-end authoring system for new agent skills. Scaffolds directories under `skills/`, writes a valid `SKILL.md`, validates structure (both standard and strict modes), and confirms symlink discovery. Triggers on phrases like "create a skill", "new skill", "skill format", "how to build a skill". Ships with two scripts:

- `scripts/init-skill.sh <name>` — scaffold a new skill (minimal or full profile)
- `scripts/validate-skill.sh <name> [--strict]` — lint a skill's structure and content

### [glyph-canvas](skills/glyph-canvas/)

Render user requests as text drawings or diagrams using only unicode glyphs (box drawing, block elements, arrows, geometric shapes). Triggers on phrases like "draw with unicode", "glyph art", "text diagram", "draw a chart in text". The skill loads its three reference palettes on demand (`Drawing Essentials.md`, `Box Art.md`, `Block Elements.md`) and ships a stdlib-only Python helper for deterministic precision:

- `scripts/glyph.py` — CLI + importable helpers for width measurement (emoji- and CJK-aware), canvas validation (`check`, `fit`, `inspect`, `annotate`), padding, box junctions in five styles, shading primitives (`shade`, `hbar`, `vbar`, `sparkline`), and width-aware layout (`wrap`, `center`, `truncate`, `table`). Run `python3 skills/glyph-canvas/scripts/glyph.py --help` for the full subcommand list.

A small `dad-jokes` demo skill also exists under `skills/dad-jokes/` as a minimal scaffolding example.

## Creating a new skill

The recommended path is to invoke the `skill-creator` skill itself by saying "create a skill" to a compatible agent. Manually:

```bash
skills/skill-creator/scripts/init-skill.sh my-new-skill --profile minimal
# edit skills/my-new-skill/SKILL.md
skills/skill-creator/scripts/validate-skill.sh my-new-skill --strict
```

The init script self-locates and refuses to write outside the canonical `skills/` root, so it can be invoked from any working directory.

## Validating an existing skill

```bash
skills/skill-creator/scripts/validate-skill.sh <skill-name>
skills/skill-creator/scripts/validate-skill.sh <skill-name> --strict
```

Strict mode fails on missing trigger phrases, leftover TODO placeholders in the body, and missing required sections (`## Overview`, `## Instructions`).

## Conventions

- **Directory name must equal the frontmatter `name`** — the validator enforces this.
- **Skills live in `skills/`, never in `.cursor/skills/` or `.claude/skills/`** — those are symlinks.
- **Keep SKILL.md under ~500 lines** — move bulk content to `references/` files loaded on demand.
- **Scripts are stdlib-only when possible** — avoids requiring users to install dependencies.
- **One topic per reference file** — no nested `references/` directories.
