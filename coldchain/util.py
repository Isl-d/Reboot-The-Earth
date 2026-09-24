"""Small shared helpers.

`camelize` exists because the reference data in fleet.py is snake_case (it
feeds the SQLAlchemy models directly) while everything on the wire is
camelCase. Converting at the API edge keeps one definition of the world and
one spelling for the frontend.
"""
from __future__ import annotations

from typing import Any


def camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(w.capitalize() for w in rest)


def camelize(value: Any) -> Any:
    """Recursively convert dict keys from snake_case to camelCase."""
    if isinstance(value, dict):
        return {camel(k): camelize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [camelize(v) for v in value]
    return value
