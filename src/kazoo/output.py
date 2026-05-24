from __future__ import annotations

import csv
import datetime as dt
import json
import sys
import uuid
from typing import Any, Iterable


def _default(value: Any) -> Any:
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, dt.timedelta):
        return value.total_seconds()
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, set):
        return sorted(value, key=str)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def emit(data: Any, *, pretty: bool = False, stream=None) -> None:
    s = stream if stream is not None else sys.stdout
    indent = 2 if pretty else None
    json.dump(data, s, default=_default, indent=indent, sort_keys=False)
    s.write("\n")


def emit_ndjson_row(row: Any, *, stream=None) -> None:
    s = stream if stream is not None else sys.stdout
    json.dump(row, s, default=_default)
    s.write("\n")


def result_to_rows(result: Any) -> list[dict[str, Any]]:
    """Materialize a kuzu QueryResult into a list of dicts."""
    columns = result.get_column_names()
    rows: list[dict[str, Any]] = []
    while result.has_next():
        values = result.get_next()
        rows.append(dict(zip(columns, values, strict=False)))
    return rows


def stream_result_rows(result: Any):
    """Yield kuzu QueryResult rows as dicts (lazy)."""
    columns = result.get_column_names()
    while result.has_next():
        yield dict(zip(columns, result.get_next(), strict=False))


def _csv_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=_default)
    return _default(value) if not isinstance(value, (str, int, float, bool)) else str(value)


def write_delimited(rows: Iterable[dict[str, Any]], *, delimiter: str, stream=None) -> None:
    """Write rows as CSV/TSV to stream, inferring header from the first row."""
    s = stream if stream is not None else sys.stdout
    iterator = iter(rows)
    try:
        first = next(iterator)
    except StopIteration:
        return
    fieldnames = list(first.keys())
    writer = csv.writer(s, delimiter=delimiter, lineterminator="\n")
    writer.writerow(fieldnames)
    writer.writerow([_csv_cell(first[k]) for k in fieldnames])
    for row in iterator:
        writer.writerow([_csv_cell(row.get(k)) for k in fieldnames])
