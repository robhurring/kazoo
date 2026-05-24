from __future__ import annotations

import json
import sys
from typing import Any, Iterable

from .db import open_db
from .output import (
    emit,
    emit_ndjson_row,
    result_to_rows,
    stream_result_rows,
    write_delimited,
)


def resolve_query(inline: str | None) -> str:
    """Pick query text from the inline arg, falling back to stdin."""
    if inline:
        return inline
    if sys.stdin.isatty():
        raise ValueError("no query provided (pass as arg or pipe via stdin)")
    text = sys.stdin.read().strip()
    if not text:
        raise ValueError("empty query on stdin")
    return text


def parse_param(spec: str) -> tuple[str, Any]:
    """Parse NAME=VALUE; VALUE is JSON if it parses, else a string."""
    if "=" not in spec:
        raise ValueError(f"--param must be NAME=VALUE, got {spec!r}")
    name, raw = spec.split("=", 1)
    name = name.strip()
    if not name:
        raise ValueError(f"--param missing name in {spec!r}")
    try:
        value: Any = json.loads(raw)
    except json.JSONDecodeError:
        value = raw
    return name, value


def materialize(result) -> list[dict[str, Any]] | list[list[dict[str, Any]]]:
    """Materialize one or many kuzu QueryResults into row dicts."""
    if isinstance(result, list):
        return [result_to_rows(r) for r in result]
    return result_to_rows(result)


def _iter_rows(result) -> Iterable[dict[str, Any]]:
    for r in result if isinstance(result, list) else [result]:
        yield from stream_result_rows(r)


def write_results(result, *, fmt: str, pretty: bool, stream=None) -> None:
    if fmt == "ndjson":
        for row in _iter_rows(result):
            emit_ndjson_row(row, stream=stream)
    elif fmt == "csv":
        write_delimited(_iter_rows(result), delimiter=",", stream=stream)
    elif fmt == "tsv":
        write_delimited(_iter_rows(result), delimiter="\t", stream=stream)
    else:  # json
        emit(materialize(result), pretty=pretty, stream=stream)


def run_query(
    *,
    inline: str | None,
    db_name: str | None,
    pretty: bool,
    params: list[str] | None = None,
    fmt: str = "json",
    explain: bool = False,
    profile: bool = False,
) -> None:
    if explain and profile:
        raise ValueError("pass at most one of --explain / --profile")
    cypher = resolve_query(inline)
    if explain:
        cypher = f"EXPLAIN {cypher.rstrip(';').strip()};"
    elif profile:
        cypher = f"PROFILE {cypher.rstrip(';').strip()};"
    bound = dict(parse_param(p) for p in (params or []))
    conn = open_db(db_name)
    result = conn.execute(cypher, bound) if bound else conn.execute(cypher)
    write_results(result, fmt=fmt, pretty=pretty)
