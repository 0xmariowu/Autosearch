# Self-written, plan v2.3 § 13.5
from collections.abc import Callable

from autosearch.channels.base import Channel
from autosearch.core.models import Evidence, SubQuery


class FakeChannel(Channel):
    def __init__(
        self,
        name: str,
        evidences: list[Evidence] | None = None,
        factory: Callable[[SubQuery], list[Evidence]] | None = None,
    ) -> None:
        self.name = name
        self._evidences = list(evidences or [])
        self._factory = factory
        self.call_count = 0
        self.queries: list[SubQuery] = []

    async def search(self, query: SubQuery) -> list[Evidence]:
        self.call_count += 1
        self.queries.append(query)
        if self._factory is not None:
            return list(self._factory(query))
        return list(self._evidences)
