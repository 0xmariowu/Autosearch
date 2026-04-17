# Self-written, plan v2.3 § W2 dummy provider
import json
from typing import Any

from pydantic import BaseModel


class DummyProvider:
    """Schema-driven provider used by smoke tests and CI without API keys."""

    name = "dummy"
    model = "dummy"

    async def complete(self, prompt: str, response_model: type[BaseModel]) -> str:
        _ = prompt
        schema = response_model.model_json_schema()
        payload = _schema_value(schema, root_schema=schema)
        return json.dumps(payload)


def _schema_value(
    schema: dict[str, Any],
    *,
    root_schema: dict[str, Any],
    field_name: str | None = None,
) -> Any:
    resolved = _resolve_schema(schema, root_schema)

    if "const" in resolved:
        return resolved["const"]

    if "enum" in resolved:
        return resolved["enum"][0]

    if "anyOf" in resolved:
        return _union_value(resolved["anyOf"], root_schema=root_schema, field_name=field_name)

    if "oneOf" in resolved:
        return _union_value(resolved["oneOf"], root_schema=root_schema, field_name=field_name)

    if "allOf" in resolved:
        return _all_of_value(resolved["allOf"], root_schema=root_schema, field_name=field_name)

    schema_type = resolved.get("type")

    if schema_type == "object" or "properties" in resolved:
        return _object_value(resolved, root_schema=root_schema)

    if schema_type == "array":
        return _array_value(resolved, root_schema=root_schema, field_name=field_name)

    if schema_type == "string":
        return _string_value(field_name)

    if schema_type == "boolean":
        return False

    if schema_type == "integer":
        return 0

    if schema_type == "number":
        return 0.0

    if schema_type == "null":
        return None

    if isinstance(schema_type, list):
        for candidate in schema_type:
            if candidate != "null":
                return _schema_value(
                    {**resolved, "type": candidate},
                    root_schema=root_schema,
                    field_name=field_name,
                )
        return None

    return _string_value(field_name)


def _resolve_schema(schema: dict[str, Any], root_schema: dict[str, Any]) -> dict[str, Any]:
    if "$ref" not in schema:
        return schema

    ref = schema["$ref"]
    if not isinstance(ref, str) or not ref.startswith("#/"):
        raise ValueError(f"Unsupported schema reference: {ref!r}")

    target: Any = root_schema
    for part in ref.removeprefix("#/").split("/"):
        target = target[part]

    if not isinstance(target, dict):
        raise ValueError(f"Schema reference did not resolve to an object: {ref!r}")

    merged = dict(target)
    for key, value in schema.items():
        if key != "$ref":
            merged[key] = value
    return merged


def _union_value(
    variants: list[dict[str, Any]],
    *,
    root_schema: dict[str, Any],
    field_name: str | None,
) -> Any:
    for variant in variants:
        resolved = _resolve_schema(variant, root_schema)
        if resolved.get("type") == "null":
            continue
        return _schema_value(resolved, root_schema=root_schema, field_name=field_name)
    return None


def _all_of_value(
    variants: list[dict[str, Any]],
    *,
    root_schema: dict[str, Any],
    field_name: str | None,
) -> Any:
    merged: dict[str, Any] = {}
    for variant in variants:
        resolved = _resolve_schema(variant, root_schema)
        if resolved.get("type") == "object" or "properties" in resolved:
            merged.setdefault("type", "object")
            merged.setdefault("properties", {})
            merged.setdefault("required", [])
            merged["properties"].update(resolved.get("properties", {}))
            merged["required"] = list(
                dict.fromkeys([*merged["required"], *resolved.get("required", [])])
            )
        else:
            merged.update(resolved)
    return _schema_value(merged, root_schema=root_schema, field_name=field_name)


def _object_value(schema: dict[str, Any], *, root_schema: dict[str, Any]) -> dict[str, Any]:
    properties = schema.get("properties", {})
    return {
        name: _schema_value(property_schema, root_schema=root_schema, field_name=name)
        for name, property_schema in properties.items()
    }


def _array_value(
    schema: dict[str, Any],
    *,
    root_schema: dict[str, Any],
    field_name: str | None,
) -> list[Any]:
    if field_name == "headings":
        return ["Overview"]
    if field_name == "rubrics":
        return ["Includes cited evidence"]

    items_schema = schema.get("items")
    if not isinstance(items_schema, dict):
        return []

    item_field_name = field_name[:-1] if field_name and field_name.endswith("s") else field_name
    return [_schema_value(items_schema, root_schema=root_schema, field_name=item_field_name)]


def _string_value(field_name: str | None) -> str:
    special_values = {
        "content": "demo [1]",
        "heading": "Overview",
        "question": "What should be researched?",
        "verification": "Proceeding with research.",
    }
    return special_values.get(field_name, "demo")
