#!/usr/bin/env python3
"""Validate stories/tracker.yaml, render stories/coverage.md and answer the coordinator's questions.

Part of the story-loop skill. `story-loop init` copies this file into the project as
stories/coverage.py so the project works without the skill installed.

Usage (run from anywhere inside the project, or pass --root):
  coverage.py [--root DIR] [check]                 validate the tracker and render stories/coverage.md
  coverage.py [--root DIR] models <id>             who coordinates / implements / verifies the story
  coverage.py [--root DIR] status                  one line per story; the last log line of the one in flight
  coverage.py [--root DIR] next                    the next eligible story, or why there is none
  coverage.py [--root DIR] show <id>               the story's brief (what an agent prompt needs)
  coverage.py [--root DIR] set <id> <field> <val>  status | commit | ticket; a line edit that keeps comments
  coverage.py [--root DIR] log <id> <text>         append a dated line to the story's log
  coverage.py [--root DIR] stale-reviews <id>      list stories/reviews/<key>-* newest last

`<id>` is the story id or its ticket key. `--models <id>` is accepted as an alias of `models`.
Exit code 1 on any validation error. Requires PyYAML (`pip install pyyaml`).

Tracker header, version 2 (version 1 trackers with top-level design/specs/jira_epic still work):

  version: 2
  project:
    design: [docs/DESIGN.md]
    specs: { kind: quint | manifest | none, dir: specs/, gate: scripts/check-specs.sh,
             ignore: { actions: [init, step], properties: [], witness_runs: [] } }
    branch: feature/XYZ-100
    ticket: { system: jira | github | linear | none, project: XYZ, epic: XYZ-100 }
    commit: { footer: Refs }
    build: { full: "mvn -B verify", scoped: "mvn -B -pl {modules} -amd verify" }
    local_only: true
    max_rounds: 3
  models:
    allowed: [opus, sonnet, haiku, fable]
    default: { coordinator: opus, implementer: opus, verifier: opus }
    phases: { 3: { implementer: sonnet } }
  stories: [...]
"""
from __future__ import annotations

import datetime as _dt
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("error: PyYAML is required: pip install pyyaml  (or: uv pip install pyyaml)")

STATUSES = ("todo", "in_progress", "in_review", "awaiting_commit", "blocked", "done")
IN_FLIGHT = ("in_progress", "in_review", "awaiting_commit")
MODEL_ROLES = ("coordinator", "implementer", "verifier")
DEFAULT_MODEL_NAMES = ("opus", "sonnet", "haiku", "fable")  # Claude Code's Agent tool names
KINDS = ("actions", "properties", "witness_runs")

# Quint: top-level members of the behaviour module (two-space indent); instance modules are capitalised.
DEF_RE = re.compile(r"^  (action|val|run)\s+([A-Za-z_][A-Za-z0-9_]*)", re.M)
MODULE_RE = re.compile(r"^module\s+([a-z][A-Za-z0-9_]*)\s*\{", re.M)
INSTANCE_RE = re.compile(r"^module\s+[A-Z]", re.M)


# --------------------------------------------------------------------------- config

@dataclass
class Config:
    version: int
    root: Path
    design: list[str]
    specs_kind: str                       # quint | manifest | none
    specs_dir: Path | None
    specs_gate: str | None
    ignore: dict[str, set[str]]
    branch: str | None
    ticket: dict
    commit: dict
    build: dict
    local_only: bool
    max_rounds: int
    model_names: tuple[str, ...]
    project_name: str | None = None
    extra: dict = field(default_factory=dict)


def _ignore_lists(block: dict | None, version: int) -> dict[str, set[str]]:
    aliases = {"actions": "actions", "vals": "properties", "properties": "properties",
               "runs": "witness_runs", "witness_runs": "witness_runs"}
    out: dict[str, set[str]] = {k: set() for k in KINDS}
    if version >= 2 or block is None:
        out["actions"] |= {"init", "step"}  # universal Quint plumbing
    for key, names in (block or {}).items():
        kind = aliases.get(key)
        if kind:
            out[kind] |= set(names or [])
    return out


