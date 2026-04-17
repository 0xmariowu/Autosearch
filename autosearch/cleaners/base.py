# Self-written, plan v2.3 § 13.5 M4
from typing import Protocol


class Cleaner(Protocol):
    def clean(self, html: str) -> str | None: ...
