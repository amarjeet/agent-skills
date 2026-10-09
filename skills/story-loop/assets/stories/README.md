# Implementation process for {{PROJECT_NAME}}

This directory turns the design document (`{{DESIGN}}`) and the specs (kind `{{SPECS_KIND}}`) into
stories that agents implement and verify one at a time. The process is the `story-loop` skill's;
this file is the copy that travels with the project, so the loop also runs where the skill is
not installed.

| File | Purpose |
| --- | --- |
| `tracker.yaml` | The stories: dependencies, design sections, spec mapping, acceptance commands, status, log |
| `TEMPLATE.md` | Story fields and rules |
| `coverage.py` | Validates the tracker and its spec references, renders `coverage.md`, answers `status`, `next` and `show <id>`, and edits `status`, `commit`, `ticket` and `log` lines |
| `coverage.md` | Generated: which spec actions, properties and witness runs have a story, and story status |
| `reviews/` | Saved implementer and verifier reports per story and round |
| `agents/` | The implementer and verifier briefs; Claude Code reads the rendered copies in `.claude/agents/` |
| `harness/` | Snippets for `CLAUDE.local.md`, `AGENTS.md` and a Cursor rule |
| `change-requests/` | Optional: behaviour-level write-ups of work handed to another team |

## Sources of truth

1. **The design document** is the source of truth for structure, naming and technology choices.
   Stories name its sections in `design`.
2. **The specs** are the source of truth for interaction behaviour. Every behavioural story maps
   to spec actions (what it implements), properties (what it must keep true) and witness runs
   (the scenarios it reproduces as tests, under the same names). `coverage.md` shows what is
   still unmapped.
3. **New interaction behaviour is specified first.** A spec-first story precedes the
   implementation story. Spec-first and decision stories produce no commit and no ticket.
4. **The verifier reads the spec before the diff** and rejects behaviour that has no counterpart
   in a spec or the design.

## Local-only material (`local_only: {{LOCAL_ONLY}}`)

When `true`, `stories/`, the design document, the specs, the spec gate and the agent files stay in
each developer's checkout and are never pushed (listed in `.git/info/exclude`). Consequences:

- **No worktrees.** Agents read the ignored files in place, in this one checkout.
- **The spec gate runs locally, not in CI**, and only when it can fail: before a story starts and
  before it closes, when the story has a non-empty `spec` mapping or touches the specs. Other
  stories skip it and log `spec gate skipped: no spec mapping, specs untouched`.
  `python3 stories/coverage.py` still runs every time.
- **Fixtures the tests need are committed as plain test resources** (generated traces, data).
  Tests keep the witness-run names, which read well without the model.
- **New team members get the material from a colleague**, not from the remote.

When `false`, everything is committed like any other file and CI may run `coverage.py` and the gate.

## Branching, tickets and commits

- Epic branch `{{BRANCH}}`. One commit per story, only on the owner's explicit go-ahead for that
  commit. The owner raises one pull request at the end; the coordinator never merges or pushes.
- Commits: Conventional Commits subject with a scope and no ticket key, blank line,
  `Refs: <ticket>` footer, never an agent attribution line.
- Tickets (`{{TICKET_SYSTEM}}`, epic `{{EPIC}}`): every story that changes committed code gets a
  ticket under the epic before implementation. Draft it (user story, scope, acceptance checkboxes),
  show the owner, create it on approval, record the key in `ticket`, log it, then start.
- Outward-facing text (tickets, pull requests) is behaviour-level only: no internal story ids, no
  design or spec names, no module, class or artifact names.

## Story lifecycle

`todo` → `in_progress` (implementer running) → `in_review` (verifier running) →
`awaiting_commit` (verified, scoped build green, commit proposed) → `done` (committed, sha in
`commit`), or `blocked` (`max_rounds` failed verifications, a prerequisite missing, or an owner
decision needed). Only the coordinator edits `status`, `commit`, `ticket` and `log`.

## State lives on disk, never only in a session

- `tracker.yaml`: `status`, plus a `log` with one dated line per step, newest last.
- `reviews/<key>-impl-r<N>.md` and `reviews/<key>-verify-r<N>.md`: the full reports of each round,
  saved verbatim. Defect lists live here, so a fresh implementer can fix them without context.
- `carry` on a story: known gaps the story must close; verified like acceptance criteria.
- Git: uncommitted work is the working tree on the epic branch; every finished story is one commit.