def load_config(tracker: dict, root: Path) -> Config:
    version = int(tracker.get("version") or 1)
    project = tracker.get("project") or {}
    models = tracker.get("models") or {}
    allowed = tuple(models.get("allowed") or DEFAULT_MODEL_NAMES)

    if version >= 2 or project:
        design = project.get("design") or []
        if isinstance(design, str):
            design = [design]
        specs = project.get("specs") or {}
        if isinstance(specs, str):
            specs = {"dir": specs}
        kind = specs.get("kind")
        specs_dir = root / specs["dir"] if specs.get("dir") else None
        if not kind:
            kind = "quint" if specs_dir and list(specs_dir.glob("*.qnt")) else "none"
        ignore = _ignore_lists(specs.get("ignore"), version)
        return Config(
            version=version, root=root, design=design, specs_kind=kind, specs_dir=specs_dir,
            specs_gate=specs.get("gate"), ignore=ignore, branch=project.get("branch"),
            ticket=project.get("ticket") or {}, commit=project.get("commit") or {},
            build=project.get("build") or {}, local_only=bool(project.get("local_only", False)),
            max_rounds=int(project.get("max_rounds") or 3), model_names=allowed,
            project_name=project.get("name"),
        )

    # version 1: top-level design / specs / jira_epic, ignore lists optional under specs_ignore
    design = tracker.get("design") or []
    if isinstance(design, str):
        design = [design]
    specs_dir = root / (tracker.get("specs") or "specs/")
    kind = "quint" if specs_dir.exists() and list(specs_dir.glob("*.qnt")) else "none"
    ignore = _ignore_lists(tracker.get("specs_ignore"), 1)
    return Config(
        version=1, root=root, design=design, specs_kind=kind, specs_dir=specs_dir,
        specs_gate="scripts/check-specs.sh", ignore=ignore, branch=None,
        ticket={"system": "jira", "epic": tracker.get("jira_epic")}, commit={"footer": "Refs"},
        build={}, local_only=True, max_rounds=3, model_names=allowed,
    )


# --------------------------------------------------------------------------- specs

def load_specs(cfg: Config) -> tuple[dict[str, dict[str, list[str]]], dict[str, str]]:
    """Return ({module: {actions, properties, witness_runs}}, {module: label})."""
    specs: dict[str, dict[str, list[str]]] = {}
    labels: dict[str, str] = {}
    if cfg.specs_kind == "none" or cfg.specs_dir is None:
        return specs, labels
    if cfg.specs_kind == "quint":
        for path in sorted(cfg.specs_dir.glob("*.qnt")):
            text = path.read_text()
            modules = MODULE_RE.findall(text)
            if not modules:
                continue
            module = modules[0]  # the behaviour module; instance modules are capitalised
            instance = INSTANCE_RE.search(text)
            body = text[: instance.start()] if instance else text
            defs = {k: [] for k in KINDS}
            for kind, name in DEF_RE.findall(body):
                target = {"action": "actions", "val": "properties", "run": "witness_runs"}[kind]
                if name not in cfg.ignore[target]:
                    defs[target].append(name)
            specs[module] = defs
            labels[module] = str(path.relative_to(cfg.root))
        return specs, labels
    if cfg.specs_kind == "manifest":
        index = cfg.specs_dir / "index.yaml"
        if not index.exists():
            sys.exit(f"error: specs kind is manifest but {index.relative_to(cfg.root)} does not exist")
        manifest = yaml.safe_load(index.read_text()) or {}
        for module, entry in (manifest.get("modules") or {}).items():
            entry = entry or {}
            specs[module] = {k: [n for n in (entry.get(k) or []) if n not in cfg.ignore[k]] for k in KINDS}
            labels[module] = entry.get("file") or f"{cfg.specs_dir.relative_to(cfg.root)}/{module}"
        return specs, labels
    sys.exit(f"error: unknown specs kind '{cfg.specs_kind}' (quint | manifest | none)")


# --------------------------------------------------------------------------- helpers

def ticket_of(story: dict) -> str | None:
    return story.get("ticket") or story.get("jira")


def natural(s: str) -> list:
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


def resolve_models(tracker: dict, story: dict) -> dict[str, str]:
    """story.models > models.phases[phase] > models.default, per role."""
    models = tracker.get("models") or {}
    phase = (models.get("phases") or {}).get(story.get("phase")) or {}
    resolved = {}
    for role in MODEL_ROLES:
        resolved[role] = (story.get("models") or {}).get(role) or phase.get(role) or (models.get("default") or {}).get(role) or "-"
    return resolved


def find_story(stories: list[dict], key: str) -> dict | None:
    for s in stories:
        if s.get("id") == key or ticket_of(s) == key:
            return s
    return None


