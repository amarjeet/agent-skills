# Tracker format

`stories/tracker.yaml` is the single file the loop reads and writes. `stories/coverage.py`
validates it, renders `stories/coverage.md`, and edits the coordinator's fields line by line so
comments survive. Everything else is edited by hand.

## Header (version 2)

```yaml
version: 2
project:
  name: my-service
  design: [docs/DESIGN.md]             # one or more design documents
  specs:
    kind: quint                        # quint | manifest | none
    dir: specs/
    gate: scripts/check-specs.sh       # the local spec gate; empty when kind is none
    ignore:                            # definitions that are plumbing, not behaviour
      actions: [init, step]
      properties: []
      witness_runs: []
  branch: feature/XYZ-100              # the epic branch
  ticket: { system: jira, project: XYZ, epic: XYZ-100 }   # system: jira | github | linear | none
  commit: { footer: Refs }             # `Refs: XYZ-123` footer; no key in the subject
  build:
    full: "mvn -B verify"
    scoped: "mvn -B -pl {modules} -amd verify"
  local_only: true
  max_rounds: 3
models:
  allowed: [opus, sonnet, haiku, fable]   # the names the harness's agent tool accepts
  default: { coordinator: opus, implementer: opus, verifier: opus }
  phases:
    3: { implementer: sonnet }
stories:
  - ...
```

Version 1 trackers (top-level `design`, `specs`, `jira_epic`, optional `specs_ignore`, story
field `jira`) still load; `jira` is an alias of `ticket` everywhere.

## Story fields

| Field | Who writes | Meaning |
| --- | --- | --- |
| `id` | author | `S<phase>-<nn>` or any scheme that sorts naturally; internal, never leaves the tracker |
| `title` | author | imperative, one line |
| `ticket` | coordinator | the outward-facing key, recorded before implementation starts; `none` for spec-only stories |
| `phase` | author | groups stories; `models.phases` keys on it |
| `status` | coordinator | `todo`, `in_progress`, `in_review`, `awaiting_commit`, `done`, `blocked` |
| `commit` | coordinator | the story's commit sha once done; `none` for spec-only stories |
| `depends_on` | author | ids that must be `done` first; no cycles |
| `design` | author | `Section / Subsection` names in the design document(s) |
| `summary` | author | what exists when the story is done; the implementer's whole brief |
| `spec` | author | `modules`, `actions`, `properties`, `witness_runs` as `module.name`, and a `note` |
| `acceptance` | author | commands that exit 0 only when the story is done; the verifier runs them |
| `prerequisites` | author | optional; facts outside the repository that must hold first |
| `carry` | coordinator | optional; gaps from earlier rounds this story must close, verified like acceptance |
| `models` | author | optional; `{ implementer: sonnet }` overrides phase and default |
| `log` | coordinator | one dated line per step, newest last |

## Rules

- **Slices, not layers.** One behaviour a test can exercise end to end.
- **Sized for one session.** Split before starting if an implementer could not finish in one run.
- **Executable acceptance.** "Compiles" and "reviewed" are not criteria.
- **Spec mapping is mandatory for behaviour**; infrastructure stories say so in `spec.note`.
- **Spec-first for new interaction behaviour**; design and spec move in the same commit.
- **One commit per story** on the epic branch, on explicit go-ahead.

## Two example stories

A behavioural story with a spec mapping:

