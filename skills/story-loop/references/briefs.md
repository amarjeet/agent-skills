# Briefing the agents

The briefs live in the project as `stories/agents/story-implementer.md` and
`stories/agents/story-verifier.md` (Claude Code reads the rendered copies in `.claude/agents/`).
They are the agents' standing instructions. The prompt the coordinator sends adds the per-run
parameters. What matters is in the prompt, not in the coordinator's memory: the agent has none
of it.

## Every implementer prompt contains

- The story id and its ticket key, and the instruction to read the story, including `carry`,
  from `stories/tracker.yaml` (`python3 stories/coverage.py show <id>` prints it).
- The branch, and that the work happens in this checkout: no worktree, no new branch.
- The mode: `fresh`, or `continue` with the path of the latest `stories/reviews/<key>-verify-r<N>.md`
  and the sentence "build on the current working tree; never discard, reset or stash it; fix
  every defect in the review and say per defect what you changed".
- The no-commit, no-push, no-stage rule, and the local-only paths when the project has them.
- The house rules that bite for this story (static analysis rules, forbidden dependencies), so
  no lint round is needed later.
- The resolved model, passed to the harness's agent tool, not written in the prompt.

## Every verifier prompt contains

- The story id and its ticket key, the branch, and the round number.
- That the story's changes are the uncommitted working tree (`git diff HEAD` plus untracked
  files); earlier stories are already committed and not under review.
- That `carry` items count as acceptance criteria.
- The gate rule: run the spec gate only when the story has a spec mapping or the diff touches
  the specs; otherwise say it was skipped and why.
- The build rule: tests by blast radius; the full build only when the coordinator says so.
- The report format: `PASS` or `FAIL` first, defects most severe first, then evidence.

The verifier gets a fresh context every round. It must not see the implementer's reasoning;
it may read the implementer's report last, as a claim to check, never as evidence.

## The fix-round message

To the same implementer when it is still reachable, otherwise a fresh one in `continue` mode:

```
Verification round N of <id> (<ticket>) FAILED. The defects are in
stories/reviews/<key>-verify-rN.md. Fix every one on the current working tree; do not discard
or reset anything; say per defect what you changed; re-run the acceptance commands; do not
commit. Report as before.
```

## Report formats

Implementer (`reviews/<key>-impl-r<N>.md`), saved verbatim with a first line
`# <key> implement round N (<model>)`:

1. Branch and the proposed commit subject with the `Refs:` footer.
2. Files changed, one line each.
3. The mapping: each spec action, property and witness run, and each `carry` item, to the code
   and the test that cover it.
4. Acceptance results, command by command.
5. Assumptions and design gaps.
6. What is missing, if anything. A partial story is reported as partial.

Verifier (`reviews/<key>-verify-r<N>.md`), saved verbatim with a first line
`# <key> verify round N (<model>): PASS|FAIL`:

1. `PASS` or `FAIL` on its own line.
2. Defects (the FAIL reasons), numbered, most severe first: file and line, what the spec or
   design requires, what the code does, how to reproduce, a suggested fix.
3. Mediums and lows, numbered on, same shape. These never fail the story on their own.
4. "Checked and correct": what was verified and found right, so the next round does not redo it.
5. Evidence: every command run and its result line.

## Severity, so rounds stay few

FAIL only for: a failing acceptance command, a mapped run, property or action missing or wrong,
unspecified behaviour, an unclosed `carry` item, a broken build, a violated design rule.
Everything else is medium or low. The coordinator parks mediums and lows in `carry` or the gap
list and says where in the log and in the commit proposal.

## The ticket draft

Shown to the owner before any code story starts; created only on approval; behaviour-level only.

```
## User story
As a <role>, I want <capability>, so that <outcome>.

## Scope
- What exists when the story is done, as behaviour a user or operator can observe.

## Acceptance criteria
- [ ] A check someone outside the team could run or observe.
```

Never in a ticket: internal story ids, the design document, spec or property names, module,
class, artifact or reference-repository names. Architectural facts are fine.

## The commit proposal

Shown at `awaiting_commit`:

```
Branch: <epic branch>    Story: <id> (<ticket>)
Diff: <git diff --stat HEAD, condensed>
Evidence: verify round N PASS (<model>); <scoped build> green; spec gate <passed|skipped: why>
Carry: <item> -> closed by <test>; ...
Parked: lows 2, 4 -> carry on <next story>; low 5 -> gap list
Staged by the IDE: <none | files, unstaged>

    <type>(<scope>): <subject>

    Refs: <ticket>
```

Then wait. On go-ahead, commit exactly that message, record the sha, set `done`, log it.