def blocking_deps(story: dict, by_id: dict[str, dict]) -> list[str]:
    return [d for d in story.get("depends_on") or [] if d not in by_id or by_id[d].get("status") != "done"]


# --------------------------------------------------------------------------- validation

def check_models(tracker: dict, stories: list[dict], names: tuple[str, ...], errors: list[str]) -> None:
    models = tracker.get("models") or {}
    blocks = [("models.default", models.get("default") or {})]
    for phase, block in (models.get("phases") or {}).items():
        blocks.append((f"models.phases.{phase}", block or {}))
    for s in stories:
        if s.get("models"):
            blocks.append((f"{s['id']}.models", s["models"]))
    for where, block in blocks:
        for role, name in block.items():
            if role not in MODEL_ROLES:
                errors.append(f"{where}: unknown role '{role}' (one of {', '.join(MODEL_ROLES)})")
            if name not in names:
                errors.append(f"{where}.{role}: unknown model '{name}' (one of {', '.join(names)})")


def validate(tracker: dict, cfg: Config, specs: dict) -> tuple[list[str], list[str], dict]:
    """Return (errors, warnings, refs) where refs maps (module, kind, name) -> [story ids]."""
    stories = tracker.get("stories") or []
    errors: list[str] = []
    warnings: list[str] = []
    check_models(tracker, stories, cfg.model_names, errors)
    if cfg.specs_kind not in ("quint", "manifest", "none"):
        errors.append(f"project.specs.kind: unknown kind '{cfg.specs_kind}'")

    in_flight = [s["id"] for s in stories if s.get("status") in IN_FLIGHT]
    if len(in_flight) > 1:
        errors.append("more than one story in flight: " + ", ".join(in_flight))
    for s in stories:
        if "id" not in s:
            errors.append("a story has no id")
            continue
        if s.get("status") not in STATUSES:
            errors.append(f"{s['id']}: unknown status '{s.get('status')}'")
        if s.get("status") == "done" and not s.get("commit"):
            errors.append(f"{s['id']}: done but no commit recorded")
        if not s.get("acceptance"):
            warnings.append(f"{s['id']}: no acceptance commands (the verifier has nothing to run)")

    ids = {s["id"] for s in stories if "id" in s}
    seen: set[str] = set()
    for s in stories:
        if s.get("id") in seen:
            errors.append(f"{s['id']}: duplicate story id")
        seen.add(s.get("id"))
    by_id = {s["id"]: s for s in stories if "id" in s}

    refs: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for s in stories:
        if "id" not in s:
            continue
        for dep in s.get("depends_on") or []:
            if dep not in ids:
                errors.append(f"{s['id']}: unknown dependency {dep}")
        spec = s.get("spec") or {}
        for kind in KINDS:
            for ref in spec.get(kind) or []:
                if cfg.specs_kind == "none":
                    errors.append(f"{s['id']}: spec reference '{ref}' but project.specs.kind is none")
                    continue
                if "." not in ref:
                    errors.append(f"{s['id']}: spec reference '{ref}' must be <module>.<name>")
                    continue
                module, name = ref.split(".", 1)
                if module not in specs:
                    errors.append(f"{s['id']}: unknown spec module '{module}' in '{ref}'")
                    continue
                if name not in specs[module][kind]:
                    errors.append(f"{s['id']}: '{name}' is not a {kind[:-1].replace('_', ' ')} in {module}")
                    continue
                refs[(module, kind, name)].append(s["id"])
        for module in spec.get("modules") or []:
            if module not in specs:
                errors.append(f"{s['id']}: unknown spec module '{module}'")

    state: dict[str, int] = {}

    def visit(node: str, path: list[str]) -> None:
        if state.get(node) == 1:
            errors.append("dependency cycle: " + " -> ".join(path + [node]))
            return
        if state.get(node) == 2:
            return
        state[node] = 1
        for dep in by_id[node].get("depends_on") or []:
            if dep in by_id:
                visit(dep, path + [node])
        state[node] = 2

    for sid in ids:
        visit(sid, [])
    return errors, warnings, refs


# --------------------------------------------------------------------------- rendering

