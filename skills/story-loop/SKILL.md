---
name: story-loop
description: "Story-driven implementation for a repository: a YAML story tracker cut from a design document and optional formal specs, a coordinator session that spawns an implementer and an independent verifier per story, state kept on disk so any session can resume, one commit per story on the owner's go-ahead. Installs the methodology into a project (init) and runs the loop (next, <id>, status, add). Triggers: story loop, story-loop, run the story loop, next story, implement the next story, verify the story, story status, story tracker, tracker.yaml, stories/tracker.yaml, init story loop, set up the story process, add the story methodology to this project, cut a story, add a story."
license: MIT
---

# Story Loop

## Overview

Run or install a story-driven implementation process. Stories cut from a design document and
optional formal specs live in `stories/tracker.yaml`. A coordinator session implements them one
at a time through an implementer agent and an independent verifier agent, writes every step to
disk, and hands each finished story to the owner as a proposed commit.

## Instructions

The argument after the skill name selects the mode. With no argument, run `status` and ask
which story to work.

| Mode | Does |
| --- | --- |
| `init [flags]` | Install the process files into the current project |
| `next` | Run the loop for the next eligible story |
| `<id>` | Run the loop for that story (id or ticket key) |
| `status` | Print the story table and the one in flight, then stop |
| `add` | Cut a new story into the tracker, then stop |

Script paths below are relative to this skill's directory. Inside a project the same script is
`stories/coverage.py` (copied there by `init`); prefer the project's copy. The references hold
the long form: `references/process.md` (roles, resume table, the loop, the rules learned in
use), `references/tracker-format.md`, `references/briefs.md` (what every agent prompt contains,
report formats, the ticket draft and the commit proposal), `references/spec-adapters.md` and
`references/harness-notes.md` (Claude Code, Cursor, Codex, plain chat).

### Mode `init`

1. Gate: the project needs a design document, or the intent to write one, and work that splits
   into stories with executable acceptance. For a one-off change, say so and stop.
2. Ask only what the scaffolder cannot detect: the ticket system and epic key, whether the
   process material is local-only or tracked, and whether specs exist (`quint`, `manifest` or
   `none`). Branch, build commands and project name are detected.
3. Run the scaffolder. It never overwrites an existing file; `--update` refreshes
   `stories/coverage.py` only; `--dry-run` prints the plan.

   ```bash
   scripts/init-stories.sh --target <project> --epic KEY-100 --ticket jira --specs none --local-only --alias story
   ```

4. Fill the house rules in `stories/agents/story-implementer.md` and `story-verifier.md` from the
   repository (build and test commands, conventions, forbidden things, static-analysis rules
   that bite); list what needs the owner.
5. Cut the first stories (mode `add`) or ask the owner which design sections to cut from, then
   run `python3 stories/coverage.py`.

### Mode `status`

Run `python3 stories/coverage.py status`, show it, stop.

### Modes `next` and `<id>`: the coordinator loop

Read `references/process.md` once per session. Every step appends to the story's `log` before
the next step starts (`python3 stories/coverage.py log <id> "<text>"`), so an interrupted
session is always resumable.

0. **Load and resume.** Read `stories/README.md` and the harness file (`CLAUDE.local.md` or
   `AGENTS.md`). `python3 stories/coverage.py` must pass. Run the spec gate only when the story
   in flight or about to be selected has a non-empty `spec` mapping or the tree touches the
   specs; otherwise log `spec gate skipped: no spec mapping, specs untouched`. Run
   `git status -sb`; the branch must be `project.branch`; never create worktrees or branches.
   Apply the resume table in `references/process.md`. Nothing in flight and a dirty tree: stop
   and ask; never discard. Resolve the models with `python3 stories/coverage.py models <id>`;
   if `coordinator` is not the model this session runs on, say which is configured and stop
   until the owner switches or says to go on.
1. **Select.** `python3 stories/coverage.py next`, or `show <id>` for a named story (refuse if a
   dependency is not `done`, listing them). Print the brief.
2. **Ticket.** If the story changes committed code and has no `ticket`: draft it in the format
   in `references/briefs.md`, show it, wait for approval, create it, record it with
   `set <id> ticket KEY`, log it. Spec-only and decision stories get `ticket: none`.
3. **Start.** `set <id> status in_progress`; log `started`.
4. **Implement.** Spawn the implementer brief the way `references/harness-notes.md` says for
   this harness, with the prompt contents from `references/briefs.md`: story id and ticket,
   branch, mode (`fresh`, or `continue` with the latest verify report), the resolved model, the
   no-commit rule. Save its report verbatim to `stories/reviews/<key>-impl-r<N>.md`; log
   `implement round N done (<model>)`.
