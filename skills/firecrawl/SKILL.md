---
name: firecrawl
description: "Use the installed Firecrawl CLI to search, scrape, crawl, map, parse, monitor, or interact with web content and local documents. Triggers: search the web, scrape this URL, fetch this page, crawl these docs, map this site, parse this file, monitor this page, use firecrawl."
---

# Firecrawl

## Overview

Use the local `firecrawl` CLI for web discovery, page extraction, site crawling, local document parsing, page monitoring, and post-scrape browser interaction.

## Instructions

Run `firecrawl --status` before real work to verify the installed CLI, authentication, account access, local cache state, and whether `.firecrawl/` is ignored. If authentication is missing, ask the user to run `firecrawl login` or provide `FIRECRAWL_API_KEY`; do not invent credentials.

Prefer file output for non-trivial results:

```bash
mkdir -p .firecrawl
firecrawl search "query" --json -o .firecrawl/search-query.json
firecrawl scrape "https://example.com/page" -o .firecrawl/example-page.md
```

Quote URLs and queries. Shells treat `?`, `&`, spaces, and parentheses specially. For structured JSON output, add `--json` and usually `--pretty`. For command details and flags, read `references/cli-command-reference.md`.

### Workflow

1. Classify the task before choosing a command: unknown source -> `search`; known page -> `scrape`; known site but unknown page -> `map`; many pages -> `crawl`; local PDF/DOCX/XLSX/HTML -> `parse`; recurring change detection -> `monitor`; needs clicks, forms, pagination, or login state -> `scrape` first, then `interact`.
2. Check for existing `.firecrawl/` outputs before spending credits on repeated calls. Reuse `search --scrape` results instead of scraping those URLs again.
3. Keep scope narrow by setting `--limit`, `--search`, `--include-paths`, `--exclude-paths`, `--max-depth`, or focused URLs when available.
4. Write large outputs to `.firecrawl/`, then inspect only relevant sections with file-reading or search tools. Do not dump huge scraped files into the chat.
5. For multi-step browser tasks, start with `firecrawl scrape "<url>"`, then run `firecrawl interact "..."` against the saved last scrape or pass `--scrape-id`.
6. Summarize the useful findings and cite saved output paths when returning results to the user.

### Edge Cases

- If `firecrawl --status` reports authenticated but cannot fetch account info, disclose that status and try a small scoped request only when the user wants to spend credits.
- If `.firecrawl/` is not ignored in the current git repo, add or request permission to add it to `.gitignore` before creating bulky or sensitive outputs.
- If a page requires stateful login, use `--profile <name>` with `scrape` when appropriate and avoid exposing secrets in prompts, filenames, or command logs.
- If the request needs exact fields from a page, use `scrape --schema-file` or `agent --schema-file` rather than asking for unstructured markdown and parsing it manually.
- If the user asks to download a whole site, use `firecrawl experimental download`, not a top-level `download` command.
- If the user wants local codebase search, git operations, deployment, or non-web file edits, do not use Firecrawl.

## Example

User: "Use firecrawl to find the current Firecrawl CLI docs and summarize the scrape command."

Response: run `firecrawl search "Firecrawl CLI scrape command docs" --scrape --limit 3 --json -o .firecrawl/firecrawl-cli-scrape.json`, inspect the saved JSON for authoritative sources, then summarize only the relevant `scrape` usage and options.

## Testing

Run validation from anywhere:

```bash
skills/skill-creator/scripts/validate-skill.sh firecrawl
skills/skill-creator/scripts/validate-skill.sh firecrawl --strict
```

If the scripts are not executable in this checkout, prefix the same repo-relative paths with `bash`.
