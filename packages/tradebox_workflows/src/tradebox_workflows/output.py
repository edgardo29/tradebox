"""Stable CLI output helpers."""

from __future__ import annotations

from collections.abc import Mapping


def print_metadata(values: Mapping[str, object]) -> None:
    """Print stable key=value metadata lines for shell smoke checks."""

    for key, value in values.items():
        print(f"{key}={_to_output_value(value)}")


def _to_output_value(value: object) -> str:
    if value is None:
        return ""
    return str(value)