def render(tracker: dict, cfg: Config, specs: dict, labels: dict, refs: dict) -> tuple[str, int]:
    stories = tracker.get("stories") or []
    by_id = {s["id"]: s for s in stories}
    lines: list[str] = []
    lines.append("# Spec coverage")
    lines.append("")
    if cfg.specs_kind == "quint":
        rel = str(cfg.specs_dir.relative_to(cfg.root)).rstrip("/")
        source = f"`stories/tracker.yaml` and `{rel}/*.qnt`"
    elif cfg.specs_kind == "manifest":
        rel = str(cfg.specs_dir.relative_to(cfg.root)).rstrip("/")
        source = f"`stories/tracker.yaml` and `{rel}/index.yaml`"
    else:
        source = "`stories/tracker.yaml`"
    lines.append(f"Generated by `python3 stories/coverage.py` from {source}. Do not edit by hand.")
    lines.append("")

    counts = defaultdict(int)
    for s in stories:
        counts[s["status"]] += 1
    lines.append("## Story status")
    lines.append("")
    lines.append("| Status | Count |")
    lines.append("| --- | --- |")
    for status in STATUSES:
        lines.append(f"| {status} | {counts.get(status, 0)} |")
    lines.append(f"| total | {len(stories)} |")
    lines.append("")

    def status_of(story_ids: list[str]) -> str:
        if not story_ids:
            return "unmapped"
        sts = {by_id[i]["status"] for i in story_ids}
        if sts == {"done"}:
            return "done"
        if sts & set(IN_FLIGHT):
            return "in progress"
        return "planned"

    unmapped_total = 0
    for module, defs in specs.items():
        lines.append(f"## {labels[module]}")
        lines.append("")
        for kind, title in (("actions", "Actions"), ("properties", "Properties"), ("witness_runs", "Witness runs")):
            lines.append(f"### {title}")
            lines.append("")
            lines.append("| Name | Stories | Status |")
            lines.append("| --- | --- | --- |")
            for name in defs[kind]:
                story_ids = refs.get((module, kind, name), [])
                st = status_of(story_ids)
                if st == "unmapped":
                    unmapped_total += 1
                lines.append(f"| `{name}` | {', '.join(story_ids) if story_ids else '-'} | {st} |")
            lines.append("")

    lines.append("## Stories by phase")
    lines.append("")
    lines.append("Models: who runs what for the story, resolved from the tracker's `models` block (coordinator / implementer / verifier).")
    lines.append("")
    lines.append("| Id | Title | Status | Depends on | Spec modules | Models |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for s in stories:
        mods = ", ".join((s.get("spec") or {}).get("modules") or []) or "-"
        deps = ", ".join(s.get("depends_on") or []) or "-"
        m = resolve_models(tracker, s)
        who = f"{m['coordinator']} / {m['implementer']} / {m['verifier']}"
        lines.append(f"| {s['id']} | {s['title']} | {s['status']} | {deps} | {mods} | {who} |")
    lines.append("")
    if cfg.specs_kind == "none":
        lines.append("No spec adapter is configured (`project.specs.kind: none`); stories carry no spec mapping.")
    elif cfg.version == 1:
        lines.append(f"Unmapped spec definitions: {unmapped_total}. Every unmapped action or property is either plumbing to add to the ignore lists in coverage.py or a missing story.")
    else:
        lines.append(f"Unmapped spec definitions: {unmapped_total}. Every unmapped action or property is either plumbing to add to `project.specs.ignore` in the tracker header or a missing story.")
    lines.append("")
    return "\n".join(lines), unmapped_total


# --------------------------------------------------------------------------- loading

def find_root(explicit: str | None) -> Path:
    if explicit:
        root = Path(explicit).resolve()
        if not (root / "stories" / "tracker.yaml").exists():
            sys.exit(f"error: {root}/stories/tracker.yaml does not exist")
        return root
    env = os.environ.get("STORY_LOOP_ROOT")
    if env:
        return find_root(env)
    here = Path(__file__).resolve().parent
    if here.name == "stories" and (here / "tracker.yaml").exists():
        return here.parent
    for d in [Path.cwd(), *Path.cwd().parents]:
        if (d / "stories" / "tracker.yaml").exists():
            return d
    sys.exit("error: no stories/tracker.yaml found above the current directory; pass --root <project> or set STORY_LOOP_ROOT")


class Project:
    def __init__(self, root: Path):
        self.root = root
        self.tracker_path = root / "stories" / "tracker.yaml"
        self.out = root / "stories" / "coverage.md"
        self.reload()

    def reload(self) -> None:
        self.text = self.tracker_path.read_text()
        try:
            self.tracker = yaml.safe_load(self.text) or {}
        except yaml.YAMLError as e:
            sys.exit(f"error: {self.tracker_path.relative_to(self.root)} is not valid YAML: {e}")
        self.cfg = load_config(self.tracker, self.root)
        self.stories: list[dict] = self.tracker.get("stories") or []
        self.by_id = {s["id"]: s for s in self.stories if "id" in s}
        self.specs, self.labels = load_specs(self.cfg)

    def check(self, write: bool = True, quiet: bool = False) -> int:
        errors, warnings, refs = validate(self.tracker, self.cfg, self.specs)
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)
        if errors:
            for e in errors:
                print(f"error: {e}", file=sys.stderr)
            print(f"{len(errors)} error(s); coverage.md not written", file=sys.stderr)
            return 1
        if write:
            text, unmapped = render(self.tracker, self.cfg, self.specs, self.labels, refs)
            self.out.write_text(text)
            if not quiet:
                print(f"wrote {self.out.relative_to(self.root)}; {len(self.stories)} stories; {unmapped} unmapped spec definitions")
        return 0

    def story(self, key: str) -> dict:
        s = find_story(self.stories, key)
        if s is None:
            sys.exit(f"error: no story {key}")
        return s


