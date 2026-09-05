---
name: skill-creator
description: "End-to-end system for creating, updating, and validating agent skills (Cursor, Claude, Codex, Grok). Triggers: create a skill, make a skill, new skill, update skill, skill format, skill spec, best practices for skills, skill engineering, how to build a skill."
license: MIT
---

# Skill Creator

## Overview

End-to-end authoring system for agent skills: gate the request, scaffold under `skills/`, write SKILL.md, validate, and confirm symlink discovery.

## Instructions

Follow every phase in order unless a skip condition applies.

### Repository Layout

```
<repo-root>/
├── skills/                    # canonical storage — write skills HERE
│   ├── skill-creator/
│   └── <skill-name>/
├── .cursor/skills -> ../skills   # symlink — never write here
└── .claude/skills -> ../skills   # symlink — never write here
```

Agents discover skills via the symlinks, but **all files must be created under `skills/`**.

### Script Invocation (Critical)

Bundled scripts resolve paths from **their own location**, not the shell's current working directory. You may run them from anywhere.

| Script | Purpose |
|--------|---------|
| `scripts/init-skill.sh` | Scaffold a new skill under the skills root |
| `scripts/validate-skill.sh` | Validate structure and content |
| `scripts/lib/paths.sh` | Shared path logic (sourced by other scripts, do not run) |

Always invoke with the repo-relative path:

```bash
skills/skill-creator/scripts/init-skill.sh <skill-name>
skills/skill-creator/scripts/validate-skill.sh <skill-name>
skills/skill-creator/scripts/validate-skill.sh <skill-name> --strict
```

**Never** pass `.cursor/skills` or `.claude/skills` as an output directory. `init-skill.sh` refuses paths outside the canonical skills root.

### Phase 0: Skill-Worthiness Gate

Before any scaffolding, decide whether a skill is the right abstraction.

**Create a skill when** the task encodes non-obvious knowledge: company workflows, proprietary APIs, multi-step procedures, platform-specific integrations, or repeatable patterns the base model would get wrong.

**Do not create a skill when** the request is general knowledge, basic reasoning, a one-off answer, or a test/demo explicitly labeled as such.

If the request fails the gate, tell the user why and suggest alternatives (a rule, a one-shot answer, or a `--profile minimal` test skill if they insist on scaffolding).

### Phase 1: Requirements

**Skip elicitation** when the user already provided: skill name, 1+ trigger phrases, and the core behavior.

**Otherwise ask** until you have:
- 2-3 concrete example tasks
- Exact trigger phrases users will say
- Target platform (Cursor, Claude, Codex, Grok, etc.)
- Constraints (APIs, security, languages)

### Phase 2: Choose Profile & Architecture

```
Is the skill a test/demo OR under ~40 lines with no scripts/references?
  yes → minimal profile
  no  → full profile
```

| Profile | When | Resources |
|---------|------|-----------|
| **minimal** | Demos, smoke tests, single-behavior skills | SKILL.md only |
| **full** | Production workflows | scripts/, references/, assets/ as needed |

Map tasks to resources:
- **scripts/** — deterministic logic you'd rewrite every time
- **references/** — long docs loaded on demand (>100 lines → add TOC)
- **assets/** — templates/files copied or modified, not read into context

Confirm the skill name is kebab-case, descriptive, and unique under `skills/`.

### Phase 3: Scaffold

Run init from anywhere:

```bash
skills/skill-creator/scripts/init-skill.sh <skill-name> --profile minimal
skills/skill-creator/scripts/init-skill.sh <skill-name> --profile full --resources scripts,references
```

Verify output lands in `skills/<skill-name>/`, not a symlink path.

### Phase 4: Frontmatter

Write YAML first. Rules:
- `name`: kebab-case, 2-64 chars, starts/ends with letter or digit, **must match directory name**
- `description`: max 1024 chars, includes `Triggers:` phrase list; wrap in double quotes if value contains `: `

```yaml
---
name: my-skill
description: "Does X for Y team. Triggers: do X, run X workflow, help with X."
---
```

### Phase 5: Author SKILL.md Body

**minimal profile** — required sections only:
1. `# Title`
2. `## Overview` (1 sentence)
3. `## Instructions` (numbered imperative steps)

**full profile** — add:
4. `### Workflow` with numbered steps
5. `### Edge Cases` with if/then rules
6. `## Example` with user input + expected response
7. `## Testing` with validate command

Writing rules:
- Stay under 500 lines; move bulk content to `references/`
- Imperative voice: "Do this", "Never do that"
- Every paragraph must pass: "Would the model already know this?"
- Replace **all** TODO placeholders before validation

### Phase 6: Build Resources (full profile only)

- Write scripts with `set -euo pipefail`; test locally before committing
- One topic per reference file; no nested `references/`
- Assets are for copy/modify workflows, not context loading

### Phase 7: Validate & Iterate

```bash
skills/skill-creator/scripts/validate-skill.sh <skill-name>
skills/skill-creator/scripts/validate-skill.sh <skill-name> --strict
```

Use `--strict` before marking a skill production-ready. It fails on: missing trigger phrases, TODO leftovers in body, missing Overview/Instructions headings.

Fix every `FAIL:` line. Address `WARN:` lines for production skills.

Confirm the skill is visible via symlinks:

```bash
ls .cursor/skills/<skill-name>/SKILL.md
ls .claude/skills/<skill-name>/SKILL.md
```

### End-to-End Checklist

- [ ] Phase 0 gate passed (or user acknowledged test/demo exception)
- [ ] Requirements captured or elicitation skipped with documented spec
- [ ] Profile chosen (minimal vs full)
- [ ] `init-skill.sh` run; skill created under `skills/`, not symlink dirs
- [ ] Frontmatter valid; `name` matches directory
- [ ] All TODO placeholders replaced
- [ ] Resources built and tested (full profile)
- [ ] `validate-skill.sh` passes; `--strict` passes for production
- [ ] Symlink visibility confirmed

### Common Pitfalls

| Mistake | Fix |
|---------|-----|
| Writing to `.cursor/skills/` | Use `init-skill.sh`; it targets `skills/` automatically |
| Relying on CWD | Scripts self-locate; invoke by repo-relative path |
| Name/dir mismatch | Directory must equal frontmatter `name` |
| Unquoted description colons | Wrap description in double quotes |
| Skill for public knowledge | Phase 0 gate — decline or use minimal test profile |
