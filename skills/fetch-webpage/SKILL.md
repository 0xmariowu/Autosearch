---
name: fetch-webpage
description: "Use when snippets are insufficient and you need the full content of an article, README, documentation page, or post for deeper reading and knowledge extraction."
---

# Purpose

Search snippets are often enough to rank, but not enough to learn.
Use this skill when you need the full page content so `extract-knowledge.md` can mine it properly.
Also use for date extraction, citation verification, and outlink discovery.

# When To Use It

Fetch the full page when:

- the snippet suggests high relevance but lacks detail
- you need the actual argument, method, code example, or limitation section
- a README or docs page likely contains implementation detail not visible in search results
- two sources appear to contradict each other and the snippet is too shallow to resolve it
- you need to extract outlinks for follow-links.md
- date metadata is missing and the page likely has publication date in its HTML

Do not fetch everything.
Fetch the pages whose full text is likely to change your understanding.
Budget: at most 10-15 page fetches per search session.

# Retrieval Methods (Priority Order)

1. **WebFetch tool** if available in Claude Code — simplest, returns readable content
2. **Jina Reader** via `https://r.jina.ai/{url}` — good markdown conversion, handles most sites
3. **curl + extraction** — fallback when other options are unavailable

Choose the path that yields clean readable content with minimal noise.

# Content Types

## HTML Pages (default)
- Extract main content, strip navigation, ads, sidebars
- Preserve: title, headings, paragraphs, lists, code blocks, tables
- Strip: cookie banners, footer links, social share buttons, related articles

## PDF Documents
- arXiv papers, whitepapers, documentation PDFs
- Extract text content, preserve section headings
- Focus on abstract, introduction, methodology, and conclusion for research papers
- Do not attempt to process scanned/image PDFs

## GitHub READMEs
- Fetch raw markdown via `https://raw.githubusercontent.com/{owner}/{repo}/main/README.md`
- This avoids GitHub's HTML wrapper and gives clean markdown directly
- Also try `/HEAD/README.md` if `/main/` fails

# Blocked Content Detection

Some pages block automated access. Detect and handle:

- **403/401 responses** → skip, do not retry
- **CAPTCHA pages** → skip, note as blocked
- **Login walls** → skip, do not attempt authentication
- **JavaScript-only rendering** → try Jina Reader (it renders JS), skip if that fails too
- **Rate limiting (429)** → wait and retry once, then skip

When blocked, do not count the page as "fetched." Note it as inaccessible so follow-up decisions account for the missing content.

# Fallback Strategy

If the primary method fails:
1. Try the next method in the priority list
2. If all methods fail, keep the snippet-only version of the result
3. Do not spend more than 2 attempts per URL

# Output Shape

Produce clean markdown or similarly readable text.
Preserve important structure:

- title
- headings
- paragraphs
- lists
- code blocks when they matter

# What To Store

Store the fetched content so later skills can reuse it without refetching:

- source URL
- fetch method used
- fetch timestamp
- cleaned content (markdown)
- any extracted metadata (publication date, author, last modified)

Pass the content to extract-knowledge.md for knowledge extraction.
Pass extracted dates to extract-dates.md for freshness metadata.
Pass outlinks to follow-links.md when the page is a hub/collection.

# Quality Bar

This skill is successful when a previously shallow result becomes readable enough to support real understanding, citation, or extraction.
A failed fetch should be noted, not silently dropped.
