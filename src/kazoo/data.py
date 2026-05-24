from __future__ import annotations

from pathlib import Path
from typing import Any

from ._util import REL_TYPE, is_ident, valid_ident as _ident
from .db import open_db
from .output import result_to_rows

_JSON_EXTS = {".json", ".ndjson", ".jsonl"}


def _quoted(p: Path) -> str:
    s = str(p.resolve()).replace("'", "''")
    return f"'{s}'"


def _maybe_load_json_ext(conn, path: Path) -> bool:
    """Kuzu requires the json extension for .json files. Best-effort load."""
    if path.suffix.lower() not in _JSON_EXTS:
        return False
    try:
        conn.execute("INSTALL json;")
    except RuntimeError:
        pass
    try:
        conn.execute("LOAD EXTENSION json;")
    except RuntimeError:
        try:
            conn.execute("LOAD json;")
        except RuntimeError:
            return False
    return True


def load(*, db_name: str | None, table: str, path: Path) -> dict[str, Any]:
    table = _ident(table, "table")
    if not path.exists():
        raise FileNotFoundError(f"input file not found: {path}")
    conn = open_db(db_name)
    used_json = _maybe_load_json_ext(conn, path)
    ddl = f"COPY {table} FROM {_quoted(path)};"
    conn.execute(ddl)
    return {"loaded": table, "from": str(path), "json_extension": used_json}


def clear(*, db_name: str | None, table: str) -> dict[str, Any]:
    """Delete all rows from a node or rel table."""
    table = _ident(table, "table")
    conn = open_db(db_name)
    ttype = _table_type(conn, table)
    if ttype is None:
        raise ValueError(f"unknown table: {table!r}")
    if ttype == REL_TYPE:
        cypher = f"MATCH ()-[r:{table}]->() DELETE r;"
    else:
        cypher = f"MATCH (n:{table}) DETACH DELETE n;"
    conn.execute(cypher)
    return {"cleared": table, "type": ttype}


def _table_type(conn, name: str) -> str | None:
    rows = result_to_rows(conn.execute("CALL show_tables() RETURN *;"))
    for r in rows:
        if r.get("name") == name:
            return (r.get("type") or "").upper()
    return None


def _table_columns(conn, name: str) -> list[str]:
    rows = result_to_rows(conn.execute(f"CALL TABLE_INFO('{name}') RETURN *;"))
    return [r.get("name") for r in rows if r.get("name")]


def _resolve_dump_query(conn, source: str) -> str:
    """Turn a table name or parenthesized query into a Cypher MATCH ... RETURN.

    For bare table names, we alias each property (`n.col AS col`) so dump output
    has clean column names instead of Kuzu's `n.col` prefix from `RETURN n.*`.
    """
    if is_ident(source):
        ttype = _table_type(conn, source)
        if ttype is None:
            raise ValueError(f"unknown table: {source!r}")
        cols = _table_columns(conn, source)
        if ttype == REL_TYPE:
            projections = ", ".join(f"r.{c} AS {c}" for c in cols)
            from_to = "label(a) AS _from_label, label(b) AS _to_label"
            tail = ", " + projections if projections else ""
            return f"MATCH (a)-[r:{source}]->(b) RETURN {from_to}{tail};"
        projections = ", ".join(f"n.{c} AS {c}" for c in cols) or "n"
        return f"MATCH (n:{source}) RETURN {projections};"
    if not (source.startswith("(") and source.endswith(")")):
        raise ValueError(
            "dump source must be a table name or a parenthesized query like '(MATCH (n) RETURN n)'"
        )
    return source[1:-1].strip() + ";"


def dump(*, db_name: str | None, source: str, fmt: str) -> None:
    """Run a table-or-query dump and write the chosen format to stdout."""
    from .query import write_results  # avoid cycle at import time

    conn = open_db(db_name)
    cypher = _resolve_dump_query(conn, source)
    result = conn.execute(cypher)
    write_results(result, fmt=fmt, pretty=False)
