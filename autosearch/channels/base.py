# Source: agent-reach/channels/base.py:L1-L37 (adapted)
from typing import Protocol

from autosearch.core.models import Evidence, SubQuery


class Channel(Protocol):
    name: str

    async def search(self, query: SubQuery) -> list[Evidence]: ...


class ChannelRegistry:
    def __init__(self) -> None:
        self._channels: dict[str, Channel] = {}

    def register(self, channel: Channel) -> None:
        self._channels[channel.name] = channel

    def get(self, name: str) -> Channel:
        return self._channels[name]

    def all_channels(self) -> list[Channel]:
        return list(self._channels.values())
