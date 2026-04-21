import os
import socket

from tests.real_llm._claude import claude_code_unavailable_reason

_PROVIDER_ENV_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GOOGLE_API_KEY",
}
_PROVIDER_HOSTS = {
    "anthropic": "api.anthropic.com",
    "openai": "api.openai.com",
    "gemini": "generativelanguage.googleapis.com",
}


def provider_unavailable_reason(provider_name: str) -> str | None:
    if provider_name == "claude_code":
        return claude_code_unavailable_reason()

    env_var = _PROVIDER_ENV_VARS[provider_name]
    if not os.getenv(env_var):
        return f"{env_var} not set"

    host = _PROVIDER_HOSTS[provider_name]
    try:
        with socket.create_connection((host, 443), timeout=5):
            return None
    except OSError as exc:
        return f"network unavailable for {provider_name}: {exc}"