```yaml
  - id: S0-07
    title: Ingest publish path (ledger first)
    ticket: XYZ-127
    phase: 0
    status: done
    commit: 9f3c2a1
    depends_on: [S0-02, S0-03, S0-06]
    design:
      - "Components and interactions / Ingest"
      - "Failure modes and behaviour / Crash between commit and append"
    summary: >
      POST /v1/topics/{topic}/messages commits the ledger row before answering 202, then
      appends to the stream; a retry with the same message id changes nothing; a crash between
      commit and append leaves a row the sweeper later repairs.
    spec:
      modules: [publish]
      actions: [publish.receive, publish.commit, publish.ack, publish.xadd]
      properties: [publish.ackedIsCommitted, publish.oneRowPerId]
      witness_runs: [publish.retryIsIdempotentTest, publish.crashBetweenCommitAndAppendTest]
      note: The sweeper's repair is S0-08; this story leaves the unlinked row in place.
    acceptance:
      - mvn -B -pl core -am verify
    carry:
      - "Error payloads lack a machine-readable reason (from XYZ-126 verify r1): add `reason` and a test."
    log:
      - 2026-01-14 ticket drafted, awaiting owner approval
      - 2026-01-14 owner approved; created XYZ-127 under XYZ-100
      - 2026-01-14 started; spec gate passed
      - 2026-01-14 implement round 1 done (opus), see reviews/XYZ-127-impl-r1.md
      - 2026-01-14 in_review; verify round 1 FAIL (opus), retry test lacks the duplicate step; see reviews/XYZ-127-verify-r1.md
      - 2026-01-14 in_progress; fix round 2 sent to the implementer (opus)
      - 2026-01-15 implement round 2 done (opus), see reviews/XYZ-127-impl-r2.md
      - 2026-01-15 in_review; verify round 2 PASS (opus), see reviews/XYZ-127-verify-r2.md; low 3 carried into S0-08
      - 2026-01-15 scoped build core -amd green; awaiting_commit; proposal shown to the owner
      - 2026-01-15 owner go-ahead; committed 9f3c2a1
```

An infrastructure story without one:

```yaml
  - id: S3-01
    title: Root Compose stack and Makefile
    ticket: XYZ-196
    phase: 3
    status: todo
    depends_on: [S2-15]
    design:
      - "docs/DEMO.md / Compose at the root"
    summary: >
      compose.yaml at the root with named volumes and a two-tier profile; a Makefile with
      demo-up, demo-down, demo-reset and chaos targets.
    spec: { modules: [], actions: [], properties: [], witness_runs: [], note: Packaging and local tooling; no interaction behaviour. }
    acceptance:
      - docker compose -f compose.yaml config -q
      - "sh -c 'docker compose up -d --wait && curl -fsS localhost:8081/ready && docker compose down -v'"
    log: []
```

## Log line conventions

One line per step, dated, with the model of any agent round and the review file it produced:

```
<date> ticket drafted, awaiting owner approval
<date> owner approved; created KEY-N under KEY-EPIC
<date> started; spec gate passed | spec gate skipped: no spec mapping, specs untouched
<date> implement round N done (<model>), see reviews/KEY-N-impl-rN.md
<date> in_review; verify round N PASS|FAIL (<model>), <one-line reason>; see reviews/KEY-N-verify-rN.md
<date> in_progress; fix round N+1 sent to the implementer (<model>)
<date> lows 2 and 4 carried into S1-03; low 5 to the gap list
<date> scoped build <what> green | full build skipped: outside the build's blast radius
<date> awaiting_commit; proposal shown to the owner
<date> owner lint round (<n> findings); fix round N sent (<model>)
<date> owner go-ahead; committed <sha>
<date> blocked: <why>
```

`python3 stories/coverage.py log <id> "<text>"` prefixes today's date, quotes the line when YAML
needs it (a `: ` inside breaks a plain scalar), appends it to the story's `log`, and re-validates.
`set <id> status|commit|ticket <value>` edits the one line and keeps any trailing comment. Both
refuse an edit that would make the file invalid, and `set status` refuses a second story in flight.

## Validation

`python3 stories/coverage.py` fails on: an unknown status, more than one story in flight, a
`done` story without `commit`, an unknown or cyclic dependency, a duplicate id, a spec
reference that does not exist in the specs, a model name outside `allowed`, and a spec mapping
when `kind` is `none`. It warns on a story without acceptance commands.

`coverage.md` is generated; never edit it. It shows, per spec module, every action, property
and witness run with the stories that map it and their status, then every story with its
resolved models. Unmapped definitions are either plumbing (add to `ignore`) or missing stories.
