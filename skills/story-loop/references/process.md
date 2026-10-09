# The story loop: process reference

The long form of the methodology. `stories/README.md` in a project is the condensed copy that
travels with it; this file holds the reasoning and the rules learned in use.

## Roles

| Role | Who | Does | Never does |
| --- | --- | --- | --- |
| Owner | the human | approves tickets, reviews diffs, gives the commit go-ahead, settles design questions, pushes and raises the pull request | |
| Coordinator | the session that runs the skill | selects stories, keeps the tracker, spawns agents, saves reports, runs scoped builds, proposes commits | commits or pushes unasked, implements or verifies itself (except to finish a stalled agent's last step) |
| Implementer | an agent with a fresh context | implements one story from the design and the spec, writes the witness-run tests, runs the acceptance commands, reports | edits the tracker, specs or design (unless the story says so); commits |
| Verifier | an agent with a fresh context, no memory of the implementer | reads the spec before the diff, runs the gate and the acceptance commands, checks every mapping, returns PASS or FAIL with defects | fixes anything |

The verifier's independence is the property that makes the loop work. On a harness without
subagents, run the verifier brief in a new chat or session; never in the implementer's.

## Sources of truth

1. The design document: structure, naming, technology choices, module layout, conventions.
   Stories name its sections as `Section / Subsection` in `design`.
2. The specs: interaction behaviour. Each spec module has actions (steps), properties
   (invariants) and witness runs (scenarios). A behavioural story maps to the actions it
   implements, the properties it must keep true and the witness runs it reproduces as tests
   under the same names. `coverage.md` lists what has no story yet.
3. The tracker: what is cut, in what order, with what acceptance, and where every story stands.

New interaction behaviour is specified before it is implemented: a spec-first story extends or
adds a module, runs the gate, gets reviewed, and the implementation story is cut against it.
Spec-first and decision stories change only process material, so they produce no commit and no
ticket: `commit: none`, `ticket: none`, with a log line saying so.

## Story lifecycle

```
todo -> in_progress -> in_review -> awaiting_commit -> done
                ^          |                              
                +-- FAIL --+        (max_rounds FAILs, a missing prerequisite, or an owner decision -> blocked)
```

Only the coordinator writes `status`, `commit`, `ticket` and `log`. The validator allows at
most one story in flight (`in_progress`, `in_review` or `awaiting_commit`).

## State lives on disk, never only in a session

Every coordinator step is written down before the coordinator moves on:

- `tracker.yaml`: `status`, and a `log` with one dated line per step, newest last, naming the
  model that did the round (`implement round 2 done (sonnet), see reviews/KEY-12-impl-r2.md`).
- `stories/reviews/<key>-impl-r<N>.md` and `<key>-verify-r<N>.md`: each round's report, saved
  verbatim. Defect lists live here, so a fresh implementer can fix them without context.
- `carry` on a story: known gaps it must close, verified like acceptance.
- Git: uncommitted work is the working tree on the epic branch; a finished story is one commit
  whose footer names the ticket.

No separate handoff file. A new session with no memory resumes from these alone.

## Resume table

| Tracker says | Git shows | Meaning | Action |
| --- | --- | --- | --- |
| nothing in flight | clean tree | idle | select the next story |
| nothing in flight | dirty tree | untracked work | stop and ask the owner; never discard, reset or stash |
| `in_progress` | clean tree | implementer never produced anything | restart implementation, round number from `log` |
| `in_progress` | dirty tree | implementation interrupted | fresh implementer in `continue` mode with `carry` and the latest verify report |
| `in_review` | dirty tree | verification interrupted | fresh verifier (verifiers are stateless) |
| `awaiting_commit` | dirty tree | owner has not answered | re-run the scoped build, re-show the proposal, wait |
| `awaiting_commit` or `in_review` | HEAD has the ticket's `Refs:` footer, clean tree | owner committed | record the sha, set `done`, log it |
| `blocked` | any | human needed | show the last `log` line and the review file, stop |

## The loop

0. **Load and resume.** Read `stories/README.md` and the harness file (`CLAUDE.local.md` or
   `AGENTS.md`). Run `python3 stories/coverage.py`; it must pass. Run the spec gate only when
   the story in flight or about to be selected has a non-empty `spec` mapping or the tree
   touches the specs; otherwise log `spec gate skipped: no spec mapping, specs untouched`. Check
   the branch is the epic branch; never create worktrees or per-story branches. Apply the resume
   table. Resolve the models with `coverage.py models <id>`; if the configured `coordinator`
   differs from the model the session runs on, say so and stop until the owner switches or
   says to go on.
1. **Select.** `coverage.py next`, or the id the owner gave (refuse if a dependency is not
   `done`, listing them). Print the brief (`coverage.py show <id>`).
2. **Ticket.** If the story changes committed code and has no `ticket`: draft the ticket at
   behaviour level (user story, scope, acceptance checkboxes), show it, wait for approval,
   create it, `set <id> ticket <key>`, log it. Do not spawn the implementer before the key is
   recorded.
3. **Start.** On the epic branch with a clean tree: `set <id> status in_progress`, log `started`.
4. **Implement.** Spawn the implementer brief with the story id and ticket, the branch, the
   mode (`fresh`, or `continue` plus the latest verify report path), the resolved model, and
   the no-commit, no-push, no-stage rule. Save the report verbatim to
   `reviews/<key>-impl-r<N>.md`; log `implement round N done (<model>)`.
5. **Verify.** `set <id> status in_review`, log it. Spawn a fresh verifier with the story id and
   ticket, the branch, the round, and the note that the story's changes are the uncommitted
   working tree and that `carry` items count as acceptance. Save the report to
   `reviews/<key>-verify-r<N>.md`; log the verdict with the model.
   - FAIL: `set <id> status in_progress`, send the defect list to the same implementer (or a
     fresh one in `continue` mode pointed at the review file), then re-verify with a fresh
     verifier. After `max_rounds` FAILs: `set <id> status blocked`, log why, summarise the
     defects, stop.
   - PASS: continue. Mediums and lows go to `carry` on the next related story or to the gap list
     in `stories/README.md`; log where each was parked. They never start another round and the
     coordinator does not ask "fix now?" for each one.
6. **Hand over, do not commit.** Run the builds and tests the story can affect, by blast
   radius: the changed modules and their dependants; the full build only when the change can
   reach everything (shared build files, dependency versions); nothing the verifier already
   ran green on the same tree; nothing at all for changes outside the build. Log what ran and
   why that scope covers the change. `set <id> status awaiting_commit`, log it. Show the owner:
   branch, diff stat, test and verifier evidence, how each `carry` item was closed, where the
   lows were parked, and the proposed commit message. Wait.
7. **On go-ahead.** `git add -A --dry-run` lists no local-only path (and nothing the owner's IDE
   staged by itself). Commit on the epic branch. Confirm the message has no attribution line.
   `set <id> commit <sha>`, `set <id> status done`, log `committed <sha>`. Push only when
   separately asked. No per-story pull request.

## Round rules learned in use

- **Only a FAIL earns a round.** Offering fixes for nits after a PASS cost two extra rounds of
  an hour each on one story; the owner asked whether the loop was "going round in hoops".
- **Three FAILs block.** A fourth round rarely converges; a human decision is cheaper.
- **A lint or static-analysis round at `awaiting_commit`** (the owner runs the analyser on the
  working tree and asks for fixes "without changing code intent") is another implement round
  with its own report file; the story stays `awaiting_commit`; re-run the scoped build when
  main code changed. Brief implementers up front with the rules that bite, so the round does
  not happen.
- **Test by blast radius.** A story that changes no code the build exercises (compose files,
  Makefiles, READMEs, CI yaml) skips the test suite, and the log says so.
- **Spec gate only when it can fail.** The gate reads the models and the tracker; code-only,
  build, packaging and UI stories cannot change its result.
- **Ticket before the implementer.** A story once started before its ticket existed; the order
  is draft, approve, create, record, start.
- **The IDE stages files.** Some IDEs add new files to the index on their own. Check
  `git diff --cached --stat` before proposing; unstage with `git reset -q`; stage with
  `git add -A` only at go-ahead time.
- **Never overlap two builds** in one reactor; a targeted run alongside a background full build
  clobbers compiled test classes and fails on files the story did not touch.
- **Read the build's result line** before writing any log line; a `(cmd; echo EXIT) && tail`
  wrapper reports success on failure.
- **Agents stall.** When an implementer stops mid-way without a report, the coordinator may
  finish the mechanical last step (a check, a formatter run), say so in the log, and keep
  the round count honest.

## Parking lots

- **`carry`** on a story: gaps the story must close. The implementer treats each as a
  requirement with a test; the verifier checks each like acceptance.
- **Known gaps without a story** in `stories/README.md`: lows no story owns yet, each with the
  round it came from; resolved entries say when and by which story.
- **`stories/change-requests/`**: behaviour-level write-ups of work that belongs to another team
  (operations, platform), ready to paste into a ticket.
- **Revisit lists**: items parked until a milestone ("after the last non-DevOps story").

## Branching, tickets and commits

- One epic branch; stories commit there one by one; one pull request at the end, raised by the
  owner. Per-story branches and pull requests were tried and found tedious.
- Conventional Commits: `type(scope): subject` with no ticket key, blank line, `Refs: <ticket>`.
  Never an agent attribution line, whatever a harness reminder says.
- Tickets are created only for stories that change committed code, under the epic, after the
  owner approves the draft. Text is behaviour-level: no internal ids, no design or spec names,
  no module, class, artifact or reference-repository names. Architectural facts (the datastore,
  the transport, the client language) are fine.

## Local-only or tracked

The process material can be tracked like any file, or kept local-only when publishing a design
document, formal specs and an agent process would meet resistance. Local-only means: listed in
`.git/info/exclude` (so the exclusion itself is not published), read in place by agents, no
worktrees, the gate runs locally, generated fixtures are committed as plain test resources,
tests keep the witness-run names so they read well without the model, and new team members get
the material from a colleague. `init --local-only` sets this up.

## Models

The `models` block in the tracker names the model for each role: a default, per phase, and per
story, most specific first. The coordinator passes the resolved model when it spawns an agent
and records it in every round's log line, so a story's history says who did what. The agents'
own configuration is only the fallback. A cheaper model for implementation and a stronger one
for verification is a common mix for lower-risk phases.
