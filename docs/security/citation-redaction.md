# Citation URL Redaction

> Status: enforced as of P0-3 fix (`fix/p0-3-citation-signed-url-redact`).
> `autosearch.core.citation_index.export_citations` redacts signed URL
> parameters by default; the MCP citation tools never expose a raw-URL
> opt-in.

## Threat model

A search session frequently produces evidence URLs that are **signed**
(time-limited, capability-bearing tokens embedded in query parameters):
S3 presigned downloads, GCS signed object URLs, Azure SAS, and arbitrary
APIs that pass `?token=…&Expires=…` for temporary access.

If the citation index stores these URLs raw and exports them to the
agent, the agent's transcript / log / downstream tool calls now carry a
working credential. Worse, the MCP `citation_add` tool used to echo the
URL straight back in its response, so a single signed URL in the
research stream propagated to:

- The agent's memory + transcript (visible to other tools / MCP servers).
- Any downstream tool that consumes citations.
- Logs, telemetry, and on-disk experience writes.

## Defense

Two pieces of infrastructure:

1. **`autosearch.core.redact.redact_signed_url(url) -> str`** —
   parses the URL, drops query parameters whose name (case-insensitive)
   appears in the signed-URL key set: `Signature`, `X-Amz-Signature`,
   `X-Goog-Signature`, `sig`, `token`, `Expires`, `X-Amz-Expires`,
   `X-Goog-Expires`, `X-Amz-Date`, `se`, `sp`, `sv`, `signature`. The
   path and remaining business parameters are preserved.
2. **`export_citations(index_id, *, raw_urls=False)`** —
   default `raw_urls=False` runs every URL through `redact_signed_url`
   before formatting the markdown reference list. `raw_urls=True` is
   the Python-only opt-in for callers that genuinely need the original
   URL (e.g. immediately re-issuing a download with the still-valid
   token).

## MCP boundary

The MCP `citation_add` and `citation_export` tools **always redact**.
Neither tool exposes a `raw_urls` parameter. External agents cannot
request raw signed URLs through MCP under any circumstance — the only
way to get a raw URL out of the citation index is via the in-process
Python API.

Why no opt-in at the MCP boundary: external agents are part of the
threat surface. A compromised or prompt-injected agent could request
raw URLs and exfiltrate them. The cost of removing the opt-in is
near-zero (no production caller needs raw URLs at the MCP boundary —
the in-process `pipeline_factory` or pipeline writers can use the
Python API directly when they do).

## Coverage

- `tests/unit/test_redact.py::TestRedactSignedUrl` — AWS SigV4, GCS,
  Azure SAS, generic token/signature/Expires regression.
- `tests/unit/test_citation_redact.py` — `export_citations` default-
  redact + `raw_urls=True` opt-in.
- `tests/unit/test_mcp_citation_redact.py` — MCP `citation_add` and
  `citation_export` always redact; tool signature does not accept
  `raw_urls`.

Source: `docs/security/autosearch-0426-p0-deep-scan-report.md` § P0-3.