# --------------------------------------------------------------------------- read-only commands

def cmd_models(p: Project, key: str) -> int:
    for role, name in resolve_models(p.tracker, p.story(key)).items():
        print(f"{role}: {name}")
    return 0


def cmd_status(p: Project) -> int:
    rows = []
    for s in p.stories:
        blocked = blocking_deps(s, p.by_id)
        rows.append((s["id"], ticket_of(s) or "-", s.get("status", "?"), ", ".join(blocked) or "-", s.get("title", "")))
    widths = [max(len(r[i]) for r in rows + [("id", "ticket", "status", "blocked by", "title")]) for i in range(4)]
    print(f"{'id':<{widths[0]}}  {'ticket':<{widths[1]}}  {'status':<{widths[2]}}  {'blocked by':<{widths[3]}}  title")
    for r in rows:
        print(f"{r[0]:<{widths[0]}}  {r[1]:<{widths[1]}}  {r[2]:<{widths[2]}}  {r[3]:<{widths[3]}}  {r[4]}")
    counts = defaultdict(int)
    for s in p.stories:
        counts[s.get("status")] += 1
    print()
    print("counts: " + ", ".join(f"{st} {counts.get(st, 0)}" for st in STATUSES))
    for s in p.stories:
        if s.get("status") in IN_FLIGHT:
            log = s.get("log") or []
            print(f"in flight: {s['id']} ({ticket_of(s) or 'no ticket'}) {s.get('status')}")
            print(f"  last log: {log[-1] if log else '(no log)'}")
    if p.cfg.branch:
        print(f"branch: {p.cfg.branch}")
    return 0


def print_story(p: Project, s: dict, log_tail: int = 8) -> None:
    def seq(key: str, items) -> None:
        if not items:
            return
        print(f"{key}:")
        for it in items:
            text = str(it).strip().replace("\n", "\n    ")
            print(f"  - {text}")

    print(f"id: {s['id']}")
    print(f"ticket: {ticket_of(s) or '(none)'}")
    print(f"title: {s.get('title', '')}")
    if s.get("phase") is not None:
        print(f"phase: {s['phase']}")
    print(f"status: {s.get('status')}")
    if s.get("commit"):
        print(f"commit: {s['commit']}")
    deps = s.get("depends_on") or []
    print("depends_on: " + (", ".join(f"{d} ({p.by_id[d].get('status') if d in p.by_id else 'unknown'})" for d in deps) or "-"))
    seq("design", s.get("design"))
    if s.get("summary"):
        print("summary: |")
        for line in str(s["summary"]).strip().splitlines():
            print(f"  {line}")
    spec = s.get("spec") or {}
    if spec:
        print("spec:")
        for k in ("modules",) + KINDS:
            if spec.get(k):
                print(f"  {k}: [{', '.join(spec[k])}]")
        if spec.get("note"):
            print(f"  note: {str(spec['note']).strip()}")
    seq("acceptance", s.get("acceptance"))
    seq("prerequisites", s.get("prerequisites"))
    seq("carry", s.get("carry"))
    m = resolve_models(p.tracker, s)
    print("models: " + " ".join(f"{r}={m[r]}" for r in MODEL_ROLES))
    reviews = sorted((p.root / "stories" / "reviews").glob(f"{ticket_of(s) or s['id']}-*")) if (p.root / "stories" / "reviews").exists() else []
    if reviews:
        print("reviews: " + ", ".join(r.name for r in reviews))
    log = s.get("log") or []
    if log:
        print(f"log (last {min(log_tail, len(log))} of {len(log)}):")
        for line in log[-log_tail:]:
            print(f"  - {line}")


