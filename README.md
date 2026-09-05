# Agent Skills

A collection of portable agent skills that work across Cursor, Claude, Codex, and other compatible AI coding assistants. Each skill is a self-contained directory under [`skills/`](skills/) with a `SKILL.md` file (instructions + frontmatter), optional `scripts/` for deterministic helpers, and optional `references/` for on-demand documentation.

## Repository layout

```
agent-skills/
├── skills/                     canonical storage — write skills HERE
│   ├── skill-creator/
│   ├── glyph-canvas/
│   └── ...
├── .agents/skills  ->  ../skills    symlink (cross-client convention)
├── .cursor/skills  ->  ../skills    symlink (Cursor discovery)
└── .claude/skills  ->  ../skills    symlink (Claude Code discovery)
```

The symlinks let multiple agent platforms discover the same skill set from a single source of truth. Always create and edit skills under `skills/`; never write into the symlinked paths.

`.agents/skills/` is the emerging cross-client convention — a client that scans it picks up skills installed by any other compliant client, and vice versa. Published packages already ship skills there (Typer and FastAPI both include `.agents/skills/<name>/SKILL.md`), so it is the path that makes this repo portable beyond Claude Code and Cursor.

Skills do not nest. A skill is exactly `skills/<name>/SKILL.md`, one level deep; a `SKILL.md` buried deeper is invisible to every harness's discovery. `validate-skill.sh` fails on one.

## How agents use these skills

Each `SKILL.md` has YAML frontmatter that the host agent reads at session start:

```yaml
---
name: my-skill
description: "What the skill does. Triggers: phrase one, phrase two, phrase three."
---
```

The `description` field — especially the `Triggers:` list — is what the agent matches user requests against. When a request fits, the agent reads the full `SKILL.md` and follows its instructions.

**Stay inside the portable frontmatter fields.** The Agent Skills spec allows six: `name`, `description`, `license`, `compatibility`, `metadata`, and `allowed-tools`. Everything else (`when_to_use`, `argument-hint`, `arguments`, `model`, `effort`, `context`, `agent`, `background`, `hooks`, `paths`, `shell`, `disable-model-invocation`, `user-invocable`, `disallowed-tools`) is Claude Code-only, and packaging or uploading a skill that carries one fails with a hard error rather than ignoring it. Keep trigger phrases inside `description` rather than splitting them into `when_to_use`, and these skills stay loadable everywhere.

`description` is capped at 1,536 characters.

## Available skills

### [skill-creator](skills/skill-creator/)

End-to-end authoring system for new agent skills. Scaffolds directories under `skills/`, writes a valid `SKILL.md`, validates structure (both standard and strict modes), and confirms symlink discovery. Triggers on phrases like "create a skill", "new skill", "skill format", "how to build a skill". Ships with two scripts:

- `scripts/init-skill.sh <name>` — scaffold a new skill (minimal or full profile)
- `scripts/validate-skill.sh <name> [--strict]` — lint a skill's structure and content

### [glyph-canvas](skills/glyph-canvas/)

Render user requests as text drawings or diagrams using only unicode glyphs (box drawing, block elements, arrows, geometric shapes). Triggers on phrases like "draw with unicode", "glyph art", "text diagram", "draw a chart in text". The skill loads its three reference palettes on demand (`Drawing Essentials.md`, `Box Art.md`, `Block Elements.md`) and ships a stdlib-only Python helper for deterministic precision:

- `scripts/glyph.py` — CLI + importable helpers for width measurement (emoji- and CJK-aware), canvas validation (`check`, `fit`, `inspect`, `annotate`), padding, box junctions in five styles, shading primitives (`shade`, `hbar`, `vbar`, `sparkline`), and width-aware layout (`wrap`, `center`, `truncate`, `table`). Run `python3 skills/glyph-canvas/scripts/glyph.py --help` for the full subcommand list.

### [dgx-spark-layout](skills/dgx-spark-layout/)

Storage layout for model-serving and training experiments on an NVIDIA DGX Spark (or any single-node CUDA host). Keeps model weights and compiler caches pinned to each tool's own standard default location instead of duplicating them per experiment — the failure mode being a dir-local `./.cache` that silently re-downloads 60–80 GB checkpoints once per experiment. Covers both the Docker path (bind-mount to the in-container default) and the native path (export the env var the tool actually reads), with a verified table of cache variables for Hugging Face, vLLM, flashinfer, triton, tilelang and llama.cpp. Triggers on phrases like "new experiment", "where should the model download go", "HF_HOME", "duplicated model downloads".

The workspace root is configurable via `DGX_SPARK_ROOT` (default `~/dgx-spark`); the tool cache locations are fixed by the tools themselves and should not be changed.

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
- **Skills live in `skills/`, never in `.agents/skills/`, `.cursor/skills/` or `.claude/skills/`** — those are symlinks.
- **Skills never nest** — one level only; `skills/<name>/SKILL.md`.
- **Frontmatter stays within the six portable spec fields** — see above.
- **Keep SKILL.md under ~500 lines** — move bulk content to `references/` files loaded on demand.
- **Scripts are stdlib-only when possible** — avoids requiring users to install dependencies.
- **One topic per reference file** — no nested `references/` directories.

## License

[MIT](LICENSE). Copy, modify, redistribute, or sell these skills freely; the only
condition is that the copyright notice travels with substantial copies.

Each `SKILL.md` also carries `license: MIT` in its frontmatter, so a skill stays
licensed when it is lifted out of this repo on its own. `license` is one of the
six portable Agent Skills spec fields, so this survives packaging and upload.
