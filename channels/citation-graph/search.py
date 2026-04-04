from __future__ import annotations

import functools
import importlib.util
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any


SearchFunction = Callable[..., Awaitable[list[dict[str, Any]]]]


@functools.lru_cache(maxsize=1)
def _load_semantic_scholar_search() -> SearchFunction:
    search_file = (
        Path(__file__).resolve().parent.parent / "semantic-scholar" / "search.py"
    )
    module_name = "channels._semantic_scholar_plugin"
    module = sys.modules.get(module_name)

    if module is None:
        spec = importlib.util.spec_from_file_location(module_name, search_file)
        if spec is None or spec.loader is None:
            raise ImportError("could not create semantic-scholar import spec")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

    search = getattr(module, "search", None)
    if not callable(search):
        raise ImportError("semantic-scholar search.py does not export search()")

    return search


async def search(query: str, max_results: int = 10) -> list[dict]:
    """Thin wrapper over semantic-scholar citation mode."""
    try:
        semantic_scholar_search = _load_semantic_scholar_search()
        return await semantic_scholar_search(query, max_results, mode="citations")
    except Exception as e:
        from lib.search_runner import SearchError

        raise SearchError(
            channel="citation-graph", error_type="network", message=str(e)
        ) from e