def cmd_show(p: Project, key: str) -> int:
    print_story(p, p.story(key))
    return 0


def cmd_next(p: Project) -> int:
    in_flight = [s for s in p.stories if s.get("status") in IN_FLIGHT]
    if in_flight:
        s = in_flight[0]
        print(f"in flight: {s['id']} ({ticket_of(s) or 'no ticket'}) is {s['status']}; finish or resume it first", file=sys.stderr)
        print_story(p, s)
        return 2
    eligible = [s for s in p.stories if s.get("status") == "todo" and not blocking_deps(s, p.by_id)]
    if eligible:
        s = min(eligible, key=lambda x: natural(x["id"]))
        print_story(p, s)
        return 0
    todo = [s for s in p.stories if s.get("status") == "todo"]
    blocked = [s for s in p.stories if s.get("status") == "blocked"]
    if not todo and not blocked:
        print("nothing to do: every story is done")
        return 1
    print("no eligible story:", file=sys.stderr)
    for s in todo:
        print(f"  {s['id']} waits for {', '.join(blocking_deps(s, p.by_id))}", file=sys.stderr)
    for s in blocked:
        print(f"  {s['id']} is blocked: {(s.get('log') or ['(no log)'])[-1]}", file=sys.stderr)
    return 1


def cmd_reviews(p: Project, key: str) -> int:
    s = p.story(key)
    d = p.root / "stories" / "reviews"
    files = sorted(d.glob(f"{ticket_of(s) or s['id']}-*"), key=lambda f: natural(f.name)) if d.exists() else []
    for f in files:
        print(f.relative_to(p.root))
    return 0 if files else 1


# --------------------------------------------------------------------------- line edits

def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def story_block(lines: list[str], key: str) -> tuple[int, int, int]:
    """Return (start, end, indent) of the story whose `- id:` matches key; end is exclusive."""
    start = -1
    ind = 0
    for i, line in enumerate(lines):
        m = re.match(r"^(\s*)- id:\s*([^\s#]+)", line)
        if m and m.group(2).strip("'\"") == key:
            start, ind = i, len(m.group(1))
            break
    if start < 0:
        sys.exit(f"error: no story block with id {key} in the tracker text")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        line = lines[j]
        if not line.strip():
            continue
        if _indent(line) <= ind and not (line.lstrip().startswith("#") and _indent(line) > ind):
            end = j
            break
    # trim trailing blank lines and section-banner comments at indent <= ind
    while end > start + 1 and (not lines[end - 1].strip() or (_indent(lines[end - 1]) <= ind and lines[end - 1].lstrip().startswith("#"))):
        end -= 1
    return start, end, ind


def yaml_scalar(text: str) -> str:
    if re.search(r"""(: |^\s*[-?:,\[\]{}#&*!|>'"%@`]| #|:$|^\s|\s$)""", text) or text.lower() in ("", "null", "true", "false", "yes", "no", "~"):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def _write_checked(p: Project, new_lines: list[str], what: str) -> int:
    new_text = "\n".join(new_lines)
    if p.text.endswith("\n") and not new_text.endswith("\n"):
        new_text += "\n"
    try:
        yaml.safe_load(new_text)
    except yaml.YAMLError as e:
        print(f"error: the edit would make the tracker invalid YAML; nothing written: {e}", file=sys.stderr)
        return 1
    p.tracker_path.write_text(new_text)
    print(what)
    p.reload()
    return p.check(write=True, quiet=True)


