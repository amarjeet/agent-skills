<!-- Paste into AGENTS.md (Codex, Cursor and other harnesses that read it). -->

## Story-driven implementation (story-loop)

- Process: `stories/README.md`. Stories and state: `stories/tracker.yaml`. Run
  `python3 stories/coverage.py` before picking work; it must pass.
- The coordinator is the chat session that runs the loop in `stories/README.md`. It is the only
  writer of `status`, `commit`, `ticket` and `log` in the tracker.
- The implementer and verifier briefs are `stories/agents/story-implementer.md` and
  `stories/agents/story-verifier.md`. Run each in a fresh context (a new agent, chat or
  subagent) with the parameters at the top of the brief; the verifier must share no context
  with the implementer. Save each report verbatim to `stories/reviews/<key>-impl-r<N>.md` or
  `<key>-verify-r<N>.md`.
- Never commit or push without an explicit instruction for that commit. Never add an agent
  attribution line. Every story is one commit on `{{BRANCH}}`.
- When `project.local_only` is true in the tracker, never stage `stories/`, the design document,
  the specs or the agent files.
- Test by blast radius; run the spec gate only for spec-mapped or spec-touching stories.
- Tickets and pull requests are behaviour-level only; internal story ids never leave the tracker.
