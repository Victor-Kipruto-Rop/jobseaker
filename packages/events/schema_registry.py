"""Local versioned JSON Schema registry and backward-compatibility checks.

The registry is a contract enforcement layer used by producers/consumers in this
repository. It is not a substitute for a highly available Confluent/Apicurio
Schema Registry deployment in production.
"""
from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


SCHEMA_ROOT = Path(__file__).resolve().parents[2] / "schemas" / "events"


@lru_cache(maxsize=32)
def load_envelope_schema(version: int) -> dict[str, Any]:
    if version != 1:
        raise ValueError(f"Unsupported event envelope schema version: {version}")
    path = SCHEMA_ROOT / f"envelope.v{version}.schema.json"
    if not path.is_file():
        raise ValueError(f"Event schema v{version} is not registered")
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def validate_envelope(envelope: dict[str, Any]) -> None:
    version = envelope.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise ValueError("schema_version must be an integer")
    schema = load_envelope_schema(version)
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(envelope),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.absolute_path) or "envelope"
        raise ValueError(f"Event schema validation failed at {location}: {first.message}")


def assert_backward_compatible(previous: dict[str, Any], candidate: dict[str, Any]) -> None:
    """Reject changes that make a previously valid producer payload invalid.

    Additive optional properties are compatible. Removing/renaming properties,
    adding required fields, narrowing enums/types/constants, or making an
    optional property required are incompatible.
    """
    old_required = set(previous.get("required", []))
    new_required = set(candidate.get("required", []))
    if not new_required.issubset(old_required):
        added = sorted(new_required - old_required)
        raise ValueError(f"Backward-incompatible required fields added: {added}")

    old_props = previous.get("properties", {})
    new_props = candidate.get("properties", {})
    for name, old_schema in old_props.items():
        if name not in new_props:
            raise ValueError(f"Backward-incompatible property removal: {name}")
        new_schema = new_props[name]
        old_type = old_schema.get("type")
        new_type = new_schema.get("type")
        if old_type is not None and new_type != old_type:
            raise ValueError(f"Backward-incompatible type change for {name}")
        old_enum = old_schema.get("enum")
        new_enum = new_schema.get("enum")
        if old_enum is not None and (new_enum is None or not set(old_enum).issubset(set(new_enum))):
            raise ValueError(f"Backward-incompatible enum narrowing for {name}")
        if "const" in old_schema and new_schema.get("const") != old_schema["const"]:
            raise ValueError(f"Backward-incompatible const change for {name}")
        if old_schema.get("format") and new_schema.get("format") != old_schema["format"]:
            raise ValueError(f"Backward-incompatible format change for {name}")
        if name in old_required and name not in new_required:
            continue


def validate_schema_registration(
    previous: dict[str, Any] | None, candidate: dict[str, Any],
) -> dict[str, Any]:
    Draft202012Validator.check_schema(candidate)
    if previous is not None:
        assert_backward_compatible(previous, candidate)
    return deepcopy(candidate)
