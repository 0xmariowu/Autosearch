"""Search mesh backend wrappers."""

from search_mesh.registry import register_provider

from .ddgs_backend import DDGSBackend
from .github_backend import GitHubBackend
from .searxng_backend import SearXNGBackend
from .web_backend import WebBackend

__all__ = [
    "DDGSBackend",
    "GitHubBackend",
    "SearXNGBackend",
    "WebBackend",
    "register_builtin_providers",
]


def register_builtin_providers() -> None:
    register_provider(SearXNGBackend())
    register_provider(DDGSBackend())
    register_provider(GitHubBackend())
    register_provider(WebBackend())
