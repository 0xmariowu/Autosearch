# Self-written, plan v2.3 § 13.5 MCP Server (~1 day per plan)
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

import yaml
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

from autosearch.channels.base import Channel
from autosearch.core.channel_bootstrap import _build_channels
from autosearch.core.citation_index import _CITATION_INDEXES as _CI_STORE
from autosearch.core.citation_index import add_citation as _ci_add
from autosearch.core.citation_index import create_index as _ci_create
from autosearch.core.citation_index import export_citations as _ci_export
from autosearch.core.citation_index import merge_index as _ci_merge
from autosearch.core.clarify import Clarifier
from autosearch.core.loop_state import add_gap as _ls_add_gap
from autosearch.core.loop_state import get_gaps as _ls_get_gaps
from autosearch.core.loop_state import init_loop as _ls_init
from autosearch.core.loop_state import update_loop as _ls_update
from autosearch.core.models import ClarifyRequest, SearchMode, SubQuery
from autosearch.core.redact import redact_signed_url
from autosearch.core.search_scope import SearchScope, depth_to_mode
from autosearch.llm.client import LLMClient

_SKILLS_ROOT = Path(__file__).resolve().parents[1] / "skills"
# Subdirectories of autosearch/skills that host SKILL.md files at depth 1.
_SKILL_GROUPS = ("channels", "tools", "meta", "router")


class ResearchResponse(BaseModel):
    """Structured MCP tool response for the research tool."""

    content: str
    delivery_status: str
    channel_empty_calls: dict[str, int] = Field(default_factory=dict)
    routing_trace: dict[str, object] = Field(default_factory=dict)
    scope: dict[str, object]

    model_config = ConfigDict(extra="forbid")


class RunChannelResponse(BaseModel):
    """Structured MCP tool response for the run_channel tool.

    `status` discriminates the meaningful outcomes a host agent must distinguish:
      - `ok`: results returned (may be empty list)
      - `no_results`: channel ran successfully but found nothing for this query
      - `not_configured`: channel exists but its requirements (env keys,
        cookies, etc.) are not met. `unmet_requires` and `fix_hint` tell
        the agent exactly what to ask the user for.
      - `unknown_channel`: the requested name is not registered at all.
      - `auth_failed`: upstream rejected the request (401/403, expired cookie,
        invalid API key) — surface "your key looks invalid" to the user
        instead of letting it look like "no matches" (Bug 1 / fix-plan).
      - `rate_limited`: upstream returned 429 / explicit rate-limit signal —
        agent should backoff and retry rather than treating as a hard error.
      - `budget_exhausted`: paid quota / wallet is empty (TikHub 402, etc).
        Distinct from rate_limited because the fix is "top up balance",
        not "wait and retry" (Bug 3 / fix-plan v8 follow-up).
      - `transient_error`: retryable transport or upstream failure.
      - `channel_unavailable`: channel is configured, but no method is usable
        right now.
      - `channel_error`: any other unexpected failure.
    """

    channel: str
    ok: bool
    status: str = "ok"
    evidence: list[dict[str, object]] = Field(default_factory=list)
    reason: str | None = None
    unmet_requires: list[str] = Field(default_factory=list)
    fix_hint: str | None = None
    count_total: int = 0
    count_returned: int = 0

    model_config = ConfigDict(extra="forbid")


class ClarifyToolResponse(BaseModel):
    """Structured MCP tool response for the run_clarify tool."""

    query: str
    ok: bool
    need_clarification: bool = False
    question: str | None = None
    # Structured answer options for AskUserQuestion when need_clarification=true.
    # Empty list = free-text question; non-empty = show as option buttons.
    question_options: list[str] = Field(default_factory=list)
    verification: str | None = None
    mode: str | None = None
    query_type: str | None = None
    rubrics: list[str] = Field(default_factory=list)
    channel_priority: list[str] = Field(default_factory=list)
    channel_skip: list[str] = Field(default_factory=list)
    reason: str | None = None

    model_config = ConfigDict(extra="forbid")


async def _invoke_clarifier(
    query: str,
    mode_hint: SearchMode | None,
    *,
    clarifier: Clarifier | None = None,
    llm: LLMClient | None = None,
    channels: list[Channel] | None = None,
) -> ClarifyToolResponse:
    """Invoke the Clarifier and return a MCP-shaped response.

    Injectable dependencies for testing:
        clarifier, llm, channels
    """
    request = ClarifyRequest(query=query, mode_hint=mode_hint)
    used_clarifier = clarifier or Clarifier()
    used_llm = llm or LLMClient()
    used_channels = channels if channels is not None else _build_channels()

    try:
        result = await used_clarifier.clarify(
            request,
            used_llm,
            channels=used_channels,
        )
    except Exception as exc:  # noqa: BLE001 — boundary; return structured error
        from autosearch.core.redact import redact

        return ClarifyToolResponse(
            query=query,
            ok=False,
            reason=redact(f"clarify_error: {type(exc).__name__}: {exc}"),
        )

    return ClarifyToolResponse(
        query=query,
        ok=True,
        need_clarification=result.need_clarification,
        question=result.question,
        question_options=list(result.question_options),
        verification=result.verification,
        mode=result.mode.value if result.mode is not None else None,
        query_type=result.query_type,
        rubrics=[r.text for r in result.rubrics],
        channel_priority=list(result.channel_priority),
        channel_skip=list(result.channel_skip),
    )


