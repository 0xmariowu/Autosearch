from __future__ import annotations

import inspect

from autosearch.core.delegate import run_subtask


def test_run_subtask_requires_channel_runtime() -> None:
    signature = inspect.signature(run_subtask)
    channel_runtime = signature.parameters.get("channel_runtime")

    assert channel_runtime is not None
    assert channel_runtime.default is inspect.Parameter.empty
