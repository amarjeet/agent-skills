---
name: glyph-canvas
description: "Render user requests as text drawings or diagrams using only unicode glyphs (box drawing, block elements, arrows, geometric shapes). Triggers: draw with unicode, glyph art, unicode diagram, text diagram, draw a box, draw a chart in text, ascii-style diagram, draw a flowchart in text."
---

# Glyph Canvas

## Overview

Turn drawing or diagram requests into monospaced output composed only from unicode glyphs. The three reference files in `references/` are the glyph palette; load them on demand instead of guessing characters from memory.

## Instructions

The three references are not equal in cost. `Drawing Essentials.md` is small and almost always sufficient. `Block Elements.md` and `Box Art.md` are comprehensive and should be loaded only when the request truly needs them.

### Reference loading policy

- Always read `references/Drawing Essentials.md` first. It covers the common cases: simple frames, arrows, axes, dots, stars, basic geometry.
- Additionally read `references/Box Art.md` only when the request needs frames, tables, trees, multi-segment borders, corner/T-junctions, nested boxes, or precise rounded/double-line styles.
- Additionally read `references/Block Elements.md` only when the request needs shading, fills, gradients, density bars, sparkline-style visualizations, or pixel-style art.
- Never read the heavy references "just in case" — context budget matters.

### Workflow

1. Parse the request and identify primitives needed: boxes, arrows, axes, fills, glyph motifs, labels.
2. If canvas dimensions are unstated and the drawing is non-trivial, ask the user for max width and height before composing.
3. Read `references/Drawing Essentials.md`.
4. Apply the reference loading policy. Read `references/Box Art.md` and/or `references/Block Elements.md` only if their domain is involved.
5. Compose on a single-cell-width grid. After composing, normalize every row with `python3 skills/glyph-canvas/scripts/glyph.py pad` (pipe the draft on stdin) instead of eyeballing column widths.
6. Validate before emitting. Run `glyph.py check` on the canvas to catch ragged rows, tabs, ANSI escapes, or control characters; fix any reported issues. For canvases with user-specified bounds, also run `glyph.py fit MAX_W MAX_H` and address any overflow before emitting.
7. Emit the drawing inside a fenced code block with no language tag (raw fences) so renderers preserve monospaced spacing.
8. Below the block, briefly note any glyph used that requires a broad-coverage font, or any deliberate stylistic choice (e.g. half-block shading used to fake a gradient).

### Helpers

A stdlib-only Python 3 helper at `scripts/glyph.py` provides deterministic primitives for width measurement, validation, padding, junction lookup, shading, layout, and diagnostics. Prefer running these helpers over inferring widths or picking junction glyphs from memory; they are cheap and do not count against the reference loading policy.

Invocation pattern:

```
python3 skills/glyph-canvas/scripts/glyph.py <subcommand> [args]
```

All subcommands accept text via a positional argument or stdin (use `-` to be explicit). Run `glyph.py <sub> --help` for the full argument list of any subcommand.

Most-used subcommands:

- `width [TEXT]` — true display width of a string (emoji- and CJK-aware).
- `check [TEXT]` — validate a canvas; exits 1 with a structured list of issues if anything is wrong.
- `pad [--width N] [--fill C] [--align left|center|right] [TEXT]` — pad every row to uniform display width.
- `fit MAX_W MAX_H [TEXT]` — exits 0 if the canvas fits inside the box, 1 with overflow detail otherwise.
- `inspect [TEXT]` — full diagnostic: dimensions, rectangularity, issues, suspicious chars.
- `annotate [TEXT]` — print the canvas with a digit row under each line showing per-cell widths. Fastest way to debug misalignment.
- `junction TRBL [--style single|double|rounded|thick|ascii]` — correct junction glyph for a TRBL mask like `1101` (top, right, bottom, left).
- `box W H [--style ...] [--title T] [--title-align L|C|R] [--fill C]` — render an empty frame.
- `shade INTENSITY [--palette PAL]` / `hbar V MAX W [--palette PAL]` / `vbar V MAX H [--palette PAL]` / `sparkline V1,V2,... [--palette PAL]` — shading primitives; every palette is a per-call argument so callers can substitute their own.
- `table [--headers H1,H2,...] [--style ...] [--align ...]` — render a table from `|`-separated rows on stdin; borders are computed with the correct junctions.
- `wrap WIDTH` / `center WIDTH` / `truncate WIDTH [--ellipsis E]` — width-aware text layout.
- `classify CHAR` — describe a single character (codepoint, category, EAW, cell width, class bucket).
- `ascii-fallback` — substitute closest ASCII for box/arrow/block glyphs when ASCII-only is requested.
- `selftest` — internal smoke tests; exit 0 means the helper works on this Python.

Every helper function takes its style, palette, fill, alignment, and width thresholds as arguments — no hidden defaults to memorize. Pass `--no-emoji-wide` on width-related subcommands if you specifically need East-Asian-Width-only semantics.

### Output rules

- One glyph per cell. Do not mix single-width and double-width characters on the same row.
- Default to glyphs from `Drawing Essentials.md`; reach into the heavier references only when the simpler palette cannot express the request.
- Keep commentary outside the code block. Inside the fence, only the drawing.
- Prefer plain ASCII fallback glyphs (`-`, `|`, `+`) only when the user explicitly asks for ASCII; otherwise use the proper unicode forms. `glyph.py ascii-fallback` performs the substitution deterministically when needed.
- When uncertain about alignment, run `glyph.py annotate` or `glyph.py inspect` first. The digit row under each canvas line shows per-cell widths and pinpoints the offending column.

### Edge Cases

- If the request is ASCII-only, still works — pick the simplest glyphs and skip Box Art / Block Elements entirely. `glyph.py junction TRBL --style ascii` and `glyph.py box W H --style ascii` produce correct ASCII frames.
- If the request mixes emoji or CJK glyphs, flag double-width cell behavior and offer a single-width alternative before drawing. Use `glyph.py width` for true display widths and `glyph.py inspect` to spot mixed-width rows.
- If color or a continuous gradient is requested, emulate with shade blocks (`█ ▓ ▒ ░`) from `references/Block Elements.md` and state the monochrome limitation. `glyph.py shade INTENSITY`, `hbar`, `vbar`, and `sparkline` produce the correct glyphs deterministically and accept custom palettes via `--palette`.
- If the drawing cannot fit cleanly at the requested size — confirm with `glyph.py fit MAX_W MAX_H` — ask whether to scale down, crop, or simplify rather than producing a broken-aligned canvas.
- If a glyph from `Drawing Essentials.md` already satisfies the request, do not load the heavier references.
- Helper limitation: `glyph.py` approximates emoji ZWJ sequences, skin-tone modifiers, and Variation Selector-16 as the base codepoint's width. If precision on those specific cases matters, fall back to `annotate` + manual verification.

## Example

User: "draw a labeled box around the word HELLO"

Response:

```
┌───────┐
│ HELLO │
└───────┘
```

Only `Drawing Essentials.md` was needed; `Box Art.md` and `Block Elements.md` were intentionally not loaded.

## Testing

Run validation from anywhere:

```bash
skills/skill-creator/scripts/validate-skill.sh glyph-canvas
skills/skill-creator/scripts/validate-skill.sh glyph-canvas --strict
python3 skills/glyph-canvas/scripts/glyph.py selftest
```
