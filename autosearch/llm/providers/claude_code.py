# Self-written, plan v2.3 § 1 decision 15
import asyncio
import json
import os
import shutil
from collections.abc import Iterable

from pydantic import BaseModel

_SUBPROCESS_ENV_KEYS = frozenset(
    {
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_BASE_URL",
        "HOME",
        "LANG",
        "PATH",
        "SHELL",
        "TERM",
        "TMPDIR",
        "USER",
    }
)
_SUBPROCESS_ENV_PREFIXES = ("CLAUDE_CODE_", "LC_", "XDG_")


def _minimal_subprocess_env(extra_keep: Iterable[str] = ()) -> dict[str, str]:
    keep = _SUBPROCESS_ENV_KEYS | frozenset(extra_keep)
    return {
        key: value
        for key, value in os.environ.items()
        if key in keep or any(key.startswith(prefix) for prefix in _SUBPROCESS_ENV_PREFIXES)
    }


class ClaudeCodeProvider:
    name = "claude_code"

    @staticmethod
    def is_available() -> bool:
        return shutil.which("claude") is not None

    async def complete(self, prompt: str, response_model: type[BaseModel]) -> str:
        if not self.is_available():
            raise RuntimeError("Claude Code provider is disabled because `claude` is not on PATH.")

        schema = json.dumps(response_model.model_json_schema(), indent=2, sort_keys=True)
        cli_prompt = (
            "Return only JSON that matches this schema exactly.\n"
            f"Schema:\n{schema}\n\n"
            f"Prompt:\n{prompt}"
        )
        process = await asyncio.create_subprocess_exec(
            "claude",
            "-p",
            cli_prompt,
            "--output-format",
            "json",
            env=_minimal_subprocess_env(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            message = stderr.decode().strip() or "claude command failed"
            raise RuntimeError(message)

        data = json.loads(stdout.decode())
        if isinstance(data, dict):
            if "result" in data:
                result = data["result"]
                return result if isinstance(result, str) else json.dumps(result)
            if "content" in data:
                content = data["content"]
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    return "".join(
                        part.get("text", "") for part in content if isinstance(part, dict)
                    )

        return data if isinstance(data, str) else json.dumps(data)
