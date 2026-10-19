"""JSON contracts between stages.

A small validator for the subset of JSON Schema the files in /schemas use
(type, required, properties, items, enum, minimum, maximum, minLength,
minItems, pattern, format, additionalProperties). Standard library only, so
the repo runs with no installs. Bad data fails loud with every problem listed.
"""

import json
import re
from datetime import date, datetime
from pathlib import Path

from . import ROOT

_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


class ContractError(ValueError):
    def __init__(self, name, errors):
        self.errors = errors
        super().__init__(f"{name} failed its contract:\n  - " + "\n  - ".join(errors))


def parse_datetime(value):
    """Parse an ISO 8601 timestamp that carries a timezone."""
    if not isinstance(value, str) or "T" not in value:
        raise ValueError(f"not an ISO date-time: {value!r}")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"date-time has no timezone: {value!r}")
    return dt


def _type_ok(value, expected):
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, _TYPES[expected])


def _check(value, schema, path, errors):
    types = schema.get("type")
    if types is not None:
        types = types if isinstance(types, list) else [types]
        if not any(_type_ok(value, t) for t in types):
            errors.append(f"{path}: expected {'/'.join(types)}, got {type(value).__name__}")
            return
    if value is None:
        return
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not one of {schema['enum']}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} above maximum {schema['maximum']}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: shorter than {schema['minLength']} characters")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: does not match {schema['pattern']}")
        fmt = schema.get("format")
        try:
            if fmt == "date-time":
                parse_datetime(value)
            elif fmt == "date":
                date.fromisoformat(value)
            elif fmt == "uri" and not re.match(r"^https?://\S+$", value):
                raise ValueError
        except ValueError:
            errors.append(f"{path}: not a valid {fmt}: {value!r}")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing required field '{key}'")
        props = schema.get("properties", {})
        for key, sub in props.items():
            if key in value:
                _check(value[key], sub, f"{path}.{key}", errors)
        if schema.get("additionalProperties") is False:
            errors.extend(f"{path}: unexpected field '{k}'" for k in value if k not in props)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: needs at least {schema['minItems']} item(s)")
        if "items" in schema:
            for i, item in enumerate(value):
                _check(item, schema["items"], f"{path}[{i}]", errors)


def load_schema(name, root=ROOT):
    return json.loads((Path(root) / "schemas" / f"{name}.schema.json").read_text())


def errors_for(record, name, root=ROOT):
    errors = []
    _check(record, load_schema(name, root), "$", errors)
    return errors


def validate(record, name, root=ROOT):
    """Raise ContractError if record breaks the named schema; return it otherwise."""
    errors = errors_for(record, name, root)
    if errors:
        rid = record.get("id", "?") if isinstance(record, dict) else "?"
        raise ContractError(f"{name} {rid}", errors)
    return record