async def _search_single_channel(
    channel: Channel,
    query: str,
    rationale: str,
) -> list[Any]:
    """Run a single channel's search and return Evidence objects.

    Raises on channel exception — callers should wrap.
    """

    subquery = SubQuery(text=query, rationale=rationale or query)
    return await channel.search(subquery)


_evidence_processor: Any = None


def _get_evidence_processor() -> Any:
    global _evidence_processor
    if _evidence_processor is None:
        from autosearch.core.evidence import EvidenceProcessor

        _evidence_processor = EvidenceProcessor()
    return _evidence_processor


class SkillSummary(BaseModel):
    """One skill entry returned by the list_skills tool."""

    name: str
    description: str
    path: str
    group: str
    layer: str | None = None
    domains: list[str] = Field(default_factory=list)
    scenarios: list[str] = Field(default_factory=list)
    model_tier: str | None = None
    auth_required: bool | None = None
    cost: str | None = None
    deprecated: bool = False

    model_config = ConfigDict(extra="ignore")


class SkillCatalogResponse(BaseModel):
    """Structured MCP tool response for the list_skills tool."""

    total: int
    skills: list[SkillSummary] = Field(default_factory=list)
    filtered_by: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


def _default_pipeline_factory() -> Any:
    """Default pipeline factory — raises to match post-W3.3-PR-D behavior.

    The legacy ``research()`` MCP tool short-circuits to a deprecation response
    BEFORE reaching this factory on the default path (no env var set). Only
    the opt-in ``AUTOSEARCH_LEGACY_RESEARCH=1`` env would reach this factory;
    when it does, raise immediately instead of constructing a dead Pipeline.

    Tests that exercise the legacy path should pass their own
    ``pipeline_factory`` into ``create_server`` rather than relying on this
    default. Retained as a function (not removed) so callers that reference
    it by name (e.g. monkeypatch in tests) still see a callable.
    """
    raise NotImplementedError(
        "The default pipeline factory is removed in v2 wave 3 PR E. "
        "Use list_skills + run_clarify + run_channel MCP tools, or "
        "pass a custom pipeline_factory to create_server() for test harnesses."
    )


