from __future__ import annotations

from pathlib import Path
from typing import Any

from ._util import REL_TYPE, valid_ident as _ident
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


def _table_type(conn, name: str) -> str | None:
    rows = result_to_rows(conn.execute("CALL show_tables() RETURN *;"))
    for r in rows:
        if r.get("name") == name:
            return (r.get("type") or "").upper()
    return None


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