def cmd_set(p: Project, key: str, fld: str, value: str, force: bool = False) -> int:
    s = p.story(key)
    if fld == "jira":
        fld = "ticket" if "jira" not in s else "jira"
    if fld not in ("status", "commit", "ticket", "jira"):
        sys.exit("error: set supports status | commit | ticket")
    if fld == "status":
        if value not in STATUSES:
            sys.exit(f"error: unknown status '{value}' (one of {', '.join(STATUSES)})")
        if value in IN_FLIGHT and not force:
            others = [o["id"] for o in p.stories if o is not s and o.get("status") in IN_FLIGHT]
            if others:
                sys.exit(f"error: {', '.join(others)} already in flight; finish it first (or --force)")
    if fld == "ticket" and "jira" in s:
        fld = "jira"
    lines = p.text.split("\n")
    start, end, ind = story_block(lines, s["id"])
    fi = ind + 2
    pat = re.compile(rf"^(\s{{{fi}}}{re.escape(fld)}:\s*)([^#]*?)(\s*#.*)?$")
    for i in range(start, end):
        m = pat.match(lines[i])
        if m:
            lines[i] = f"{m.group(1)}{yaml_scalar(value)}{m.group(3) or ''}"
            return _write_checked(p, lines, f"{s['id']}: {fld} = {value}")
    # insert after the last of the leading fields that exists
    order = ["id", "title", "jira", "ticket", "phase", "status", "commit"]
    pos = order.index(fld)
    insert_after = start
    for i in range(start, end):
        m = re.match(rf"^\s{{{fi}}}([a-z_]+):", lines[i])
        if m and m.group(1) in order[:pos]:
            insert_after = i
    lines.insert(insert_after + 1, f"{' ' * fi}{fld}: {yaml_scalar(value)}")
    return _write_checked(p, lines, f"{s['id']}: {fld} = {value} (field added)")


def cmd_log(p: Project, key: str, text: str) -> int:
    s = p.story(key)
    text = text.strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}\b", text):
        text = f"{_dt.date.today().isoformat()} {text}"
    lines = p.text.split("\n")
    start, end, ind = story_block(lines, s["id"])
    fi = ind + 2
    item = f"{' ' * (fi + 2)}- {yaml_scalar(text)}"
    log_line = -1
    for i in range(start, end):
        if re.match(rf"^\s{{{fi}}}log:", lines[i]):
            log_line = i
            break
    if log_line >= 0:
        m = re.match(r"^(\s*log:)\s*(\[\s*\])?\s*(#.*)?$", lines[log_line])
        if m is None:
            sys.exit(f"error: {s['id']}: `log:` holds an inline value; convert it to a block list first")
        if m.group(2):  # `log: []` -> block list
            lines[log_line] = m.group(1) + (f"   {m.group(3)}" if m.group(3) else "")
        last = log_line
        j = log_line + 1
        while j < end:
            if not lines[j].strip():
                j += 1
                continue
            if _indent(lines[j]) > fi:
                last = j
                j += 1
                continue
            break
        lines.insert(last + 1, item)
    else:
        last = start
        for i in range(start, end):
            if lines[i].strip() and _indent(lines[i]) >= fi:
                last = i
        lines.insert(last + 1, f"{' ' * fi}log:")
        lines.insert(last + 2, item)
    return _write_checked(p, lines, f"{s['id']}: log + {text}")


# --------------------------------------------------------------------------- main

USAGE = __doc__.split("Tracker header")[0]


def main(argv: list[str]) -> int:
    root_arg = None
    force = False
    args: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--root":
            root_arg = argv[i + 1]
            i += 2
            continue
        if a.startswith("--root="):
            root_arg = a.split("=", 1)[1]
        elif a == "--force":
            force = True
        elif a == "--models":
            args.append("models")
        elif a in ("-h", "--help"):
            print(USAGE)
            return 0
        else:
            args.append(a)
        i += 1
    p = Project(find_root(root_arg))
    cmd = args[0] if args else "check"
    rest = args[1:]
    try:
        if cmd == "check":
            return p.check()
        if cmd == "models" and len(rest) == 1:
            return cmd_models(p, rest[0])
        if cmd == "status":
            return cmd_status(p)
        if cmd == "next":
            return cmd_next(p)
        if cmd == "show" and len(rest) == 1:
            return cmd_show(p, rest[0])
        if cmd == "set" and len(rest) == 3:
            return cmd_set(p, rest[0], rest[1], rest[2], force)
        if cmd == "log" and len(rest) >= 2:
            return cmd_log(p, rest[0], " ".join(rest[1:]))
        if cmd in ("reviews", "stale-reviews") and len(rest) == 1:
            return cmd_reviews(p, rest[0])
    except BrokenPipeError:
        return 0
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
