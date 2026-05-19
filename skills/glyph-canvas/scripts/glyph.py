#!/usr/bin/env python3
"""glyph.py — unicode canvas helpers for the glyph-canvas skill.

Stdlib-only (Python 3.8+). Provides width measurement, validation,
padding, junction lookup, shading, layout, and diagnostics for
unicode text drawings. Every function is parameterized; no hidden
magic constants.

Limitations:
  - Emoji width covers common pictographic ranges. ZWJ sequences,
    skin-tone modifiers, and Variation Selector-16 are approximated
    as the base codepoint's width.
  - Unicode data follows the host Python's `unicodedata` version;
    very new codepoints may misclassify until the system Python
    ships an updated database.

Dual interface:
  - import the functions directly (`from glyph import display_width, ...`)
  - or run as a CLI: `python3 glyph.py <subcommand> [args]`

Run `python3 glyph.py --help` for the full subcommand list, and
`python3 glyph.py selftest` to verify the helper works on this Python.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple, Union


VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

# Wide emoji ranges. Most emoji are East Asian Width = Neutral in the
# Unicode database even though terminals render them double-wide; this
# table corrects the common pictographic blocks.
EMOJI_WIDE_RANGES: Tuple[Tuple[int, int], ...] = (
    (0x1F1E6, 0x1F1FF),  # Regional indicators (flag halves)
    (0x1F300, 0x1F5FF),  # Misc Symbols and Pictographs
    (0x1F600, 0x1F64F),  # Emoticons
    (0x1F680, 0x1F6FF),  # Transport and Map
    (0x1F900, 0x1F9FF),  # Supplemental Symbols and Pictographs
    (0x1FA70, 0x1FAFF),  # Symbols and Pictographs Extended-A
)

BOX_DRAWING_RANGE: Tuple[int, int] = (0x2500, 0x257F)
BLOCK_ELEMENTS_RANGE: Tuple[int, int] = (0x2580, 0x259F)
GEOMETRIC_SHAPES_RANGE: Tuple[int, int] = (0x25A0, 0x25FF)
ARROW_RANGES: Tuple[Tuple[int, int], ...] = (
    (0x2190, 0x21FF),  # Arrows
    (0x27F0, 0x27FF),  # Supplemental Arrows-A
    (0x2900, 0x297F),  # Supplemental Arrows-B
    (0x2B00, 0x2BFF),  # Misc Symbols and Arrows (partial overlap is ok)
)

VALID_STYLES: Tuple[str, ...] = ("single", "double", "rounded", "thick", "ascii")

# Box junction lookup keyed by (top, right, bottom, left) booleans as ints.
# Missing combos fall back to space. Rounded shares horizontal/vertical and
# T-junctions with single; only its corners differ.
_JUNCTION_TABLE: Dict[str, Dict[Tuple[int, int, int, int], str]] = {
    "single": {
        (0, 1, 0, 1): "─", (1, 0, 1, 0): "│",
        (0, 1, 1, 0): "┌", (0, 0, 1, 1): "┐",
        (1, 1, 0, 0): "└", (1, 0, 0, 1): "┘",
        (1, 1, 1, 0): "├", (1, 0, 1, 1): "┤",
        (0, 1, 1, 1): "┬", (1, 1, 0, 1): "┴",
        (1, 1, 1, 1): "┼",
        (0, 1, 0, 0): "╶", (0, 0, 0, 1): "╴",
        (1, 0, 0, 0): "╵", (0, 0, 1, 0): "╷",
    },
    "double": {
        (0, 1, 0, 1): "═", (1, 0, 1, 0): "║",
        (0, 1, 1, 0): "╔", (0, 0, 1, 1): "╗",
        (1, 1, 0, 0): "╚", (1, 0, 0, 1): "╝",
        (1, 1, 1, 0): "╠", (1, 0, 1, 1): "╣",
        (0, 1, 1, 1): "╦", (1, 1, 0, 1): "╩",
        (1, 1, 1, 1): "╬",
    },
    "rounded": {
        (0, 1, 0, 1): "─", (1, 0, 1, 0): "│",
        (0, 1, 1, 0): "╭", (0, 0, 1, 1): "╮",
        (1, 1, 0, 0): "╰", (1, 0, 0, 1): "╯",
        (1, 1, 1, 0): "├", (1, 0, 1, 1): "┤",
        (0, 1, 1, 1): "┬", (1, 1, 0, 1): "┴",
        (1, 1, 1, 1): "┼",
        (0, 1, 0, 0): "╶", (0, 0, 0, 1): "╴",
        (1, 0, 0, 0): "╵", (0, 0, 1, 0): "╷",
    },
    "thick": {
        (0, 1, 0, 1): "━", (1, 0, 1, 0): "┃",
        (0, 1, 1, 0): "┏", (0, 0, 1, 1): "┓",
        (1, 1, 0, 0): "┗", (1, 0, 0, 1): "┛",
        (1, 1, 1, 0): "┣", (1, 0, 1, 1): "┫",
        (0, 1, 1, 1): "┳", (1, 1, 0, 1): "┻",
        (1, 1, 1, 1): "╋",
    },
    "ascii": {
        (0, 1, 0, 1): "-", (1, 0, 1, 0): "|",
        (0, 1, 1, 0): "+", (0, 0, 1, 1): "+",
        (1, 1, 0, 0): "+", (1, 0, 0, 1): "+",
        (1, 1, 1, 0): "+", (1, 0, 1, 1): "+",
        (0, 1, 1, 1): "+", (1, 1, 0, 1): "+",
        (1, 1, 1, 1): "+",
        (0, 1, 0, 0): "-", (0, 0, 0, 1): "-",
        (1, 0, 0, 0): "|", (0, 0, 1, 0): "|",
    },
}

ASCII_FALLBACK_DEFAULT: Dict[str, str] = {
    # horizontal lines
    "─": "-", "━": "-", "═": "=", "╌": "-", "╍": "-",
    "┄": "-", "┅": "-", "┈": "-", "┉": "-",
    # vertical lines
    "│": "|", "┃": "|", "║": "|", "╎": "|", "╏": "|",
    "┆": "|", "┇": "|", "┊": "|", "┋": "|",
    # corners
    "┌": "+", "┐": "+", "└": "+", "┘": "+",
    "┏": "+", "┓": "+", "┗": "+", "┛": "+",
    "╔": "+", "╗": "+", "╚": "+", "╝": "+",
    "╭": "+", "╮": "+", "╯": "+", "╰": "+",
    # T-junctions / cross
    "├": "+", "┤": "+", "┬": "+", "┴": "+", "┼": "+",
    "┣": "+", "┫": "+", "┳": "+", "┻": "+", "╋": "+",
    "╠": "+", "╣": "+", "╦": "+", "╩": "+", "╬": "+",
    # arrows
    "→": "->", "←": "<-", "↑": "^", "↓": "v",
    "↔": "<->", "↕": "|",
    "⇒": "=>", "⇐": "<=", "⇑": "^", "⇓": "v",
    # block elements
    "█": "#", "▓": "#", "▒": ".", "░": ".",
    "▀": "-", "▄": "_", "▌": "[", "▐": "]",
    # bullets / stars / geometric
    "•": "*", "●": "*", "◆": "*", "★": "*", "☆": "*",
    "◯": "o", "○": "o", "■": "#", "□": "[]",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _in_ranges(cp: int, ranges: Iterable[Tuple[int, int]]) -> bool:
    for lo, hi in ranges:
        if lo <= cp <= hi:
            return True
    return False


def _in_range(cp: int, lo_hi: Tuple[int, int]) -> bool:
    return lo_hi[0] <= cp <= lo_hi[1]


# ===========================================================================
# Section 1: Width measurement
# ===========================================================================

def cell_width(ch: str, *, emoji_wide: bool = True, tab_width: int = 0) -> int:
    """Display width of a single character in monospace cells.

    Combining marks and zero-width formatting chars return 0.
    East-Asian Wide/Fullwidth chars return 2. When `emoji_wide=True`,
    common pictographic ranges also return 2. Default printable ASCII
    returns 1. Tabs return `tab_width` (default 0; pass 4/8 for expanded).
    """
    if not ch:
        return 0
    if len(ch) > 1:
        return display_width(ch, emoji_wide=emoji_wide, tab_width=tab_width)
    if ch == "\t":
        return tab_width
    if ch in ("\n", "\r"):
        return 0
    cp = ord(ch)
    if 0x20 <= cp < 0x7F:
        return 1
    cat = unicodedata.category(ch)
    if cat in ("Mn", "Me", "Cf"):
        return 0
    if cat == "Cc":
        return 0
    eaw = unicodedata.east_asian_width(ch)
    if eaw in ("W", "F"):
        return 2
    if emoji_wide and _in_ranges(cp, EMOJI_WIDE_RANGES):
        return 2
    return 1


def display_width(s: str, *, emoji_wide: bool = True, tab_width: int = 0) -> int:
    """Sum of `cell_width` across the string."""
    return sum(
        cell_width(ch, emoji_wide=emoji_wide, tab_width=tab_width) for ch in s
    )


def line_widths(canvas: str, **kw) -> List[int]:
    """Display width of every line in the canvas. Empty input yields [0]."""
    lines = canvas.splitlines() or [""]
    return [display_width(line, **kw) for line in lines]


def max_width(canvas: str, **kw) -> int:
    widths = line_widths(canvas, **kw)
    return max(widths) if widths else 0


# ===========================================================================
# Section 2: Validation
# ===========================================================================

@dataclass
class Issue:
    kind: str
    row: int
    col: int = -1
    char: str = ""
    codepoint: str = ""
    message: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def __str__(self) -> str:
        loc = (
            f"row {self.row + 1} col {self.col + 1}"
            if self.col >= 0
            else f"row {self.row + 1}"
        )
        return f"[{self.kind}] {loc}: {self.message}"


@dataclass
class FitResult:
    ok: bool
    actual_w: int
    actual_h: int
    max_w: int
    max_h: int
    overflow_w: int
    overflow_h: int
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def __str__(self) -> str:
        status = "FIT" if self.ok else "OVERFLOW"
        tail = f" — {self.reason}" if self.reason else ""
        return (
            f"{status}: actual {self.actual_w}x{self.actual_h}, "
            f"max {self.max_w}x{self.max_h}{tail}"
        )


def is_rectangular(canvas: str, **kw) -> bool:
    """True if every line in the canvas has the same display width."""
    widths = line_widths(canvas, **kw)
    return len(set(widths)) <= 1


def validate(
    canvas: str,
    *,
    allow_tabs: bool = False,
    allow_ansi: bool = False,
    allow_double_width: bool = True,
    allow_combining: bool = True,
    **kw,
) -> List[Issue]:
    """Return a list of structured issues found in the canvas.

    Issue kinds: ragged, tab, ansi, control, double_width, combining.
    """
    issues: List[Issue] = []
    lines = canvas.splitlines() or [""]
    widths = [display_width(line, **kw) for line in lines]
    target = max(widths) if widths else 0
    for i, line in enumerate(lines):
        if widths[i] != target:
            issues.append(
                Issue(
                    kind="ragged",
                    row=i,
                    col=-1,
                    message=f"display width {widths[i]} != canvas max {target}",
                )
            )
        if not allow_tabs and "\t" in line:
            col = line.index("\t")
            issues.append(
                Issue(
                    kind="tab",
                    row=i,
                    col=col,
                    char="\\t",
                    codepoint="U+0009",
                    message="tab character breaks monospace alignment",
                )
            )
        if not allow_ansi:
            m = ANSI_RE.search(line)
            if m:
                issues.append(
                    Issue(
                        kind="ansi",
                        row=i,
                        col=m.start(),
                        message="ANSI escape sequence present",
                    )
                )
        for j, ch in enumerate(line):
            cp = ord(ch)
            if cp < 0x20 and ch != "\t":
                issues.append(
                    Issue(
                        kind="control",
                        row=i,
                        col=j,
                        char=repr(ch),
                        codepoint=f"U+{cp:04X}",
                        message="control character",
                    )
                )
            if not allow_double_width and cell_width(ch, **kw) == 2:
                issues.append(
                    Issue(
                        kind="double_width",
                        row=i,
                        col=j,
                        char=ch,
                        codepoint=f"U+{cp:04X}",
                        message="double-width cell in single-width canvas",
                    )
                )
            if not allow_combining and unicodedata.category(ch) in ("Mn", "Me"):
                issues.append(
                    Issue(
                        kind="combining",
                        row=i,
                        col=j,
                        char=ch,
                        codepoint=f"U+{cp:04X}",
                        message="combining mark",
                    )
                )
    return issues


def fits_in(canvas: str, max_w: int, max_h: int, **kw) -> FitResult:
    """Check whether the canvas fits in a `max_w` x `max_h` box."""
    lines = canvas.splitlines() or [""]
    actual_h = len(lines)
    actual_w = max((display_width(line, **kw) for line in lines), default=0)
    overflow_w = max(0, actual_w - max_w)
    overflow_h = max(0, actual_h - max_h)
    ok = overflow_w == 0 and overflow_h == 0
    parts: List[str] = []
    if overflow_w:
        parts.append(f"width over by {overflow_w}")
    if overflow_h:
        parts.append(f"height over by {overflow_h}")
    reason = "; ".join(parts)
    return FitResult(
        ok=ok,
        actual_w=actual_w,
        actual_h=actual_h,
        max_w=max_w,
        max_h=max_h,
        overflow_w=overflow_w,
        overflow_h=overflow_h,
        reason=reason,
    )


def bounding_box(canvas: str, *, blank_chars: str = " ", **kw) -> Tuple[int, int]:
    """Smallest enclosing rectangle of visible content, in (rows, cols)."""
    lines = canvas.splitlines()
    while lines and all(c in blank_chars for c in lines[-1]):
        lines.pop()
    if not lines:
        return (0, 0)
    trimmed = [line.rstrip(blank_chars) for line in lines]
    rows = len(trimmed)
    cols = max((display_width(line, **kw) for line in trimmed), default=0)
    return (rows, cols)


# ===========================================================================
# Section 3: Padding / normalization
# ===========================================================================

def pad_row(
    row: str,
    width: int,
    *,
    fill: str = " ",
    align: str = "left",
    **kw,
) -> str:
    """Pad `row` to exactly `width` display cells.

    `fill` may be any string; it's repeated in its own display-width
    increments and topped up with spaces when the remainder isn't an
    exact multiple. Rows already at or above `width` are returned as-is.
    """
    cur = display_width(row, **kw)
    if cur >= width:
        return row
    pad_cells = width - cur
    fill_w = display_width(fill, **kw) or 1

    def _build(cells: int) -> str:
        n = cells // fill_w
        leftover = cells - n * fill_w
        return fill * n + (" " * leftover)

    if align == "left":
        return row + _build(pad_cells)
    if align == "right":
        return _build(pad_cells) + row
    if align == "center":
        left_cells = pad_cells // 2
        right_cells = pad_cells - left_cells
        return _build(left_cells) + row + _build(right_cells)
    raise ValueError(f"unknown align: {align!r}")


def pad_canvas(
    canvas: str,
    *,
    width: Optional[int] = None,
    fill: str = " ",
    align: str = "left",
    **kw,
) -> str:
    """Pad every line of the canvas to `width` (or the canvas max if None)."""
    lines = canvas.splitlines() or [""]
    target = (
        width
        if width is not None
        else max((display_width(line, **kw) for line in lines), default=0)
    )
    return "\n".join(
        pad_row(line, target, fill=fill, align=align, **kw) for line in lines
    )


def truncate(
    row: str,
    width: int,
    *,
    ellipsis: Optional[str] = None,
    **kw,
) -> str:
    """Width-aware truncation that never splits a double-width cell.

    If `ellipsis` is given and the row would not fit, the ellipsis is
    appended within the final width budget.
    """
    if width <= 0:
        return ""
    ell = ellipsis or ""
    ell_w = display_width(ell, **kw)
    if ell_w >= width:
        ell = ""
        ell_w = 0
    full_w = display_width(row, **kw)
    if full_w <= width:
        return row
    budget = width - ell_w
    out: List[str] = []
    used = 0
    for ch in row:
        cw = cell_width(ch, **kw)
        if used + cw > budget:
            break
        out.append(ch)
        used += cw
    return "".join(out) + ell


def replace_tabs(text: str, *, tab_size: int = 4) -> str:
    """Expand TAB characters to spaces."""
    return text.expandtabs(tab_size)


def strip_trailing(canvas: str, *, chars: str = " \t") -> str:
    """Strip trailing whitespace from every line."""
    return "\n".join(line.rstrip(chars) for line in canvas.splitlines())


# ===========================================================================
# Section 4: Classification
# ===========================================================================

def is_box_drawing(ch: str) -> bool:
    return bool(ch) and _in_range(ord(ch[0]), BOX_DRAWING_RANGE)


def is_block_element(ch: str) -> bool:
    return bool(ch) and _in_range(ord(ch[0]), BLOCK_ELEMENTS_RANGE)


def is_geometric(ch: str) -> bool:
    return bool(ch) and _in_range(ord(ch[0]), GEOMETRIC_SHAPES_RANGE)


def is_arrow(ch: str) -> bool:
    return bool(ch) and _in_ranges(ord(ch[0]), ARROW_RANGES)


def is_combining(ch: str) -> bool:
    return bool(ch) and unicodedata.category(ch[0]) in ("Mn", "Me")


def is_double_width(ch: str, *, emoji_wide: bool = True) -> bool:
    return bool(ch) and cell_width(ch[0], emoji_wide=emoji_wide) == 2


def classify(ch: str) -> str:
    """Bucket a character into one of:
    combining, box_drawing, block, geometric, arrow, ascii, wide, other.
    """
    if not ch:
        return "other"
    c = ch[0]
    if is_combining(c):
        return "combining"
    if is_box_drawing(c):
        return "box_drawing"
    if is_block_element(c):
        return "block"
    if is_geometric(c):
        return "geometric"
    if is_arrow(c):
        return "arrow"
    if ord(c) < 0x80:
        return "ascii"
    if cell_width(c) == 2:
        return "wide"
    return "other"


# ===========================================================================
# Section 5: Box junctions
# ===========================================================================

def junction(
    top: bool,
    right: bool,
    bottom: bool,
    left: bool,
    *,
    style: str = "single",
    weight: Optional[str] = None,
) -> str:
    """Return the correct junction glyph for connections on each side.

    `style` is one of single, double, rounded, thick, ascii. `weight` is
    reserved for future asymmetric-thickness lookups (currently ignored).
    Unsupported combinations for a given style return a single space.
    """
    if style not in _JUNCTION_TABLE:
        raise ValueError(
            f"unknown style {style!r}; pick one of {VALID_STYLES}"
        )
    _ = weight  # placeholder; documented for future extension
    table = _JUNCTION_TABLE[style]
    key = (int(bool(top)), int(bool(right)), int(bool(bottom)), int(bool(left)))
    if key == (0, 0, 0, 0):
        return " "
    return table.get(key, " ")


def corners(style: str = "single") -> Tuple[str, str, str, str]:
    """Return (top-left, top-right, bottom-left, bottom-right) for `style`."""
    tl = junction(False, True, True, False, style=style)
    tr = junction(False, False, True, True, style=style)
    bl = junction(True, True, False, False, style=style)
    br = junction(True, False, False, True, style=style)
    return (tl, tr, bl, br)


def box(
    width: int,
    height: int,
    *,
    style: str = "single",
    title: Optional[str] = None,
    title_align: str = "center",
    fill: str = " ",
    **kw,
) -> str:
    """Render an empty frame of the given outer dimensions.

    A `title` string is embedded into the top edge if supplied; it is
    automatically truncated with an ellipsis if too wide. `fill` is the
    glyph used for interior cells (default: space).
    """
    if width < 2 or height < 2:
        raise ValueError("box requires width >= 2 and height >= 2")
    tl, tr, bl, br = corners(style)
    h = junction(False, True, False, True, style=style)
    v = junction(True, False, True, False, style=style)
    inner_w = width - 2
    fill_w = display_width(fill, **kw) or 1
    n_fills = inner_w // fill_w
    leftover = inner_w - n_fills * fill_w
    inner = fill * n_fills + (" " * leftover) if fill != " " else " " * inner_w
    top = tl + h * inner_w + tr
    mid = v + inner + v
    bot = bl + h * inner_w + br
    rows = [top] + [mid] * (height - 2) + [bot]
    if title:
        title_str = " " + title + " "
        title_w = display_width(title_str, **kw)
        if title_w > inner_w:
            shrunk = truncate(title, max(0, inner_w - 4), ellipsis="…", **kw)
            title_str = " " + shrunk + " "
            title_w = display_width(title_str, **kw)
        if title_align == "left":
            new_top = tl + title_str + h * max(0, inner_w - title_w) + tr
        elif title_align == "right":
            new_top = tl + h * max(0, inner_w - title_w) + title_str + tr
        else:
            left_pad = (inner_w - title_w) // 2
            right_pad = inner_w - title_w - left_pad
            new_top = tl + h * left_pad + title_str + h * right_pad + tr
        rows[0] = new_top
    return "\n".join(rows)


# ===========================================================================
# Section 6: Shading / blocks
# ===========================================================================

def shade(intensity: float, *, palette: str = " ░▒▓█") -> str:
    """Single glyph for an intensity in [0, 1] picked from `palette`."""
    if not palette:
        return ""
    if intensity != intensity:  # NaN
        return palette[0]
    clamped = max(0.0, min(1.0, intensity))
    idx = int(clamped * len(palette))
    if idx >= len(palette):
        idx = len(palette) - 1
    return palette[idx]


def hbar(
    value: float,
    max_value: float,
    width: int,
    *,
    palette: str = "█▉▊▋▌▍▎▏",
    empty: str = " ",
) -> str:
    """Horizontal bar of `width` cells representing `value / max_value`.

    `palette` runs FULL → thinnest (8 chars typical). The first glyph
    represents a fully-filled cell; subsequent glyphs are used for the
    fractional trailing cell.
    """
    if width <= 0:
        return ""
    if max_value <= 0:
        return empty * width
    ratio = max(0.0, min(1.0, value / max_value))
    bins = len(palette)
    if bins == 0:
        return empty * width
    total_units = ratio * width * bins
    full_cells = int(total_units // bins)
    remainder = int(round(total_units - full_cells * bins))
    if remainder >= bins:
        full_cells += 1
        remainder = 0
    full_cells = min(full_cells, width)
    out = palette[0] * full_cells
    if remainder > 0 and full_cells < width:
        out += palette[bins - remainder]
        full_cells += 1
    out += empty * (width - full_cells)
    return out


def vbar(
    value: float,
    max_value: float,
    height: int,
    *,
    palette: str = "▁▂▃▄▅▆▇█",
    empty: str = " ",
) -> List[str]:
    """Vertical bar as a list of one-glyph rows, top-down.

    `palette` runs thinnest → FULL (8 chars typical).
    """
    if height <= 0:
        return []
    if max_value <= 0:
        return [empty] * height
    bins = len(palette)
    if bins == 0:
        return [empty] * height
    ratio = max(0.0, min(1.0, value / max_value))
    total_units = ratio * height * bins
    full_rows = int(total_units // bins)
    remainder = int(round(total_units - full_rows * bins))
    if remainder >= bins:
        full_rows += 1
        remainder = 0
    full_rows = min(full_rows, height)
    bot_up: List[str] = [palette[-1]] * full_rows
    if remainder > 0 and full_rows < height:
        bot_up.append(palette[remainder - 1])
    while len(bot_up) < height:
        bot_up.append(empty)
    return list(reversed(bot_up))


def sparkline(
    values: List[float],
    *,
    palette: str = "▁▂▃▄▅▆▇█",
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
) -> str:
    """One-line sparkline for a sequence of numbers."""
    if not values:
        return ""
    lo = min(values) if min_value is None else min_value
    hi = max(values) if max_value is None else max_value
    if hi <= lo:
        return palette[0] * len(values)
    bins = len(palette)
    out: List[str] = []
    for v in values:
        ratio = (v - lo) / (hi - lo)
        ratio = max(0.0, min(1.0, ratio))
        idx = int(ratio * bins)
        if idx >= bins:
            idx = bins - 1
        out.append(palette[idx])
    return "".join(out)


# ===========================================================================
# Section 7: Layout
# ===========================================================================

def center(text: str, width: int, *, fill: str = " ", **kw) -> str:
    return pad_row(text, width, fill=fill, align="center", **kw)


def ljust_cells(text: str, width: int, *, fill: str = " ", **kw) -> str:
    return pad_row(text, width, fill=fill, align="left", **kw)


def rjust_cells(text: str, width: int, *, fill: str = " ", **kw) -> str:
    return pad_row(text, width, fill=fill, align="right", **kw)


def wrap(text: str, width: int, *, break_long: bool = True, **kw) -> List[str]:
    """Width-aware word wrap. Splits on spaces; preserves explicit newlines."""
    if width <= 0:
        return [text] if text else []
    lines: List[str] = []
    paragraphs = text.splitlines() or [""]
    for paragraph in paragraphs:
        if not paragraph:
            lines.append("")
            continue
        words = paragraph.split(" ")
        cur: List[str] = []
        cur_w = 0
        for word in words:
            word_w = display_width(word, **kw)
            sep_w = 1 if cur else 0
            if cur_w + sep_w + word_w <= width:
                cur.append(word)
                cur_w += sep_w + word_w
            else:
                if cur:
                    lines.append(" ".join(cur))
                    cur = []
                    cur_w = 0
                if word_w > width and break_long:
                    while display_width(word, **kw) > width:
                        chunk = truncate(word, width, **kw)
                        lines.append(chunk)
                        word = word[len(chunk):]
                    if word:
                        cur = [word]
                        cur_w = display_width(word, **kw)
                else:
                    cur = [word]
                    cur_w = word_w
        if cur:
            lines.append(" ".join(cur))
    return lines


def table(
    rows: List[List[str]],
    *,
    headers: Optional[List[str]] = None,
    style: str = "single",
    align: Union[str, List[str]] = "left",
    padding: int = 1,
    **kw,
) -> str:
    """Render a table with correct unicode borders.

    `align` may be a single value (applied to every column) or a list of
    `left|center|right` per column. `padding` is the number of spaces on
    each side of cell contents.
    """
    body: List[List[str]] = list(rows)
    if not body and not headers:
        return ""
    all_rows: List[List[str]] = ([list(headers)] if headers else []) + body
    n_cols = max(len(r) for r in all_rows)
    norm: List[List[str]] = [
        [str(c) for c in row] + [""] * (n_cols - len(row)) for row in all_rows
    ]
    if isinstance(align, str):
        col_align = [align] * n_cols
    else:
        col_align = list(align) + ["left"] * (n_cols - len(align))
    col_w = [0] * n_cols
    for row in norm:
        for j, cell in enumerate(row):
            w = display_width(cell, **kw)
            if w > col_w[j]:
                col_w[j] = w
    pad_str = " " * padding
    h = junction(False, True, False, True, style=style)
    v = junction(True, False, True, False, style=style)
    tl, tr, bl, br = corners(style)
    t_top = junction(False, True, True, True, style=style)
    t_bot = junction(True, True, False, True, style=style)
    t_left = junction(True, True, True, False, style=style)
    t_right = junction(True, False, True, True, style=style)
    cross = junction(True, True, True, True, style=style)

    def hline(left: str, mid: str, right: str) -> str:
        segments = [h * (col_w[j] + 2 * padding) for j in range(n_cols)]
        return left + mid.join(segments) + right

    top_line = hline(tl, t_top, tr)
    sep_line = hline(t_left, cross, t_right)
    bot_line = hline(bl, t_bot, br)

    def render_row(row: List[str]) -> str:
        cells = []
        for j, cell in enumerate(row):
            aligned = pad_row(cell, col_w[j], align=col_align[j], **kw)
            cells.append(pad_str + aligned + pad_str)
        return v + v.join(cells) + v

    out: List[str] = [top_line]
    start_idx = 0
    if headers:
        out.append(render_row(norm[0]))
        out.append(sep_line)
        start_idx = 1
    for row in norm[start_idx:]:
        out.append(render_row(row))
    out.append(bot_line)
    return "\n".join(out)


def columns(
    items: List[str],
    total_width: int,
    *,
    gutter: int = 2,
    align: str = "left",
    **kw,
) -> str:
    """Multi-column layout of `items` within `total_width`."""
    if not items:
        return ""
    max_item_w = max(display_width(s, **kw) for s in items)
    col_w = max_item_w
    n_cols = max(1, (total_width + gutter) // (col_w + gutter))
    n_rows = (len(items) + n_cols - 1) // n_cols
    grid = [[""] * n_cols for _ in range(n_rows)]
    for i, item in enumerate(items):
        r = i % n_rows
        c = i // n_rows
        grid[r][c] = item
    sep = " " * gutter
    lines: List[str] = []
    for row in grid:
        cells = [pad_row(cell, col_w, align=align, **kw) for cell in row]
        lines.append(sep.join(cells).rstrip())
    return "\n".join(lines)


# ===========================================================================
# Section 8: Diagnostics
# ===========================================================================

@dataclass
class InspectReport:
    lines: int
    max_width: int
    min_width: int
    rectangular: bool
    issues: List[Issue] = field(default_factory=list)
    suspicious: List[Tuple[int, int, str, str]] = field(default_factory=list)
    expected_width: Optional[int] = None
    expected_height: Optional[int] = None
    fit_ok: Optional[bool] = None

    def to_dict(self) -> dict:
        return {
            "lines": self.lines,
            "max_width": self.max_width,
            "min_width": self.min_width,
            "rectangular": self.rectangular,
            "issues": [i.to_dict() for i in self.issues],
            "suspicious": [
                {"row": r, "col": c, "char": ch, "reason": why}
                for r, c, ch, why in self.suspicious
            ],
            "expected_width": self.expected_width,
            "expected_height": self.expected_height,
            "fit_ok": self.fit_ok,
        }

    def __str__(self) -> str:
        out: List[str] = ["Canvas inspection"]
        out.append(f"  lines:        {self.lines}")
        out.append(f"  max width:    {self.max_width}")
        out.append(f"  min width:    {self.min_width}")
        out.append(f"  rectangular:  {'yes' if self.rectangular else 'no'}")
        if self.expected_width is not None or self.expected_height is not None:
            ew = self.expected_width if self.expected_width is not None else "*"
            eh = self.expected_height if self.expected_height is not None else "*"
            verdict = "fits" if self.fit_ok else "overflow"
            out.append(f"  expected:     {ew} x {eh}  ({verdict})")
        out.append(f"  issues:       {len(self.issues) or 'none'}")
        for issue in self.issues:
            out.append(f"    {issue}")
        out.append(f"  suspicious:   {len(self.suspicious) or 'none'}")
        for r, c, ch, why in self.suspicious[:20]:
            out.append(f"    row {r + 1} col {c + 1}: {ch!r} ({why})")
        if len(self.suspicious) > 20:
            out.append(f"    ... {len(self.suspicious) - 20} more")
        return "\n".join(out)


def inspect(
    canvas: str,
    *,
    expected_width: Optional[int] = None,
    expected_height: Optional[int] = None,
    **kw,
) -> InspectReport:
    """Comprehensive diagnostic report for a canvas."""
    text_lines = canvas.splitlines() or [""]
    widths = [display_width(line, **kw) for line in text_lines]
    issues = validate(canvas, **kw)
    suspicious: List[Tuple[int, int, str, str]] = []
    for i, line in enumerate(text_lines):
        for j, ch in enumerate(line):
            cw = cell_width(ch, **kw)
            cat = unicodedata.category(ch)
            cp = ord(ch)
            if cw == 2:
                suspicious.append((i, j, ch, f"double-width U+{cp:04X}"))
            elif cat in ("Mn", "Me"):
                suspicious.append((i, j, ch, f"combining mark U+{cp:04X}"))
            elif cp < 0x20 and ch != "\t":
                suspicious.append((i, j, ch, f"control U+{cp:04X}"))
    rect = len(set(widths)) <= 1
    fit_ok: Optional[bool] = None
    if expected_width is not None or expected_height is not None:
        ew = expected_width if expected_width is not None else 10**9
        eh = expected_height if expected_height is not None else 10**9
        fit_ok = fits_in(canvas, ew, eh, **kw).ok
    return InspectReport(
        lines=len(text_lines),
        max_width=max(widths) if widths else 0,
        min_width=min(widths) if widths else 0,
        rectangular=rect,
        issues=issues,
        suspicious=suspicious,
        expected_width=expected_width,
        expected_height=expected_height,
        fit_ok=fit_ok,
    )


def annotate_widths(canvas: str, **kw) -> str:
    """Return canvas with a digit row under each line showing per-cell widths.

    Double-width cells render as `2 ` (digit then space) so the annotation
    row stays aligned with the original. Combining marks contribute nothing
    to the annotation since they occupy zero cells.
    """
    lines = canvas.splitlines() or [""]
    out: List[str] = []
    for line in lines:
        out.append(line)
        digits: List[str] = []
        for ch in line:
            cw = cell_width(ch, **kw)
            if cw == 0:
                continue
            if cw == 1:
                digits.append("1")
            elif cw == 2:
                digits.append("2 ")
            else:
                digits.append(str(cw))
        out.append("".join(digits))
    return "\n".join(out)


# ===========================================================================
# Section 9: Misc
# ===========================================================================

def ascii_fallback(canvas: str, *, mapping: Optional[Dict[str, str]] = None) -> str:
    """Substitute closest ASCII for known box/arrow/block glyphs."""
    table_map = dict(ASCII_FALLBACK_DEFAULT)
    if mapping:
        table_map.update(mapping)
    return "".join(table_map.get(ch, ch) for ch in canvas)


def strip_ansi(text: str) -> str:
    """Remove ANSI CSI escape sequences."""
    return ANSI_RE.sub("", text)


# ===========================================================================
# CLI
# ===========================================================================

def _read_input(text_arg: Optional[str]) -> str:
    if text_arg is None or text_arg == "-":
        return sys.stdin.read()
    return text_arg


def _trbl_from_arg(s: str) -> Tuple[bool, bool, bool, bool]:
    if len(s) != 4 or any(c not in "01" for c in s):
        raise argparse.ArgumentTypeError(
            "TRBL must be exactly 4 binary digits (top right bottom left), e.g. 1101"
        )
    return tuple(c == "1" for c in s)  # type: ignore[return-value]


def _parse_char(s: str) -> str:
    if not s:
        return ""
    if s.upper().startswith("U+"):
        try:
            return chr(int(s[2:], 16))
        except ValueError as e:
            raise SystemExit(f"glyph.py: invalid codepoint {s!r}: {e}")
    return s


def _width_kw(args: argparse.Namespace) -> Dict[str, object]:
    return {
        "emoji_wide": not getattr(args, "no_emoji_wide", False),
        "tab_width": getattr(args, "tab_width", 0),
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="glyph.py",
        description="Unicode canvas helpers for the glyph-canvas skill.",
    )
    p.add_argument("--version", action="version", version=f"glyph.py {VERSION}")
    sub = p.add_subparsers(dest="cmd", metavar="SUBCOMMAND")
    sub.required = True

    def add_text(sp: argparse.ArgumentParser, name: str = "text") -> None:
        sp.add_argument(
            name, nargs="?", default=None,
            help="text (or '-' for stdin; default: stdin)",
        )
        sp.add_argument(
            "--no-emoji-wide", action="store_true",
            help="treat emoji as width 1 (skip the emoji wide-range table)",
        )
        sp.add_argument(
            "--tab-width", type=int, default=0,
            help="cell width assigned to TAB (default 0)",
        )

    sw = sub.add_parser("width", help="display width of TEXT")
    add_text(sw)

    sh = sub.add_parser("height", help="number of lines in TEXT")
    add_text(sh)

    sc = sub.add_parser("check", help="validate a canvas; exit 1 if issues")
    add_text(sc)
    sc.add_argument("--allow-tabs", action="store_true")
    sc.add_argument("--allow-ansi", action="store_true")
    sc.add_argument("--no-double-width", action="store_true",
                    help="flag double-width cells as issues")
    sc.add_argument("--no-combining", action="store_true",
                    help="flag combining marks as issues")
    sc.add_argument("--json", action="store_true")

    sp_pad = sub.add_parser("pad", help="pad rows to uniform width")
    add_text(sp_pad)
    sp_pad.add_argument("--width", type=int, default=None,
                        help="target width (default: canvas max)")
    sp_pad.add_argument("--fill", default=" ", help="fill char (default: space)")
    sp_pad.add_argument("--align", choices=("left", "center", "right"),
                        default="left")

    sf = sub.add_parser("fit", help="check whether canvas fits in MAX_W x MAX_H")
    sf.add_argument("max_w", type=int)
    sf.add_argument("max_h", type=int)
    add_text(sf)
    sf.add_argument("--json", action="store_true")

    si = sub.add_parser("inspect", help="detailed canvas diagnostics")
    add_text(si)
    si.add_argument("--expected-width", type=int, default=None)
    si.add_argument("--expected-height", type=int, default=None)
    si.add_argument("--json", action="store_true")

    sa = sub.add_parser("annotate", help="annotate per-cell widths under each row")
    add_text(sa)

    scl = sub.add_parser("classify", help="classify a single character")
    scl.add_argument("char", help="character (or codepoint like U+2500)")

    sj = sub.add_parser("junction", help="box junction glyph for a TRBL mask")
    sj.add_argument("trbl", type=_trbl_from_arg,
                    help="4 binary digits: top right bottom left (e.g. 1101)")
    sj.add_argument("--style", choices=VALID_STYLES, default="single")

    sb = sub.add_parser("box", help="render an empty box")
    sb.add_argument("width", type=int)
    sb.add_argument("height", type=int)
    sb.add_argument("--style", choices=VALID_STYLES, default="single")
    sb.add_argument("--title", default=None)
    sb.add_argument("--title-align", choices=("left", "center", "right"),
                    default="center")
    sb.add_argument("--fill", default=" ")

    ssh = sub.add_parser("shade", help="single shade glyph for intensity in [0,1]")
    ssh.add_argument("intensity", type=float)
    ssh.add_argument("--palette", default=" ░▒▓█")

    sh_b = sub.add_parser("hbar", help="horizontal bar")
    sh_b.add_argument("value", type=float)
    sh_b.add_argument("max", type=float)
    sh_b.add_argument("width", type=int)
    sh_b.add_argument("--palette", default="█▉▊▋▌▍▎▏")
    sh_b.add_argument("--empty", default=" ")

    sv_b = sub.add_parser("vbar", help="vertical bar (multi-line)")
    sv_b.add_argument("value", type=float)
    sv_b.add_argument("max", type=float)
    sv_b.add_argument("height", type=int)
    sv_b.add_argument("--palette", default="▁▂▃▄▅▆▇█")
    sv_b.add_argument("--empty", default=" ")

    ssp = sub.add_parser("sparkline", help="sparkline of comma-separated values")
    ssp.add_argument("values", help="comma-separated numbers")
    ssp.add_argument("--palette", default="▁▂▃▄▅▆▇█")
    ssp.add_argument("--min", type=float, default=None)
    ssp.add_argument("--max", type=float, default=None)

    st = sub.add_parser(
        "table",
        help="render a table from stdin (one row per line, cells separated by --sep)",
    )
    add_text(st)
    st.add_argument("--headers", default=None, help="comma-separated header labels")
    st.add_argument("--style", choices=VALID_STYLES, default="single")
    st.add_argument(
        "--align", default="left",
        help="single value or comma list per column (left/center/right)",
    )
    st.add_argument("--padding", type=int, default=1)
    st.add_argument("--sep", default="|", help="cell separator in input (default: |)")

    sw_w = sub.add_parser("wrap", help="width-aware word wrap")
    sw_w.add_argument("width", type=int)
    add_text(sw_w)
    sw_w.add_argument("--no-break-long", action="store_true",
                      help="don't hard-break words longer than WIDTH")

    sce = sub.add_parser("center", help="center text in width (per line)")
    sce.add_argument("width", type=int)
    add_text(sce)
    sce.add_argument("--fill", default=" ")

    str_p = sub.add_parser("truncate", help="truncate text to width (per line)")
    str_p.add_argument("width", type=int)
    add_text(str_p)
    str_p.add_argument("--ellipsis", default=None)

    saf = sub.add_parser(
        "ascii-fallback",
        help="substitute closest ASCII for known box/arrow/block glyphs",
    )
    add_text(saf)

    sub.add_parser("selftest", help="run internal smoke tests")

    return p


def cmd_width(args: argparse.Namespace) -> int:
    text = _read_input(args.text)
    print(display_width(text, **_width_kw(args)))
    return 0


def cmd_height(args: argparse.Namespace) -> int:
    text = _read_input(args.text)
    print(len(text.splitlines()))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    text = _read_input(args.text)
    kw = _width_kw(args)
    issues = validate(
        text,
        allow_tabs=args.allow_tabs,
        allow_ansi=args.allow_ansi,
        allow_double_width=not args.no_double_width,
        allow_combining=not args.no_combining,
        **kw,
    )
    if args.json:
        print(json.dumps(
            {"ok": not issues, "issues": [i.to_dict() for i in issues]},
            ensure_ascii=False, indent=2,
        ))
    else:
        if not issues:
            print("OK")
        else:
            print(f"{len(issues)} issue(s):")
            for issue in issues:
                print(f"  {issue}")
    return 0 if not issues else 1


def cmd_pad(args: argparse.Namespace) -> int:
    text = _read_input(args.text)
    out = pad_canvas(
        text, width=args.width, fill=args.fill, align=args.align,
        **_width_kw(args),
    )
    sys.stdout.write(out)
    if not out.endswith("\n"):
        sys.stdout.write("\n")
    return 0


def cmd_fit(args: argparse.Namespace) -> int:
    text = _read_input(args.text)
    result = fits_in(text, args.max_w, args.max_h, **_width_kw(args))
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(str(result))
    return 0 if result.ok else 1


def cmd_inspect(args: argparse.Namespace) -> int:
    text = _read_input(args.text)
    report = inspect(
        text,
        expected_width=args.expected_width,
        expected_height=args.expected_height,
        **_width_kw(args),
    )
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(str(report))
    fit_pass = report.fit_ok in (None, True)
    return 0 if not report.issues and fit_pass else 1


def cmd_annotate(args: argparse.Namespace) -> int:
    text = _read_input(args.text)
    print(annotate_widths(text, **_width_kw(args)))
    return 0


def cmd_classify(args: argparse.Namespace) -> int:
    ch = _parse_char(args.char)
    if not ch:
        raise SystemExit("glyph.py: empty character")
    c = ch[0]
    cp = ord(c)
    try:
        name = unicodedata.name(c)
    except ValueError:
        name = "<no name>"
    print(f"char:        {c!r}")
    print(f"codepoint:   U+{cp:04X}")
    print(f"name:        {name}")
    print(f"category:    {unicodedata.category(c)}")
    print(f"east_asian:  {unicodedata.east_asian_width(c)}")
    print(f"cell_width:  {cell_width(c)}")
    print(f"class:       {classify(c)}")
    return 0


def cmd_junction(args: argparse.Namespace) -> int:
    t, r, b, l = args.trbl
    print(junction(t, r, b, l, style=args.style))
    return 0


def cmd_box(args: argparse.Namespace) -> int:
    print(box(
        args.width, args.height,
        style=args.style, title=args.title,
        title_align=args.title_align, fill=args.fill,
    ))
    return 0


def cmd_shade(args: argparse.Namespace) -> int:
    print(shade(args.intensity, palette=args.palette))
    return 0


def cmd_hbar(args: argparse.Namespace) -> int:
    print(hbar(
        args.value, args.max, args.width,
        palette=args.palette, empty=args.empty,
    ))
    return 0


def cmd_vbar(args: argparse.Namespace) -> int:
    for line in vbar(
        args.value, args.max, args.height,
        palette=args.palette, empty=args.empty,
    ):
        print(line)
    return 0


def cmd_sparkline(args: argparse.Namespace) -> int:
    try:
        values = [float(v) for v in args.values.split(",") if v.strip()]
    except ValueError as e:
        raise SystemExit(f"glyph.py: invalid value: {e}")
    print(sparkline(
        values, palette=args.palette,
        min_value=args.min, max_value=args.max,
    ))
    return 0


def cmd_table(args: argparse.Namespace) -> int:
    text = _read_input(args.text)
    sep = args.sep
    rows: List[List[str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        cells = line.split(sep)
        rows.append([c.strip() for c in cells])
    headers = (
        [h.strip() for h in args.headers.split(",")] if args.headers else None
    )
    if "," in args.align:
        align: Union[str, List[str]] = [a.strip() for a in args.align.split(",")]
    else:
        align = args.align
    print(table(
        rows, headers=headers, style=args.style,
        align=align, padding=args.padding, **_width_kw(args),
    ))
    return 0


def cmd_wrap(args: argparse.Namespace) -> int:
    text = _read_input(args.text)
    for line in wrap(
        text, args.width,
        break_long=not args.no_break_long,
        **_width_kw(args),
    ):
        print(line)
    return 0


def cmd_center(args: argparse.Namespace) -> int:
    text = _read_input(args.text)
    out_lines = [
        center(line, args.width, fill=args.fill, **_width_kw(args))
        for line in (text.splitlines() or [text])
    ]
    print("\n".join(out_lines))
    return 0


def cmd_truncate(args: argparse.Namespace) -> int:
    text = _read_input(args.text)
    out_lines = [
        truncate(line, args.width, ellipsis=args.ellipsis, **_width_kw(args))
        for line in (text.splitlines() or [text])
    ]
    print("\n".join(out_lines))
    return 0


def cmd_ascii_fallback(args: argparse.Namespace) -> int:
    text = _read_input(args.text)
    sys.stdout.write(ascii_fallback(text))
    return 0


def cmd_selftest(args: argparse.Namespace) -> int:
    failed: List[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        if not cond:
            failed.append(f"{name}: {detail}" if detail else name)

    check("ascii width", display_width("hello") == 5)
    check("cjk width", display_width("你好") == 4)
    check("emoji width", display_width("🎉") == 2)
    check("combining width", cell_width("\u0301") == 0)
    check("tab default zero", cell_width("\t") == 0)
    check("tab override", cell_width("\t", tab_width=4) == 4)

    check("rectangular yes", is_rectangular("abc\ndef"))
    check("rectangular no", not is_rectangular("abc\nde"))

    check("pad left",   pad_row("hi", 5, align="left")   == "hi   ")
    check("pad right",  pad_row("hi", 5, align="right")  == "   hi")
    check("pad center", pad_row("hi", 5, align="center") == " hi  ")
    check("pad noop",   pad_row("hello", 3) == "hello")

    check("truncate fit",      truncate("hello", 10) == "hello")
    check("truncate plain",    truncate("hello world", 5) == "hello")
    check("truncate ellipsis", display_width(truncate("hello world", 7, ellipsis="…")) == 7)
    check("truncate cjk safe", display_width(truncate("你好世界", 3)) <= 3)

    check("junction h",       junction(False, True, False, True, style="single") == "─")
    check("junction v",       junction(True, False, True, False, style="single") == "│")
    check("junction tl",      junction(False, True, True, False, style="single") == "┌")
    check("junction tl dbl",  junction(False, True, True, False, style="double") == "╔")
    check("junction tl rnd",  junction(False, True, True, False, style="rounded") == "╭")
    check("junction tl thk",  junction(False, True, True, False, style="thick") == "┏")
    check("junction tl ascii",junction(False, True, True, False, style="ascii") == "+")
    check("junction cross",   junction(True, True, True, True, style="single") == "┼")
    check("junction cross dbl",junction(True, True, True, True, style="double") == "╬")
    check("junction empty",   junction(False, False, False, False, style="single") == " ")

    check("shade min", shade(0.0) == " ")
    check("shade max", shade(1.0) == "█")
    check("shade mid", shade(0.5) in "░▒▓")

    check("hbar full",     hbar(1, 1, 4) == "████")
    check("hbar empty",    hbar(0, 1, 4) == "    ")
    check("hbar half",     hbar(0.5, 1, 4) == "██  ")
    check("hbar fraction", display_width(hbar(0.625, 1, 4)) == 4)

    vb = vbar(0.5, 1, 4)
    check("vbar len", len(vb) == 4)
    check("vbar half full", vb[2] == "█" and vb[3] == "█")
    check("vbar half empty", vb[0] == " " and vb[1] == " ")

    check("sparkline len", len(sparkline([1, 2, 3, 4, 5])) == 5)
    check("sparkline flat", sparkline([3, 3, 3]) == "▁▁▁")

    box_5x3 = box(5, 3, style="single")
    check("box single 5x3", box_5x3.splitlines() == ["┌───┐", "│   │", "└───┘"])
    box_ascii = box(5, 3, style="ascii")
    check("box ascii 5x3", box_ascii.splitlines() == ["+---+", "|   |", "+---+"])
    box_titled = box(11, 3, style="single", title="HI", title_align="center")
    check("box title center", box_titled.splitlines()[0] == "┌── HI ───┐")

    fit_ok = fits_in("abc\ndef", 10, 10)
    check("fit ok", fit_ok.ok)
    fit_bad = fits_in("abc\ndef", 2, 10)
    check("fit overflow w", not fit_bad.ok and fit_bad.overflow_w == 1)
    fit_h = fits_in("a\nb\nc", 5, 2)
    check("fit overflow h", not fit_h.ok and fit_h.overflow_h == 1)

    tbl = table([["a", "b"], ["c", "d"]], headers=["X", "Y"])
    check("table contains border", "─" in tbl)
    check("table contains header", "X" in tbl)

    issues = validate("a\tb")
    check("validate tab", any(i.kind == "tab" for i in issues))
    issues_r = validate("abc\ndefgh")
    check("validate ragged", any(i.kind == "ragged" for i in issues_r))
    issues_ansi = validate("\x1b[31mhi\x1b[0m")
    check("validate ansi", any(i.kind == "ansi" for i in issues_ansi))

    check("classify box",   classify("┌") == "box_drawing")
    check("classify block", classify("█") == "block")
    check("classify arrow", classify("→") == "arrow")
    check("classify ascii", classify("a") == "ascii")
    check("classify wide",  classify("你") == "wide")

    ann = annotate_widths("你hi")
    check("annotate widths", display_width(ann.splitlines()[1]) == display_width("你hi"))

    check("strip ansi",      strip_ansi("\x1b[31mhi\x1b[0m") == "hi")
    check("ascii fallback",  ascii_fallback("┌─┐") == "+-+")

    bw = bounding_box("abc  \ndef\n   \n")
    check("bounding box", bw == (2, 3))

    wrapped = wrap("the quick brown fox", 10)
    check("wrap simple", all(display_width(l) <= 10 for l in wrapped))

    centered = center("hi", 6)
    check("center", display_width(centered) == 6)

    cols = columns(["a", "b", "c", "d"], 10, gutter=2)
    check("columns nonempty", bool(cols))

    if failed:
        print(f"FAIL: {len(failed)} test(s)")
        for f in failed:
            print(f"  - {f}")
        return 1
    print("OK: selftest assertions passed")
    return 0


COMMANDS = {
    "width": cmd_width,
    "height": cmd_height,
    "check": cmd_check,
    "pad": cmd_pad,
    "fit": cmd_fit,
    "inspect": cmd_inspect,
    "annotate": cmd_annotate,
    "classify": cmd_classify,
    "junction": cmd_junction,
    "box": cmd_box,
    "shade": cmd_shade,
    "hbar": cmd_hbar,
    "vbar": cmd_vbar,
    "sparkline": cmd_sparkline,
    "table": cmd_table,
    "wrap": cmd_wrap,
    "center": cmd_center,
    "truncate": cmd_truncate,
    "ascii-fallback": cmd_ascii_fallback,
    "selftest": cmd_selftest,
}


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    fn = COMMANDS[args.cmd]
    rc = fn(args)
    return rc if isinstance(rc, int) else 0


if __name__ == "__main__":
    sys.exit(main())
