from __future__ import annotations

import re
from typing import Any

from ._util import REL_TYPE, valid_ident as _ident
from .db import open_db
from .output import result_to_rows


def stats(*, db_name: str | None = None, conn=None) -> dict[str, Any]:
    """Return per-table row counts. Pass `conn` to reuse an open connection."""
    if conn is None:
        conn = open_db(db_name)
    tables = result_to_rows(conn.execute("CALL show_tables() RETURN *;"))
    nodes: dict[str, int] = {}
    rels: dict[str, int] = {}
    for t in tables:
        name = t.get("name")
        ttype = (t.get("type") or "").upper()
        if ttype == REL_TYPE:
            row = result_to_rows(conn.execute(f"MATCH ()-[r:{name}]->() RETURN count(r) AS c;"))
            rels[name] = int(row[0]["c"]) if row else 0
        else:
            row = result_to_rows(conn.execute(f"MATCH (n:{name}) RETURN count(n) AS c;"))
            nodes[name] = int(row[0]["c"]) if row else 0
    return {"nodes": nodes, "rels": rels}


def _parse_prop(spec: str) -> tuple[str, str]:
    """Parse 'name:TYPE' into (name, TYPE). Validates identifier; type passes through."""
    if ":" not in spec:
        raise ValueError(f"property spec must be NAME:TYPE, got {spec!r}")
    name, type_ = spec.split(":", 1)
    name = name.strip()
    type_ = type_.strip()
    if not name or not type_:
        raise ValueError(f"property spec must be NAME:TYPE, got {spec!r}")
    _ident(name, "property name")
    # Allow common parametric types like STRING, INT64, DECIMAL(10,2), STRING[]
    if not re.match(r"^[A-Za-z0-9_\[\]\(\),\s]+$", type_):
        raise ValueError(f"invalid property type: {type_!r}")
    return name, type_


def describe(*, db_name: str | None, name: str) -> dict[str, Any]:
    """Return one table's properties (and connections for rels)."""
    name = _ident(name, "table")
    snap = show(db_name=db_name)
    for entry in snap["nodes"] + snap["rels"]:
        if entry["name"] == name:
            return entry
    raise ValueError(f"table not found: {name}")


def show(*, db_name: str | None = None, conn=None) -> dict[str, Any]:
    """Show schema as JSON-friendly dict. Pass `conn` to reuse an open connection."""
    if conn is None:
        conn = open_db(db_name)
    tables = result_to_rows(conn.execute("CALL show_tables() RETURN *;"))
    nodes: list[dict[str, Any]] = []
    rels: list[dict[str, Any]] = []
    for t in tables:
        name = t.get("name")
        ttype = (t.get("type") or "").upper()
        info_rows = result_to_rows(conn.execute(f"CALL TABLE_INFO('{name}') RETURN *;"))
        properties = [
            {
                "name": r.get("name"),
                "type": r.get("type"),
                "primary_key": bool(r.get("primary key", r.get("primary_key", False))),
            }
            for r in info_rows
        ]
        entry: dict[str, Any] = {
            "name": name,
            "type": ttype,
            "properties": properties,
        }
        if ttype == REL_TYPE:
            try:
                conns = result_to_rows(
                    conn.execute(f"CALL show_connection('{name}') RETURN *;")
                )
                entry["connections"] = [
                    {"from": c.get("source table name"), "to": c.get("destination table name")}
                    for c in conns
                ]
            except RuntimeError:
                entry["connections"] = []
            rels.append(entry)
        else:
            nodes.append(entry)
    return {"nodes": nodes, "rels": rels}


def split_statements(text: str) -> list[str]:
    """Split a Cypher source on `;`, ignoring separators inside strings and comments.

    Recognized literal/comment forms: 'single', "double", `backtick`, // line, /* block */.
    Backslash escapes inside string literals.
    """
    statements: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(text)
    in_quote: str | None = None
    in_line_comment = False
    in_block_comment = False

    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if in_line_comment:
            buf.append(c)
            if c == "\n":
                in_line_comment = False
            i += 1
            continue
        if in_block_comment:
            buf.append(c)
            if c == "*" and nxt == "/":
                buf.append(nxt)
                i += 2
                in_block_comment = False
                continue
            i += 1
            continue
        if in_quote is not None:
            buf.append(c)
            if c == "\\" and nxt:
                buf.append(nxt)
                i += 2
                continue
            if c == in_quote:
                in_quote = None
            i += 1
            continue

        if c == "/" and nxt == "/":
            in_line_comment = True
            buf.append(c)
            i += 1
            continue
        if c == "/" and nxt == "*":
            in_block_comment = True
            buf.append(c)
            buf.append(nxt)
            i += 2
            continue
        if c in ("'", '"', "`"):
            in_quote = c
            buf.append(c)
            i += 1
            continue
        if c == ";":
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
            i += 1
            continue

        buf.append(c)
        i += 1

    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def apply_text(*, db_name: str | None, text: str, atomic: bool = True) -> dict[str, Any]:
    """Apply a semicolon-separated stream of DDL statements.

    When `atomic`, wraps execution in a transaction so partial failures roll back.
    """
    conn = open_db(db_name)
    statements = split_statements(text)
    if not statements:
        return {"applied": 0, "atomic": atomic}
    if atomic:
        conn.execute("BEGIN TRANSACTION;")
        try:
            for stmt in statements:
                conn.execute(stmt + ";")
            conn.execute("COMMIT;")
        except Exception:
            try:
                conn.execute("ROLLBACK;")
            except Exception:
                pass
            raise
    else:
        for stmt in statements:
            conn.execute(stmt + ";")
    return {"applied": len(statements), "atomic": atomic}