No other handoff document is needed or kept.

## Resuming in a new session

Find the one story whose status is `in_progress`, `in_review` or `awaiting_commit` (the validator
allows at most one) and reconcile it with git:

| Tracker says | Git shows | Meaning | Action |
| --- | --- | --- | --- |
| nothing in flight | clean tree | idle | select the next story |
| nothing in flight | dirty tree | untracked work | stop and ask the owner; never discard |
| `in_progress` | clean tree | implementer never produced anything | restart implementation, round from `log` |
| `in_progress` | dirty tree | implementation interrupted | fresh implementer in `continue` mode, with `carry` and the latest `reviews/*-verify-*` defects |
| `in_review` | dirty tree | verification interrupted | fresh verifier (verifiers are stateless) |
| `awaiting_commit` | dirty tree | owner has not answered | re-run the scoped build, re-show the proposal, wait |
| `awaiting_commit` or `in_review` | HEAD has `Refs: <that ticket>`, clean tree | owner committed | record the sha, set `done`, log it |
| `blocked` | any | human needed | show the last `log` line and review file, stop |

## Who runs what

The `models` block in `tracker.yaml` names the model for each role: `coordinator` (the loop
session), `implementer` and `verifier` (the agents it spawns). Resolution per story:
the story's `models` > `models.phases.<phase>` > `models.default`.
`python3 stories/coverage.py models <id>` prints it. The log records the model of every round.

## Coordinator loop

1. **Resume check** (table above). `python3 stories/coverage.py` must pass. Spec gate only when in
   play. On the epic branch with a clean tree, pick `python3 stories/coverage.py next`.
2. **Ticket.** If the story changes code and has no `ticket`, draft it, wait for approval, create
   it, record the key, log it.
3. **Start.** `set <id> status in_progress`, log `started`.
4. **Implement.** Spawn the implementer brief (`agents/story-implementer.md`) with the story, the
   branch, the mode and the resolved model. Save its report verbatim to
   `reviews/<key>-impl-r<N>.md`; log `implement round N done (<model>)`.
5. **Verify.** `set <id> status in_review`, log it. Spawn a fresh verifier (`agents/story-verifier.md`)
   that shares no context with the implementer. Save its report to `reviews/<key>-verify-r<N>.md`;
   log the verdict with the model.
   - FAIL: `set <id> status in_progress`, send the defects to the implementer (`continue` mode,
     pointing at the review file), re-verify with a fresh verifier. After `max_rounds` FAILs set
     `blocked`, log why, stop.
   - PASS: continue. Lows and nits go to `carry` on the next related story or to the gap list
     below; they never start another round.
6. **Hand over, do not commit.** Run the builds and tests the story can affect, by blast radius
   (scoped: `{{BUILD_SCOPED}}`; full `{{BUILD_FULL}}` only when the change can reach everything;
   nothing the verifier already ran green on the same tree). Log what ran and why that scope
   covers the change. `set <id> status awaiting_commit`, log it. Show the owner: branch, diff stat,
   test and verifier evidence, how each `carry` item was closed, and the proposed commit message.
   Wait. A lint or static-analysis round the owner asks for here is another implement round; the
   story stays `awaiting_commit`.
7. **On go-ahead.** `git add -A --dry-run` lists no local-only path; commit on the epic branch;
   `set <id> commit <sha>`, `set <id> status done`, log `committed <sha>`; `coverage.py` regenerates
   `coverage.md`. Push only when separately asked.

Agents never edit `tracker.yaml`, the specs or the design unless the story is a spec-first or
decision story that says so.

## Known gaps without a story

Low findings from verifications that no story owns yet. Append here; promote to `carry` on the
next related story. Resolved entries say when and by which story.

- (none yet)

## Commands

```sh
python3 stories/coverage.py                 # validate the tracker, render coverage.md
python3 stories/coverage.py status          # every story, blockers, the one in flight
python3 stories/coverage.py next            # the next eligible story, or why there is none
python3 stories/coverage.py show <id>       # a story's brief (id or ticket key)
python3 stories/coverage.py models <id>     # who coordinates / implements / verifies it
python3 stories/coverage.py set <id> status in_progress
python3 stories/coverage.py log <id> "implement round 1 done (opus), see reviews/KEY-1-impl-r1.md"
{{SPECS_GATE}}                              # the spec gate (spec-mapped or spec-touching stories only)
```
