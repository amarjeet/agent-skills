# {{PROJECT_NAME}}: story-loop instructions (local)

This file points at the implementation process. It is loaded automatically by Claude Code in this
directory.

## Read on every session start
- `stories/README.md`: the process, the branching rules, the coordinator loop, the resume table.
- `stories/tracker.yaml`: the stories, their status, spec mappings and ticket keys.
- Run `python3 stories/coverage.py` before picking work; it must pass.
- Resuming: the tracker's `status` and `log`, `stories/reviews/` and git are the whole state;
  there is no handoff file. `/story-loop` step 0 reconciles them.

## Rules that override defaults
- **Never commit or push without an explicit instruction for that commit.** Prepare the commit,
  show the message, and wait. Never add an agent attribution line.
- **Local-only material.** When `project.local_only` is true in the tracker, `stories/`, the
  design document, the specs, the spec gate and the agent files are git-ignored and must never
  be staged. Agents read them in place; no worktrees.
- **One checkout, one branch.** Every story is implemented in this checkout on `{{BRANCH}}`, one
  commit per story. No per-story branch or pull request; the owner raises one at the end.
- **Commits** are Conventional Commits with the ticket key in a `Refs:` footer, not the subject.
  Internal story ids never appear in commits, branches, tickets or code comments.
- **Specs are the reference.** Run the spec gate only when the story has a spec mapping or
  touches the specs; otherwise skip and log it.
- **Test by blast radius.** Run only what a change can affect; never re-run green, untouched
  areas for ritual.
- **Outward-facing text** (tickets, pull requests) is behaviour-level only.

## Working the tracker
`/story-loop next` runs the coordinator loop for the next eligible story, `/story-loop <id>` for a
specific one, `/story-loop status` prints the table. The coordinator session is the only writer of
`status`, `commit`, `ticket` and `log` in `stories/tracker.yaml`; agents never edit it.