def export(*, db_name: str | None) -> str:
    """Emit Cypher DDL that recreates the current schema."""
    snap = show(db_name=db_name)
    lines: list[str] = []
    for node in snap["nodes"]:
        props = ", ".join(f"{p['name']} {p['type']}" for p in node["properties"])
        pk = next((p["name"] for p in node["properties"] if p["primary_key"]), None)
        pk_clause = f", PRIMARY KEY ({pk})" if pk else ""
        lines.append(f"CREATE NODE TABLE {node['name']} ({props}{pk_clause});")
    for rel in snap["rels"]:
        conns = rel.get("connections") or []
        from_to = ", ".join(f"FROM {c['from']} TO {c['to']}" for c in conns)
        props = ", ".join(f"{p['name']} {p['type']}" for p in rel["properties"])
        body = ", ".join(filter(None, [from_to, props]))
        lines.append(f"CREATE REL TABLE {rel['name']} ({body});")
    return "\n".join(lines) + ("\n" if lines else "")


def create_node(
    *,
    db_name: str | None,
    name: str,
    props: list[str],
    pk: str | None,
    if_not_exists: bool = False,
) -> dict[str, Any]:
    name = _ident(name, "node table")
    if not props:
        raise ValueError("node table needs at least one --prop")
    if not pk:
        raise ValueError("node table requires --pk (Kuzu requires a primary key)")
    parsed = [_parse_prop(p) for p in props]
    cols = ", ".join(f"{n} {t}" for n, t in parsed)
    pk = _ident(pk, "primary key")
    if pk not in [n for n, _ in parsed]:
        raise ValueError(f"primary key {pk!r} not in properties")
    exists_clause = "IF NOT EXISTS " if if_not_exists else ""
    ddl = f"CREATE NODE TABLE {exists_clause}{name} ({cols}, PRIMARY KEY ({pk}));"
    conn = open_db(db_name)
    conn.execute(ddl)
    return {"created": "NODE", "name": name, "ddl": ddl}


def create_rel(
    *,
    db_name: str | None,
    name: str,
    from_table: str,
    to_table: str,
    props: list[str],
    if_not_exists: bool = False,
) -> dict[str, Any]:
    name = _ident(name, "rel table")
    from_table = _ident(from_table, "from table")
    to_table = _ident(to_table, "to table")
    parsed = [_parse_prop(p) for p in props]
    parts = [f"FROM {from_table} TO {to_table}"]
    if parsed:
        parts.append(", ".join(f"{n} {t}" for n, t in parsed))
    exists_clause = "IF NOT EXISTS " if if_not_exists else ""
    ddl = f"CREATE REL TABLE {exists_clause}{name} ({', '.join(parts)});"
    conn = open_db(db_name)
    conn.execute(ddl)
    return {"created": "REL", "name": name, "ddl": ddl}


def add_column(
    *,
    db_name: str | None,
    table: str,
    spec: str,
    default: str | None = None,
) -> dict[str, Any]:
    table = _ident(table, "table")
    col_name, col_type = _parse_prop(spec)
    default_clause = f" DEFAULT {default}" if default else ""
    ddl = f"ALTER TABLE {table} ADD {col_name} {col_type}{default_clause};"
    conn = open_db(db_name)
    conn.execute(ddl)
    return {"altered": table, "added": col_name, "type": col_type, "ddl": ddl}


def drop_column(*, db_name: str | None, table: str, column: str) -> dict[str, Any]:
    table = _ident(table, "table")
    column = _ident(column, "column")
    ddl = f"ALTER TABLE {table} DROP {column};"
    conn = open_db(db_name)
    conn.execute(ddl)
    return {"altered": table, "dropped": column}


def drop(*, db_name: str | None, name: str, if_exists: bool = False) -> dict[str, Any]:
    name = _ident(name, "table")
    exists_clause = "IF EXISTS " if if_exists else ""
    ddl = f"DROP TABLE {exists_clause}{name};"
    conn = open_db(db_name)
    conn.execute(ddl)
    return {"dropped": name}
