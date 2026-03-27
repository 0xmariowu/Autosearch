"""Capability registry — auto-discovers and dispatches capabilities."""

import importlib
from pathlib import Path
from typing import Any

_MANIFEST_CACHE: list[dict[str, str]] | None = None
_MODULE_CACHE: dict[str, Any] = {}


def _capability_dir() -> Path:
    return Path(__file__).parent


def _load_module(name: str):
    if name not in _MODULE_CACHE:
        _MODULE_CACHE[name] = importlib.import_module(f"capabilities.{name}")
    return _MODULE_CACHE[name]


def load_manifest(force: bool = False) -> list[dict[str, str]]:
    """Scan capabilities/ and return manifest of all registered capabilities."""
    global _MANIFEST_CACHE
    if _MANIFEST_CACHE is not None and not force:
        return list(_MANIFEST_CACHE)
    manifest = []
    for file in sorted(_capability_dir().glob("*.py")):
        if file.name.startswith("_"):
            continue
        try:
            mod = _load_module(file.stem)
            manifest.append(
                {
                    "name": getattr(mod, "name", file.stem),
                    "description": getattr(mod, "description", ""),
                    "when": getattr(mod, "when", ""),
                    "input_type": getattr(mod, "input_type", "any"),
                    "output_type": getattr(mod, "output_type", "any"),
                }
            )
        except Exception as exc:
            manifest.append(
                {
                    "name": file.stem,
                    "description": f"LOAD ERROR: {exc}",
                    "when": "",
                    "input_type": "any",
                    "output_type": "any",
                }
            )
    _MANIFEST_CACHE = manifest
    return list(manifest)


def dispatch(name: str, input_data: Any = None, **context: Any) -> Any:
    """Call a capability by name."""
    mod = _load_module(name)
    return mod.run(input_data, **context)


def manifest_text() -> str:
    """Generate AI-readable manifest for LLM prompt injection."""
    lines = []
    for cap in load_manifest():
        lines.append(
            f"- **{cap['name']}** ({cap['input_type']} -> {cap['output_type']})"
        )
        lines.append(f"  {cap['description']}")
        lines.append(f"  Use when: {cap['when']}")
    return "\n".join(lines)


def manifest_json() -> list[dict[str, Any]]:
    """Generate tool-use compatible definitions for LLM."""
    tools = []
    for cap in load_manifest():
        if "LOAD ERROR" in cap.get("description", ""):
            continue
        # Try to get capability-specific schema
        try:
            mod = _load_module(cap["name"])
            schema = getattr(mod, "input_schema", None)
        except Exception:
            schema = None

        if not schema:
            schema = {
                "type": "object",
                "properties": {
                    "input": {"description": f"Input type: {cap['input_type']}"},
                    "context": {
                        "description": "Additional parameters",
                        "type": "object",
                    },
                },
            }

        tools.append(
            {
                "name": cap["name"],
                "description": f"{cap['description']} Use when: {cap['when']}",
                "input_schema": schema,
            }
        )
    return tools


def available_capabilities(
    context: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """Return only capabilities whose health_check passes."""
    result = []
    for cap in load_manifest():
        if "LOAD ERROR" in cap.get("description", ""):
            continue
        try:
            mod = _load_module(cap["name"])
            if hasattr(mod, "health_check"):
                health = mod.health_check()
                if health.get("status") == "off":
                    continue
        except Exception:
            continue
        result.append(cap)
    return result


def run_all_tests() -> dict[str, str]:
    """Run self-tests for all capabilities."""
    results = {}
    for file in sorted(_capability_dir().glob("*.py")):
        if file.name.startswith("_"):
            continue
        stem = file.stem
        try:
            mod = _load_module(stem)
            if hasattr(mod, "test"):
                results[stem] = mod.test()
            else:
                results[stem] = "no_test"
        except Exception as exc:
            results[stem] = f"FAIL: {exc}"
    return results
