# Story template

Every entry in `tracker.yaml` has these fields. A story that cannot fill the `spec` block is
either infrastructure (say so in `spec.note`) or a sign that a spec-first story is missing.

```yaml
- id: S<phase>-<nn>              # internal id; never appears outside the tracker and reviews
  title: Imperative, one line
  ticket: KEY-123                # the outward-facing ticket; the coordinator fills it before the story starts
  phase: 0
  status: todo | in_progress | in_review | awaiting_commit | done | blocked
  commit: sha of the story's commit on the epic branch, once done (`none` for spec-only stories)
  depends_on: [ids that must be done first]
  design:
    - "Section / subsection of the design document" the story implements
  summary: >
    What exists when the story is done, in terms of behaviour and modules.
    Precise enough that an agent needs no other brief; short enough to read twice.
  spec:
    modules: [module ...]
    actions:       [module.action ...]   # spec steps this story implements
    properties:    [module.prop ...]     # invariants the implementation must preserve, as tests
    witness_runs:  [module.runTest ...]  # spec scenarios reproduced as tests, same name
    note: anything the mapping needs explained, or why it is empty
  acceptance:
    - a command that exits 0 only when the story is done
  prerequisites:   # optional: things outside the repository that must be true first
    - ...
  carry:           # optional: known gaps this story must also close; verified like acceptance
    - ...
  models:          # optional: { implementer: sonnet } overrides the phase and default models
  log:             # coordinator-only: one dated line per step, newest last
    - 2026-01-15 started
```

## Rules

- **Slices, not layers.** A story delivers one behaviour a test can exercise end to end.
- **Sized for one session.** If an implementer cannot finish it in one focused run, split it before starting.
- **Executable acceptance.** "Compiles" and "reviewed" are not acceptance criteria. The command is what the verifier runs.
- **Spec mapping is mandatory for behaviour.** Actions name what is implemented, properties name what must not break, witness runs name the tests to write. The test for a witness run carries the run's name.
- **Spec-first for new interaction behaviour.** If a story changes how components interact and no spec covers it, a spec-first story precedes it: extend or add a module, run the spec gate, review, then cut the implementation story against it. Spec-first and decision stories produce no commit and no ticket (`commit: none`, `ticket: none`).
- **Design and spec move together.** A story that changes the design edits the design document and the affected spec in the same commit.
- **One commit per story** on the epic branch, only on the owner's explicit go-ahead: Conventional Commits subject with a scope and no ticket key, blank line, `Refs: <ticket>` footer, never any agent attribution. Internal ids never appear in branches, commits, tickets or pull requests.
- **Carry forward, do not loop.** Low findings from a PASS go into the next related story's `carry` or the gap list in `README.md`; they never start another round.
- **Log before moving on.** Every coordinator step appends a dated line (`python3 stories/coverage.py log <id> "<text>"`), so an interrupted session is always resumable.
