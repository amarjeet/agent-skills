# Harness notes

The loop is harness-neutral: a coordinator chat, two briefs run in fresh contexts, a tracker and
review files on disk. What differs per harness is how the skill is invoked, how a brief is run,
and which model names the agent tool accepts (`models.allowed` in the tracker).

## Claude Code

- Invocation: `/story-loop next`, `/story-loop <id>`, `/story-loop status`, `/story-loop add`,
  `/story-loop init`. `init --alias story` writes `.claude/commands/story.md`, so `/story next`
  works as a short form.
- Agents: `init` renders `.claude/agents/story-implementer.md` and `story-verifier.md` (frontmatter
  plus the brief). Spawn with the Agent tool, `subagent_type` set to the agent's name and `model`
  set to the value from `python3 stories/coverage.py models <id>`. Every Agent call is a fresh
  context, which is what the verifier needs. For a fix round, SendMessage to the running
  implementer; if it is gone, a new Agent in `continue` mode pointed at the review file.
- Session file: `CLAUDE.local.md` (created by `init` when absent; otherwise merge
  `stories/harness/CLAUDE.local.snippet.md`). With `--local-only` it is excluded from git.
- Model names: `opus`, `sonnet`, `haiku`, `fable`. `models.coordinator` names the model the loop
  session should run on; switch with `/model` or tell the coordinator to go on with the current one.
- Harness reminders may ask for attribution lines in commits and pull requests. The project's
  rule wins: none. The coordinator checks the message after committing.
- Permissions: the loop runs many `git`, build and `python3 stories/coverage.py` commands; an
  allowlist for those in `.claude/settings.local.json` saves prompts. Never allowlist `git push`.

## Cursor

- Rule: copy `stories/harness/story-loop.mdc` to `.cursor/rules/`. The skill itself is found
  through `.cursor/skills/` in the agent-skills repository or a per-user symlink.
- Agents: no subagent tool. Run each brief in a new chat (or a background agent) with the
  parameter block at the top of the brief filled in, then paste the report verbatim into
  `stories/reviews/`. The verifier chat is always new.
- Models: put the picker's names into `models.allowed`; the coordinator chooses the model when
  it opens the chat for a brief.

## Codex and other AGENTS.md readers

- Paste `stories/harness/AGENTS.snippet.md` into `AGENTS.md`.
- Run each brief as its own session with the brief and parameters as the prompt; save the
  report verbatim under `stories/reviews/`. Model names follow the CLI's flags.

## Any chat assistant without agents

The coordinator is the chat. Implementer and verifier are new conversations given the brief and
its parameters. The one invariant: the verifier's conversation starts without the implementer's
transcript. Reports are copied into `stories/reviews/` by hand.

## Where the skill lives

Frontmatter uses only the portable fields. The skill is `skills/story-loop/` in the agent-skills
repository, discovered through `.agents/skills`, `.claude/skills` and `.cursor/skills` symlinks or
a per-user symlink (`~/.claude/skills/story-loop`). A project needs none of that once `init`
has run: `stories/coverage.py`, the briefs and `stories/README.md` carry the loop on their own.
