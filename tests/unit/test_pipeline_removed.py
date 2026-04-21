"""Verify Pipeline + ReportSynthesizer are gutted post-W3.3 PR D.

Historical context: the full autosearch pipeline (clarify → decompose →
channel fan-out → m3 compaction → m7 synthesis) was deleted in v2 wave 3.
Pipeline and ReportSynthesizer remain as stub classes so legacy imports
don't break, but any ``run()`` / ``synthesize()`` call raises
``NotImplementedError`` pointing at the v2 trio.
"""

from __future__ import annotations

import pytest

from autosearch.core.pipeline import Pipeline, PipelineEvent, PipelineResult
from autosearch.synthesis.report import ReportSynthesizer


def test_pipeline_is_importable() -> None:
    """Pipeline class is still importable so legacy callers don't crash at import."""
    assert Pipeline is not None
    assert callable(Pipeline)


def test_pipeline_event_is_importable() -> None:
    """PipelineEvent dataclass retained for import-compat; can be instantiated."""
    event = PipelineEvent(name="test", payload={"k": 1})
    assert event.name == "test"
    assert event.payload == {"k": 1}


def test_pipeline_result_is_importable() -> None:
    """PipelineResult still comes from models via re-export; tests depending on it still build."""
    assert PipelineResult is not None


def test_pipeline_init_accepts_any_legacy_signature() -> None:
    """Pipeline.__init__ must accept legacy kwargs (llm, channels, ...) without crashing."""

    class _FakeLLM:
        pass

    pipeline = Pipeline(llm=_FakeLLM(), channels=[], extra_arg="ignored")
    assert pipeline is not None


@pytest.mark.asyncio
async def test_pipeline_run_raises_not_implemented() -> None:
    """Pipeline.run() must raise NotImplementedError pointing at the v2 trio."""
    pipeline = Pipeline()
    with pytest.raises(NotImplementedError) as exc_info:
        await pipeline.run("sample query")

    message = str(exc_info.value)
    assert "Pipeline is removed" in message
    assert "list_skills" in message
    assert "run_clarify" in message
    assert "run_channel" in message
    assert "migration" in message.lower()


def test_report_synthesizer_is_importable() -> None:
    """ReportSynthesizer class is still importable (legacy compat)."""
    synth = ReportSynthesizer(llm=None, outline=None)
    assert synth is not None


@pytest.mark.asyncio
async def test_report_synthesizer_synthesize_raises_not_implemented() -> None:
    """ReportSynthesizer.synthesize() must raise NotImplementedError."""
    synth = ReportSynthesizer()
    with pytest.raises(NotImplementedError) as exc_info:
        await synth.synthesize()
    message = str(exc_info.value)
    assert "ReportSynthesizer is removed" in message
    assert "list_skills" in message


def test_deleted_modules_are_gone() -> None:
    """The 4 pipeline-internal modules must no longer be importable."""
    # iteration.py / context_compaction.py / delegation.py / synthesis/section.py
    # were all deleted. Importing them must raise ModuleNotFoundError.
    import importlib

    for mod in (
        "autosearch.core.iteration",
        "autosearch.core.context_compaction",
        "autosearch.core.delegation",
        "autosearch.synthesis.section",
    ):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(mod)
