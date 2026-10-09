# Spec adapters

`project.specs.kind` in the tracker header tells `coverage.py` where the actions, properties and
witness runs a story can map to come from.

## `quint`

Each `specs/*.qnt` file holds one behaviour module (lowercase name, first `module` in the file)
followed by instance modules (capitalised) that bind constants for checking and hold rejected
designs. Only the behaviour module's top-level definitions are mapped:

```quint
module publish {
  action receive(id) = ...        // actions:        publish.receive
  val ackedIsCommitted = ...      // properties:     publish.ackedIsCommitted
  run retryIsIdempotentTest = ... // witness_runs:   publish.retryIsIdempotentTest
}
module PublishSync { import publish(N = 2).* ... }          // instance: not mapped
module PublishAsyncRejected { ... run lostAckViolates = ... } // rejected design: not mapped
```

The parser takes two-space-indented `action`, `val` and `run` members up to the first
capitalised `module`. `project.specs.ignore` removes plumbing (`init`, `step`, frame conditions,
helper runs) so `coverage.md` lists only what a story can own.

The gate (`scripts/check-specs.sh`, skeleton installed by `init --specs quint`):

1. `quint typecheck` every file.
2. Witness runs with `quint test --main <Instance> --match '<pattern>'`, through `expect_passing N`
   so a renamed run cannot pass silently (`quint test` exits 0 when `--match` selects nothing).
3. Invariants with `quint run --invariant <prop> --max-steps --max-samples`.
4. Documented violations: rejected-design instances must be found violating their property
   (`expect_violation`), and their `...Violates` runs must pass.
5. `python3 stories/coverage.py` for the tracker references.
6. `--itf` writes ITF traces for a conformance harness that replays them against the running
   system; commit them as plain test fixtures so CI needs no knowledge of the model.

Bounded model checking (`quint verify`, Apalache) takes minutes to tens of minutes per instance:
run it nightly, not in the gate, and record results in the specs README's properties table.

## `manifest`

For spec languages the script does not parse (TLA+, Alloy, Gherkin features, prose invariants),
`specs/index.yaml` lists the definitions by hand:

```yaml
modules:
  publish:
    file: specs/publish.tla
    actions: [Receive, Commit, Ack]
    properties: [AckedIsCommitted]
    witness_runs: [RetryIsIdempotent]
```

Keep the manifest next to the specs and update it in the same spec-first story that changes
them. The gate is whatever checks the language has (`tlc`, `alloy`, a feature runner); point
`project.specs.gate` at a script that runs them and ends with `python3 stories/coverage.py`.

## `none`

No formal specs. Every story's `spec` block must be empty; `coverage.md` carries only the
status tables. The design document carries the behavioural claims, and the verifier holds the
diff to its named sections. Move to `manifest` the day a component's interactions become
subtle enough that a written model would catch something a test would not.

## Witness runs become tests

A test class or method named after the run (`WorkerCrashRedeliversDuplicateTest` for
`workerCrashRedeliversDuplicateTest`) follows the run's steps and asserts its expectations.
Where the spec abstracts time or faults, the project needs an injectable clock and fault hooks
so the steps are reproducible; the story that introduces them is usually among the first.

## Spec-first stories

When a story would change how components interact and no spec covers it:

1. Cut a spec-first story: extend or add a module, write the witness runs the design claims,
   add the rejected alternatives as instances with `...Violates` runs, run the gate, update the
   specs README's properties table.
2. Have it verified like any story (the verifier reads the design and checks the model holds
   it to account). It produces no commit and no ticket (`commit: none`, `ticket: none`).
3. Cut the implementation story against the new definitions.

A decision story (the owner settles an open design question in the design document and the
spec together) follows the same path.