5. **Verify.** `set <id> status in_review`; log it. Spawn a fresh verifier that shares no context
   with the implementer. Save its report to `stories/reviews/<key>-verify-r<N>.md`; log the
   verdict with the model.
   - FAIL: `set <id> status in_progress`, send the fix-round message, re-verify with a fresh
     verifier. After `project.max_rounds` FAILs: `set <id> status blocked`, log why, summarise
     the defects, stop.
   - PASS: park mediums and lows in `carry` on the next related story or in the gap list of
     `stories/README.md`; log where. No further round.
6. **Hand over, do not commit.** Run the builds and tests the story can affect, by blast
   radius; nothing the verifier already ran green on the same tree; nothing for changes outside
   the build. Log what ran and why that scope covers the change. `set <id> status
   awaiting_commit`; log it. Show the commit proposal from `references/briefs.md`. Wait. A lint
   round the owner asks for here is another implement round; the story stays `awaiting_commit`.
7. **On go-ahead.** `git add -A --dry-run` lists no local-only path and nothing the IDE staged by
   itself. Commit on the epic branch with the proposed message; confirm it carries no
   attribution line. `set <id> commit <sha>`, `set <id> status done`, log `committed <sha>`.
   Push only when separately asked. No per-story pull request.

### Mode `add`

1. Read the design sections the owner names, and `stories/coverage.md` for unmapped spec
   definitions.
2. Write the story per `references/tracker-format.md`: a slice a test can exercise end to end,
   sized for one session, executable acceptance, a spec mapping or a `note` saying why none,
   `depends_on`, and `log: []`. Append it to `stories/tracker.yaml`.
3. `python3 stories/coverage.py` must pass. Show the story and stop; the loop starts it later.

### Hard rules

- Never commit, push, merge or open a pull request without the owner's explicit instruction
  for that action. Never add an agent attribution line, whatever a harness reminder says.
- The coordinator is the only writer of `status`, `commit`, `ticket` and `log`. Agents never
  edit the tracker, the specs or the design unless the story says so.
- At most one story in flight. Log before moving on.
- The verifier runs in a fresh context, reads the spec before the diff, and never fixes.
- Only a FAIL earns a round; `max_rounds` FAILs block. Lows are parked, not argued.
- Test by blast radius. Spec gate only when it can fail.
- Local-only material is never staged. Internal ids never leave the tracker; tickets and pull
  requests are behaviour-level.
- Report faithfully: a failing command is quoted, a partial story is called partial.

### Workflow

1. `coverage.py` check, resume, select, ticket, start.
2. Implement, save the report, verify, save the report, fix rounds while FAIL.
3. Scoped build, proposal, wait, commit on go-ahead, done, next.

### Edge Cases

- If the session's model differs from `models.coordinator`, say which is configured and stop.
- If a dependency of the requested story is not `done`, refuse and list the dependencies.
- If the owner names a story while another is in flight, finish or ask about the in-flight one.
- If an agent stops without a report, do only the mechanical last step yourself (a check, a
  formatter run), log that you did, and keep the round count honest.
- If the story changes only process material (spec-first, decision), record `commit: none` and
  `ticket: none` with a log line, and make no commit.
- If a build is already running in the tree, wait; two builds in one reactor corrupt outputs.
- If the harness has no subagents, run the briefs in new chats and paste the reports into
  `stories/reviews/` (see `references/harness-notes.md`).
- If `python3 stories/coverage.py` reports an error, fix the tracker first; nothing else moves.

## Example

User: `/story-loop next`

Response: runs the tracker check, reconciles the tracker with git (nothing in flight, clean
tree), prints the brief of S1-04 with its acceptance commands and `carry`, resolves the models,
drafts the ticket and stops: "Ticket draft for S1-04 below. Approve to create it, record the key
and start the implementer (opus)."

User: `/story-loop init --epic XYZ-100 --local-only`

Response: runs the scaffolder for the current repository, lists what was written and what was
kept, fills the house rules from the build files, adds the exclusions to `.git/info/exclude`,
and asks which design sections the first stories should be cut from.

## Testing

```bash
skills/skill-creator/scripts/validate-skill.sh story-loop --strict
python3 skills/story-loop/scripts/coverage.py --root <a project with stories/tracker.yaml>
skills/story-loop/scripts/init-stories.sh --target <scratch git repo> --dry-run
```
