# Firecrawl CLI Command Reference

This reference is based on `firecrawl --help` and subcommand help for Firecrawl CLI v1.18.1. Run `firecrawl <command> --help` when exact flags matter.

## Global

```bash
firecrawl --status
firecrawl --api-key "$FIRECRAWL_API_KEY" --api-url "https://api.firecrawl.dev" <command>
firecrawl login
firecrawl logout
firecrawl credit-usage --json --pretty -o .firecrawl/credits.json
```

Use `--status` first. It reports version, auth state, account access, local `.firecrawl/` cache state, and whether `.firecrawl` is ignored by git.

## Command Choice

- `search`: discover URLs from a query. Use `--scrape` when result contents are needed immediately.
- `scrape`: extract one or more known URLs. Multiple positional URLs run concurrently and save to `.firecrawl/` by default when no `-o` is supplied.
- `map`: discover URLs on a known site, optionally filtered by `--search`.
- `crawl`: extract many pages from a site or check/cancel a crawl job by ID.
- `parse`: convert a local `.html`, `.pdf`, `.docx`, `.doc`, `.odt`, `.rtf`, `.xlsx`, or `.xls` file into markdown, HTML, links, JSON, or summaries.
- `agent`: run an AI extraction job, best for complex structured data across pages.
- `interact`: run prompts or Playwright code against a live browser session from a previous scrape.
- `monitor`: schedule recurring scrapes/crawls and inspect checks.
- `experimental download`: save a site section into `.firecrawl/` as nested local files.

## Search

```bash
firecrawl search "query" --limit 5 --json -o .firecrawl/search.json
firecrawl search "query" --scrape --scrape-formats markdown --limit 3 --json -o .firecrawl/search-scraped.json
```

Useful flags: `--sources web,images,news`, `--categories github,research,pdf`, `--tbs qdr:w`, `--location`, `--country`, `--ignore-invalid-urls`, `--timeout`.

After using a search result, send feedback when useful:

```bash
firecrawl search-feedback "<searchId>" --rating good --valuable-sources '[{"url":"https://example.com","reason":"Authoritative"}]' --silent
```

Respect `FIRECRAWL_NO_SEARCH_FEEDBACK=1` if present.

## Scrape

```bash
firecrawl scrape "https://example.com" -o .firecrawl/example.md
firecrawl scrape "https://example.com" --format markdown,links --json --pretty -o .firecrawl/example.json
firecrawl scrape "https://example.com" --schema-file schema.json --json --pretty -o .firecrawl/example-structured.json
```

Useful flags: `--format markdown,html,rawHtml,links,images,screenshot,summary,changeTracking,json,attributes,branding`, `--only-main-content`, `--wait-for`, `--max-age`, `--country`, `--languages`, `--query`, `--profile`, `--no-save-changes`, `--actions-file`, `--proxy`.

Single format outputs raw content. Multiple formats output JSON.

## Map And Crawl

```bash
firecrawl map "https://example.com" --search "docs auth" --limit 20 --json --pretty -o .firecrawl/map.json
firecrawl crawl "https://example.com/docs" --wait --limit 50 --max-depth 3 --include-paths "/docs" --pretty -o .firecrawl/crawl.json
firecrawl crawl "<job-id>" --status --pretty
firecrawl crawl "<job-id>" --cancel
```

Use `map` before `crawl` when you need to find a page. Use `crawl` when bulk content is the desired output. Important crawl controls include `--exclude-paths`, `--include-paths`, `--sitemap skip|include`, `--ignore-query-parameters`, `--allow-subdomains`, `--delay`, `--max-concurrency`, `--scrape-options-file`, and `--webhook`.

## Parse

```bash
firecrawl parse ./report.pdf -o .firecrawl/report.md
firecrawl parse ./report.pdf --format markdown,links --json --pretty -o .firecrawl/report.json
firecrawl parse ./report.pdf --query "What is the total revenue?"
```

Max upload size is 50 MB. Supported file types are `.html`, `.htm`, `.pdf`, `.docx`, `.doc`, `.odt`, `.rtf`, `.xlsx`, and `.xls`.

## Agent And Interact

```bash
firecrawl agent "Extract pricing tiers from these pages" --urls "https://example.com/pricing" --schema-file schema.json --wait --json --pretty -o .firecrawl/pricing.json
firecrawl scrape "https://example.com/pricing"
firecrawl interact "Click the monthly billing toggle and extract the Pro price" --json -o .firecrawl/interact.json
firecrawl interact -c "await page.title()"
firecrawl interact stop
```

Use `agent --model spark-1-mini` for cheaper default work or `--model spark-1-pro` for higher accuracy. Use `--max-credits`, `--wait`, `--status`, and `--cancel` to control jobs.

## Monitor And Download

```bash
firecrawl monitor create --name "Blog" --goal "Notify me when a new post is published" --schedule "every 30 minutes" --page "https://example.com/blog"
firecrawl monitor list --limit 20
firecrawl monitor run "<monitorId>"
firecrawl monitor checks "<monitorId>" --limit 10
firecrawl monitor check "<monitorId>" "<checkId>" --page-status changed
firecrawl monitor update "<monitorId>" --state paused
firecrawl monitor delete "<monitorId>"
firecrawl experimental download "https://example.com/docs" --include-paths "/docs" --limit 100 --yes
```

Monitor creation can also read JSON from a file or stdin. Use JSON monitor payloads for structured change tracking schemas.