def _parse_skill_md(path: Path, *, group: str) -> SkillSummary | None:
    """Parse a single SKILL.md file's YAML frontmatter into a SkillSummary.

    Returns None if the file cannot be parsed. Callers should skip rather
    than raise so a single malformed skill does not break the whole catalog.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None

    lines = raw.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == "---"), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return None

    frontmatter_text = "\n".join(lines[start + 1 : end]).strip()
    if not frontmatter_text:
        return None
    try:
        data = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None

    try:
        rel_path: str
        try:
            rel_path = str(path.parent.relative_to(_SKILLS_ROOT.parent))
        except ValueError:
            rel_path = str(path.parent)
        return SkillSummary(
            name=str(data.get("name") or path.parent.name),
            description=str(data.get("description") or ""),
            path=rel_path,
            group=group,
            layer=data.get("layer") if isinstance(data.get("layer"), str) else None,
            domains=list(data.get("domains") or []),
            scenarios=list(data.get("scenarios") or []),
            model_tier=data.get("model_tier") if isinstance(data.get("model_tier"), str) else None,
            auth_required=data.get("auth_required")
            if isinstance(data.get("auth_required"), bool)
            else None,
            cost=data.get("cost") if isinstance(data.get("cost"), str) else None,
            deprecated=bool(data.get("deprecated"))
            if data.get("deprecated") is not None
            else False,
        )
    except Exception:
        return None


def _scan_skill_catalog(
    *,
    skills_root: Path | None = None,
    group_filter: str = "",
    domain_filter: str = "",
    include_deprecated: bool = False,
) -> list[SkillSummary]:
    """Walk autosearch/skills/ and return SkillSummaries for every SKILL.md found.

    Scans the groups defined by `_SKILL_GROUPS`. For each group directory, scans
    direct child directories (leaf skills). `router/` is special-cased — its
    SKILL.md sits at the group root, not under a child leaf.
    """
    root = skills_root or _SKILLS_ROOT
    results: list[SkillSummary] = []
    if not root.is_dir():
        return results

    for group in _SKILL_GROUPS:
        group_dir = root / group
        if not group_dir.is_dir():
            continue
        if group_filter and group_filter != group:
            continue

        # router/ has SKILL.md at the group root
        if group == "router":
            skill_path = group_dir / "SKILL.md"
            if skill_path.is_file():
                summary = _parse_skill_md(skill_path, group=group)
                if summary is not None:
                    results.append(summary)
            continue

        # channels/ / tools/ / meta/ have SKILL.md under leaf child dirs
        for leaf_dir in sorted(p for p in group_dir.iterdir() if p.is_dir()):
            skill_path = leaf_dir / "SKILL.md"
            if not skill_path.is_file():
                continue
            summary = _parse_skill_md(skill_path, group=group)
            if summary is not None:
                results.append(summary)

    if domain_filter:
        results = [s for s in results if domain_filter in s.domains]
    if not include_deprecated:
        results = [s for s in results if not s.deprecated]

    return sorted(results, key=lambda s: (s.group, s.name))


def _health_required_tools() -> tuple[str, ...]:
    """Lazy import of the required-v2-tools list — kept on cli.main as the
    canonical home (mcp-check uses the same list)."""
    from autosearch.cli.main import _REQUIRED_MCP_TOOLS

    return _REQUIRED_MCP_TOOLS


def create_server(pipeline_factory: Callable[[], Any] | None = None) -> FastMCP:
    # Push ~/.config/ai-secrets.env keys into process env BEFORE any channel
    # method or LLM provider is constructed — otherwise their `os.getenv()`
    # calls miss keys the user configured via `autosearch configure`.
    from autosearch.core.secrets_store import inject_into_env

    inject_into_env()

    factory = pipeline_factory or _default_pipeline_factory
    server = FastMCP(
        name="autosearch",
        instructions=(
            "AutoSearch v2 tool supplier. Prefer the tool-supplier trio "
            "(list_skills, run_clarify, run_channel) for new integrations — "
            "the runtime AI drives channel selection and synthesis itself. "
            "The legacy research() tool runs the old pipeline and is "
            "deprecated (see docs/migration/legacy-research-to-tool-supplier.md)."
        ),
    )

    # Plan §P1-4: the deprecated `research` tool is registered only when the
    # user explicitly opts in via AUTOSEARCH_LEGACY_RESEARCH=1. By default the
    # MCP tool list does NOT advertise it — so a host agent cannot mis-pick
    # the v1 entry point over the v2 trio (list_skills + run_clarify + run_channel).
    import os as _os_research_gate

    _legacy_research_enabled = (
        _os_research_gate.environ.get("AUTOSEARCH_LEGACY_RESEARCH", "").strip() == "1"
    )
    _maybe_register = server.tool() if _legacy_research_enabled else (lambda f: f)

    @_maybe_register
    async def research(
        query: str,
        mode: Literal["fast", "deep"] = "fast",
        languages: Literal["all", "en_only", "zh_only", "mixed"] | None = None,
        depth: Literal["fast", "deep", "comprehensive"] | None = None,
        output_format: Literal["md", "html"] | None = None,
    ) -> ResearchResponse:
        """Run the legacy AutoSearch pipeline and return a structured response envelope.

        DEPRECATED under v2 tool-supplier architecture: prefer the trio
        (list_skills, run_clarify, run_channel) and let the runtime AI
        synthesize. This tool still works for backward compatibility but
        loses to bare `claude -p` on Gate 12 quality benchmarks because it
        wraps the runtime's strong synthesis with an older pipeline
        synthesizer.

        Migration guide: docs/migration/legacy-research-to-tool-supplier.md.
        """
        import os as _os
        import warnings as _warnings

        _warnings.warn(
            "autosearch.research() is deprecated. Use list_skills + run_clarify + "
            "run_channel and let the runtime AI synthesize. See "
            "docs/migration/legacy-research-to-tool-supplier.md.",
            DeprecationWarning,
            stacklevel=2,
        )

        scope = SearchScope(
            channel_scope=languages or "all",
            depth=depth or mode,
            output_format=output_format or "md",
        )

        # W3.3 PR A: by default, do NOT invoke the legacy pipeline. Return a
        # structured deprecation response pointing callers at the tool-supplier
        # trio. Legacy pipeline behaviour is preserved only when the opt-in
        # env var AUTOSEARCH_LEGACY_RESEARCH=1 is set (used by existing tests).
        legacy_opt_in = _os.environ.get("AUTOSEARCH_LEGACY_RESEARCH", "").strip() == "1"
        if not legacy_opt_in:
            return ResearchResponse(
                content=(
                    "[deprecated] The `research` MCP tool is deprecated under v2 "
                    "tool-supplier architecture. Use `list_skills` + `run_clarify` "
                    "+ `run_channel` and let the runtime AI synthesize the report. "
                    "Migration guide: docs/migration/legacy-research-to-tool-supplier.md"
                ),
                channel_empty_calls={},
                routing_trace={"deprecated": True},
                delivery_status="deprecated",
                scope=scope.model_dump(),
            )

        mode_hint = depth_to_mode(scope.depth)
        assert mode_hint is not None

        try:
            result = await factory().run(query, mode_hint=mode_hint, scope=scope)
        except Exception as exc:
            return ResearchResponse(
                content=f"[error] {exc}",
                channel_empty_calls={},
                routing_trace={},
                delivery_status="error",
                scope=scope.model_dump(),
            )

        if result.delivery_status == "needs_clarification":
            question = result.clarification.question or "More detail is required."
            return ResearchResponse(
                content=f"[clarification needed] {question}",
                channel_empty_calls=result.channel_empty_calls,
                routing_trace=result.routing_trace,
                delivery_status=result.delivery_status,
                scope=scope.model_dump(),
            )

        banner = _scope_banner(scope)
        markdown_text = result.markdown or ""
        if banner is not None:
            markdown_text = f"{banner}\n\n{markdown_text}" if markdown_text else banner

        return ResearchResponse(
            content=_render_output(
                markdown_text=markdown_text,
                title=query,
                output_format=scope.output_format,
            ),
            channel_empty_calls=result.channel_empty_calls,
            routing_trace=result.routing_trace,
            delivery_status=result.delivery_status,
            scope=scope.model_dump(),
        )

    @server.tool()
    def health() -> dict:
        """Return a structured health snapshot for MCP clients.

        Includes version, registered tool count, required-tool status, channel
        counts by status, secrets-file presence (key NAMES only), and a
        cooldown summary from the runtime ChannelHealth. All values are
        redacted before return — no key VALUES, no cookies, no token text.
        """
        from autosearch.core.channel_runtime import get_channel_runtime
        from autosearch.core.doctor import scan_channels
        from autosearch.core.redact import redact
        from autosearch.core.secrets_store import load_secrets, secrets_path

        snapshot: dict[str, object] = {"ok": True}
        try:
            from autosearch import __version__  # noqa: PLC0415

            snapshot["version"] = __version__
        except Exception:  # noqa: BLE001
            snapshot["version"] = "unknown"

        try:
            tools = list(server._tool_manager.list_tools())  # noqa: SLF001
            tool_names = {t.name for t in tools}
            snapshot["tool_count"] = len(tool_names)
            snapshot["required_tools_present"] = sorted(
                {n for n in _health_required_tools() if n in tool_names}
            )
            snapshot["required_tools_missing"] = sorted(
                {n for n in _health_required_tools() if n not in tool_names}
            )
        except Exception as exc:  # noqa: BLE001
            snapshot["tool_inspection_error"] = redact(f"{type(exc).__name__}: {exc}")

        try:
            statuses = scan_channels()
            counts: dict[str, int] = {"total": len(statuses), "ok": 0, "warn": 0, "off": 0}
            for s in statuses:
                counts[s.status] = counts.get(s.status, 0) + 1
            snapshot["channels"] = counts
        except Exception:  # noqa: BLE001
            snapshot["channels"] = {}

        try:
            secrets_keys = sorted(load_secrets().keys())
            snapshot["secrets_file"] = {
                "path": str(secrets_path()),
                "exists": secrets_path().is_file(),
                "key_count": len(secrets_keys),
                "key_names": secrets_keys,  # names only
            }
        except Exception:  # noqa: BLE001
            snapshot["secrets_file"] = {}

        try:
            runtime = get_channel_runtime()
            snapshot["channel_health_snapshot"] = runtime.health.snapshot()
        except Exception:  # noqa: BLE001
            snapshot["channel_health_snapshot"] = {}

        return snapshot

    @server.tool()
    def list_modes() -> dict:
        """List available search modes with their channel guidance.

        Returns the built-in research modes (academic, news, chinese_ugc,
        developer, product) plus any user-defined custom modes from
        ~/.config/autosearch/custom_modes.json.

        Each mode includes:
          - key: mode identifier to pass to run_clarify as mode_hint
          - label_zh / label_en: display name
          - keywords: phrases that trigger auto-detection
          - channel_priority: recommended channels for this mode
          - channel_skip: channels to avoid for this mode
        """
        from autosearch.core.search_modes import list_modes as _list_modes

        return {
            "modes": [
                {
                    "key": m.key,
                    "label_zh": m.label_zh,
                    "label_en": m.label_en,
                    "keywords": m.keywords[:6],
                    "channel_priority": m.channel_priority,
                    "channel_skip": m.channel_skip,
                    "is_system": m.is_system,
                }
                for m in _list_modes()
            ],
            "total": len(_list_modes()),
        }

    @server.tool()
    async def run_clarify(
        query: str,
        mode_hint: Literal["fast", "deep", "comprehensive"] | None = None,
    ) -> ClarifyToolResponse:
        """Run the autosearch clarifier on a user query, returning structured output.

        Part of the v2 tool-supplier architecture: the runtime AI uses this
        to decide whether to ask the user a clarifying question, and which
        channels / mode / rubrics to target if it proceeds. Autosearch does
        NOT run the full research pipeline here — it only produces the
        clarification envelope.

        Args:
            query: The user's research question, as-is.
            mode_hint: Optional preference for "fast" / "deep" /
                "comprehensive". If omitted, the clarifier picks.

        Returns:
            ClarifyToolResponse with:
              - need_clarification: True if runtime should ask the user first.
              - question: the clarifying question (if needed).
              - verification: acknowledgement text (if no clarification needed).
              - mode / query_type / rubrics / channel_priority / channel_skip
                as structured guidance for the runtime's next step.
        """
        from autosearch.core.search_modes import detect_mode

        parsed_mode = SearchMode(mode_hint) if mode_hint else None
        result = await _invoke_clarifier(query=query, mode_hint=parsed_mode)

        # Augment with search mode guidance (channel priority + system prompt hint)
        detected = detect_mode(query)
        if detected is not None:
            # Merge detected mode's channel guidance (clarifier result takes precedence)
            if not result.channel_priority and detected.channel_priority:
                result = result.model_copy(
                    update={
                        "channel_priority": detected.channel_priority,
                        "channel_skip": list(set(result.channel_skip) | set(detected.channel_skip)),
                    }
                )
            # Inject mode key so runtime AI knows which mode was detected
            if result.mode is None:
                result = result.model_copy(update={"mode": detected.key})

        return result

    @server.tool()
    async def run_channel(
        channel_name: str,
        query: str,
        rationale: str = "",
        k: int = 10,
    ) -> RunChannelResponse:
        """Run a single autosearch channel and return raw evidence.

        Part of the v2 tool-supplier architecture: autosearch does NOT
        synthesize, compact, or summarize — the runtime AI reads the
        evidence list and decides what to do (quote, cite, follow up,
        ignore). Use `list_skills(group="channels")` to discover valid
        `channel_name` values.

        Args:
            channel_name: One of the autosearch channel skill names, e.g.
                "bilibili", "arxiv", "github", "xiaohongshu".
            query: The search text.
            rationale: Optional short rationale (defaults to `query` if empty).
                Used by some channels to tune ranking.
            k: Max number of Evidence items to return (latest first). Default 10.

        Returns:
            RunChannelResponse with `ok: bool`, `evidence: list[dict]`
            (up to k items; each evidence is already source_page-slimmed),
            `reason` populated on failure, and `count_total / count_returned`.
        """
        from autosearch.core.channel_runtime import get_channel_runtime

        runtime = get_channel_runtime()
        channels = runtime.channels
        registry = runtime.registry
        matched = next((c for c in channels if c.name == channel_name), None)
        if matched is None:
            # Differentiate "channel name typo" (unknown_channel) from "channel
            # exists but its requirements aren't met" (not_configured). The
            # latter must surface fix_hint + unmet_requires so the host agent
            # can ask the user for the missing key instead of falling back.
            if registry is not None and channel_name in registry._metadata:  # noqa: SLF001
                meta = registry.metadata(channel_name)
                unmet: list[str] = []
                for method in meta.methods:
                    unmet.extend(method.unmet_requires)
                unmet = list(dict.fromkeys(unmet))
                from autosearch.core.doctor import _resolve_fix_hint

                fix = _resolve_fix_hint(meta, unmet)
                return RunChannelResponse(
                    channel=channel_name,
                    ok=False,
                    status="not_configured",
                    reason=f"not_configured: {channel_name} known but requirements unmet",
                    unmet_requires=unmet,
                    fix_hint=fix or None,
                )
            available = ", ".join(sorted(c.name for c in channels))[:500]
            return RunChannelResponse(
                channel=channel_name,
                ok=False,
                status="unknown_channel",
                reason=f"unknown_channel. available: {available}",
            )

        from datetime import UTC, datetime

        from autosearch.core.channel_status import exception_to_channel_status
        from autosearch.core.experience_compact import compact
        from autosearch.core.experience_privacy import query_shape
        from autosearch.skills.experience import (
            append_event,
            load_experience_digest,
            should_compact,
        )

        digest = load_experience_digest(channel_name)
        search_rationale = rationale
        if digest is not None:
            search_rationale = f"{rationale}\n\n[Experience Digest]\n{digest}"

        try:
            slim = await _search_single_channel(matched, query, search_rationale)
        except Exception as exc:  # noqa: BLE001 — boundary; report reason, don't leak
            append_event(
                channel_name,
                {
                    "skill": channel_name,
                    "channel": channel_name,
                    "query_shape": query_shape(query, channel=channel_name, outcome="error"),
                    "outcome": "error",
                    "count_returned": 0,
                    "count_total": 0,
                    "ts": datetime.now(UTC).isoformat(),
                },
            )
            if should_compact(channel_name):
                compact(channel_name)
            failure = exception_to_channel_status(exc)
            return RunChannelResponse(
                channel=channel_name,
                ok=False,
                status=failure.status,
                reason=failure.reason,
                unmet_requires=failure.unmet_requires,
                fix_hint=failure.fix_hint,
            )

        # Quality pipeline: URL dedup → SimHash near-dedup → BM25 relevance rerank
        k = max(1, int(k)) if k else 10
        proc = _get_evidence_processor()
        slim = proc.dedup_urls(slim)
        slim = proc.dedup_simhash(slim)
        total = len(slim)  # count after dedup, before k cutoff
        slim = proc.rerank_bm25(slim, query, top_k=k)
        returned = [ev.to_context_dict() for ev in slim]
        append_event(
            channel_name,
            {
                "skill": channel_name,
                "channel": channel_name,
                "query_shape": query_shape(query, channel=channel_name, outcome="success"),
                "outcome": "success",
                "count_returned": len(returned),
                "count_total": total,
                "ts": datetime.now(UTC).isoformat(),
            },
        )
        if should_compact(channel_name):
            compact(channel_name)
        return RunChannelResponse(
            channel=channel_name,
            ok=True,
            status="ok" if returned else "no_results",
            evidence=returned,
            count_total=total,
            count_returned=len(returned),
        )

    @server.tool()
    def list_skills(
        group: str = "",
        domain: str = "",
        include_deprecated: bool = False,
    ) -> SkillCatalogResponse:
        """List autosearch skills with their frontmatter metadata.

        Part of the v2 tool-supplier architecture: the runtime AI calls this
        to discover what autosearch can do, then picks and invokes the leaf
        skills it needs. Returns static metadata only — this does not run
        any skill. See also: `autosearch:router` SKILL.md for how to pick
        groups before reading leaf skills.

        Args:
            group: Filter by group ("channels", "tools", "meta", "router").
                   Empty string = all groups.
            domain: Filter by domain tag (e.g. "chinese-ugc", "web-fetch",
                    "academic"). Empty string = no domain filter.
            include_deprecated: If True, include skills marked
                `deprecated: true` in their frontmatter. Defaults to False
                so callers don't accidentally discover wave-3 removal targets.
        """
        summaries = _scan_skill_catalog(
            group_filter=group or "",
            domain_filter=domain or "",
            include_deprecated=include_deprecated,
        )
        filtered: dict[str, str] = {}
        if group:
            filtered["group"] = group
        if domain:
            filtered["domain"] = domain
        if include_deprecated:
            filtered["include_deprecated"] = "true"
        return SkillCatalogResponse(
            total=len(summaries),
            skills=summaries,
            filtered_by=filtered,
        )

    # F006: reflective search loop state
    @server.tool()
    def loop_init() -> dict:
        """Initialize a reflective search loop. Returns {state_id}."""
        return {"state_id": _ls_init()}

    @server.tool()
    def loop_update(state_id: str, evidence: list[dict], query: str) -> dict:
        """Update loop state with evidence from run_channel. Returns state summary."""
        try:
            return _ls_update(state_id, evidence, query)
        except KeyError:
            return {"ok": False, "reason": "invalid_state_id", "state_id": state_id}

    @server.tool()
    def loop_get_gaps(state_id: str) -> dict:
        """Get coverage gaps for this loop. Returns {state_id, gaps}."""
        try:
            return {"state_id": state_id, "gaps": _ls_get_gaps(state_id)}
        except KeyError:
            return {"ok": False, "reason": "invalid_state_id", "state_id": state_id}

    @server.tool()
    def loop_add_gap(state_id: str, gap: str) -> dict:
        """Mark a topic as a coverage gap. Returns {state_id, gaps}."""
        try:
            _ls_add_gap(state_id, gap)
            return {"state_id": state_id, "gaps": _ls_get_gaps(state_id)}
        except KeyError:
            return {"ok": False, "reason": "invalid_state_id", "state_id": state_id}

    # F007: citation index
    @server.tool()
    def citation_create() -> dict:
        """Create a citation index for a research session. Returns {index_id}."""
        return {"index_id": _ci_create()}

    @server.tool()
    def citation_add(index_id: str, url: str, title: str = "", source: str = "") -> dict:
        """Add URL to citation index (idempotent). Returns {index_id, citation_number, url}."""
        try:
            num = _ci_add(index_id, url, title=title, source=source)
        except KeyError:
            return {"ok": False, "reason": "invalid_index_id", "index_id": index_id}
        return {"index_id": index_id, "citation_number": num, "url": redact_signed_url(url)}

    @server.tool()
    def citation_export(index_id: str) -> dict:
        """Export citations as Markdown. Returns {index_id, markdown, count}."""
        try:
            markdown = _ci_export(index_id)
            count = len(_CI_STORE[index_id]._entries)
        except KeyError:
            return {"ok": False, "reason": "invalid_index_id", "index_id": index_id}
        return {"index_id": index_id, "markdown": markdown, "count": count}

    @server.tool()
    def citation_merge(target_id: str, source_id: str) -> dict:
        """Merge source citation index into target. Returns {merged_count, skipped_duplicates}."""
        try:
            return _ci_merge(target_id, source_id)
        except KeyError as exc:
            missing = str(exc).strip("'\"")
            which = "target_id" if missing == target_id else "source_id"
            return {
                "ok": False,
                "reason": f"invalid_{which}",
                "target_id": target_id,
                "source_id": source_id,
            }

    # F004: group-first channel selection
    @server.tool()
    def select_channels_tool(
        query: str,
        channel_priority: list[str] | None = None,
        channel_skip: list[str] | None = None,
        mode: str = "fast",
    ) -> dict:
        """Select 3-8 channels using group-first two-stage algorithm.

        Call after run_clarify to get a ranked channel list before run_channel.
        Returns {groups, channels, rationale}.
        """
        from autosearch.core.channel_select import select_channels  # noqa: PLC0415

        return select_channels(
            query,
            channel_priority=channel_priority,
            channel_skip=channel_skip,
            mode=mode,
        )

    # F005: parallel multi-channel subtask delegation
    @server.tool()
    async def delegate_subtask(
        task_description: str,
        channels: list[str],
        query: str,
        max_per_channel: int = 5,
    ) -> dict:
        """Run a query across multiple channels concurrently.

        Use when you want to search several channels in parallel for the same query.
        Returns {evidence_by_channel, summary, failed_channels, failed_channel_details, budget_used}.
        """
        from autosearch.core.delegate import run_subtask  # noqa: PLC0415

        result = await run_subtask(task_description, channels, query, max_per_channel)
        return {
            "evidence_by_channel": result.evidence_by_channel,
            "summary": result.summary,
            "failed_channels": result.failed_channels,
            "failed_channel_details": result.failed_channel_details,
            "budget_used": result.budget_used,
        }

    # F009: channel health scanner
    @server.tool()
    def doctor() -> dict:
        """Scan all configured channels and return their health status with fix hints.

        Returns a structured report grouped by tier:
          - tier 0: zero-config (works out of the box)
          - tier 1: needs API key
          - tier 2: needs login / cookie  (run: autosearch login <platform>)

        Each channel includes a fix_hint — a one-line command to resolve the issue.
        Use this to diagnose which channels are missing API keys or credentials.
        """
        from autosearch.core.doctor import format_report, scan_channels  # noqa: PLC0415

        results = scan_channels()
        ok_count = sum(1 for r in results if r.status == "ok")
        return {
            "summary": f"{ok_count}/{len(results)} channels available",
            "report": format_report(results),
            "channels": [
                {
                    "channel": s.channel,
                    "status": s.status,
                    "tier": s.tier,
                    "message": s.message,
                    "fix_hint": s.fix_hint,
                    "unmet_requires": s.unmet_requires,
                }
                for s in results
            ],
        }

    # G1: channel capability directory (status + availability in one call)
    @server.tool()
    def list_channels(status_filter: str = "") -> dict:
        """List all channels with their runtime availability status.

        Unlike list_skills (which returns SKILL.md metadata), list_channels
        returns the live status of each channel: whether it's usable right
        now based on the current environment's API keys and credentials.

        Args:
            status_filter: Optional filter — "ok", "warn", or "off".
                           Empty string returns all channels.

        Returns:
            {total, ok_count, warn_count, off_count, channels: [{name, status, message, unmet_requires}]}
        """
        from autosearch.core.doctor import scan_channels  # noqa: PLC0415

        all_channels = scan_channels()
        if status_filter:
            filtered = [s for s in all_channels if s.status == status_filter]
        else:
            filtered = all_channels

        # Sort: ok first, then warn, then off
        order = {"ok": 0, "warn": 1, "off": 2}
        filtered.sort(key=lambda s: (order.get(s.status, 3), s.channel))

        return {
            "total": len(filtered),
            "ok_count": sum(1 for s in all_channels if s.status == "ok"),
            "tier0_count": sum(1 for s in all_channels if s.tier == 0 and s.status == "ok"),
            "tier1_count": sum(1 for s in all_channels if s.tier == 1 and s.status == "ok"),
            "tier2_count": sum(1 for s in all_channels if s.tier == 2 and s.status == "ok"),
            "warn_count": sum(1 for s in all_channels if s.status == "warn"),
            "off_count": sum(1 for s in all_channels if s.status == "off"),
            "channels": [
                {
                    "name": s.channel,
                    "status": s.status,
                    "tier": s.tier,
                    "message": s.message,
                    "fix_hint": s.fix_hint,
                    "unmet_requires": s.unmet_requires,
                }
                for s in filtered
            ],
        }

    # F010: workflow skills
    @server.tool()
    def trace_harvest(
        channel: str,
        query: str,
        count_returned: int = 0,
        count_total: int = 0,
        outcome: str = "success",
    ) -> list[dict]:
        """Extract winning query patterns from a run_channel trace.

        Pass the channel name, query, and result counts from a run_channel call.
        Returns a list of {query, channel, score} pattern dicts (empty if score < 0.5).
        Write results to the channel's patterns.jsonl to accumulate learning.
        """
        from autosearch.core.trace_harvest import extract_winning_patterns  # noqa: PLC0415

        trace = {
            "channel": channel,
            "query": query,
            "count_returned": count_returned,
            "count_total": count_total,
            "outcome": outcome,
        }
        patterns = extract_winning_patterns(trace)
        return [{"query": p.query, "channel": p.channel, "score": p.score} for p in patterns]

    @server.tool()
    def perspective_questioning(topic: str, n: int = 4) -> list[dict]:
        """Generate n sub-questions covering different viewpoints on a topic.

        Viewpoints: user (practitioner), expert (domain), critic (skeptic),
        competitor (alternatives). n is clamped to [1, 4].
        Returns list of {viewpoint, question} dicts.
        """
        from autosearch.core.perspective_questioning import generate_perspectives  # noqa: PLC0415

        subs = generate_perspectives(topic, n)
        return [{"viewpoint": s.viewpoint, "question": s.question} for s in subs]

    @server.tool()
    def graph_search_plan(subtasks: list[dict]) -> list[list[str]]:
        """Build a DAG from subtasks and return topologically sorted parallel batches.

        Each subtask dict: {id, description, depends_on?: [id, ...]}.
        Returns list of batches; subtasks in the same batch can run in parallel.
        Raises on unknown dependency references or cycles.
        """
        from autosearch.core.graph_search_plan import SearchGraph, SubTask, get_parallel_batches  # noqa: PLC0415

        nodes = [
            SubTask(
                id=str(t["id"]),
                description=str(t.get("description") or ""),
                depends_on=[str(d) for d in (t.get("depends_on") or [])],
            )
            for t in subtasks
        ]
        return get_parallel_batches(SearchGraph(nodes=nodes))

    @server.tool()
    def recent_signal_fusion(evidence: list[dict], days: int = 30) -> list[dict]:
        """Filter evidence to items published within the last `days` days, newest first.

        Looks for date in keys: date, published_at, created_at, ts, timestamp.
        Items with no parseable date are excluded.
        """
        from autosearch.core.recent_signal_fusion import filter_recent  # noqa: PLC0415

        return filter_recent(evidence, days)

    @server.tool()
    def context_retention_policy(evidence: list[dict], token_budget: int) -> list[dict]:
        """Trim evidence list to fit within token_budget, keeping highest-scored items.

        Token estimate: len(str(item)) // 4 per item.
        Items sorted by 'score' field descending before trimming.
        """
        from autosearch.core.context_retention_policy import trim_to_budget  # noqa: PLC0415

        return trim_to_budget(evidence, token_budget)

    @server.tool()
    def consolidate_research(evidence: list[dict], query: str, top_k: int = 5) -> dict:
        """Compress accumulated evidence into a compact research brief.

        Use this when a research session has accumulated many evidence items
        (from multiple run_channel calls) and the context is getting large.
        Deduplicates, reranks by relevance to query, and formats a brief summary.

        Args:
            evidence: Combined list of evidence dicts from run_channel / delegate_subtask.
            query: The original research question (used for relevance ranking).
            top_k: Max items to keep in the brief (default 5).

        Returns:
            {
              total_processed: int,
              kept: int,
              top_evidence: list[dict],
              source_coverage: {channel: count},
              brief_text: "Markdown summary of key findings",
            }
        """
        from autosearch.core.context_compression import compress_evidence  # noqa: PLC0415

        return compress_evidence(evidence, query, top_k=top_k)

    return server


def _scope_banner(scope: SearchScope) -> str | None:
    default_scope = SearchScope()
    parts: list[str] = []
    if scope.channel_scope != default_scope.channel_scope:
        parts.append(f"languages={scope.channel_scope}")
    if scope.depth != default_scope.depth:
        parts.append(f"depth={scope.depth}")
    if scope.output_format != default_scope.output_format:
        parts.append(f"format={scope.output_format}")
    if not parts:
        return None
    return "[scope] " + " ".join(parts)


def _render_output(markdown_text: str, title: str, output_format: str) -> str:
    if output_format == "html":
        return _render_html(markdown_text=markdown_text, title=title)
    return markdown_text


def _render_html(markdown_text: str, title: str) -> str:
    import html as html_lib

    try:
        import markdown as md
    except ImportError as exc:
        try:
            from markdown_it import MarkdownIt
        except ImportError:
            raise RuntimeError("markdown package is required for HTML output") from exc
        body = MarkdownIt("js-default").render(markdown_text or "")
    else:
        body = md.markdown(markdown_text or "", extensions=["tables", "fenced_code"])
    safe_title = html_lib.escape(title)
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        '<head><meta charset="utf-8"><title>{title}</title></head>\n'
        "<body><article>\n{body}\n</article></body>\n"
        "</html>\n"
    ).format(title=safe_title, body=body)
