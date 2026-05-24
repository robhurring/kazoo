from __future__ import annotations

import os
import sys
from pathlib import Path


from . import schema
from .db import data_root, list_dbs, open_db
from .output import emit, result_to_rows
from .schema import split_statements


def _history_path() -> Path:
    """REPL history at $XDG_STATE_HOME/kazoo/history (default ~/.local/state/kazoo/history)."""
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "state"
    return base / "kazoo" / "history"


def _setup_readline() -> object | None:
    try:
        import readline  # noqa: F401
    except ImportError:
        return None
    history = _history_path()
    history.parent.mkdir(parents=True, exist_ok=True)
    if history.exists():
        try:
            readline.read_history_file(str(history))
        except OSError:
            pass
    readline.set_history_length(10_000)
    return readline


def _print_help() -> None:
    print(
        "Commands:\n"
        "  \\help, \\?           show this help\n"
        "  \\quit, \\q, \\exit    exit\n"
        "  \\schema             show schema (JSON)\n"
        "  \\stats              show per-table counts\n"
        "  \\d <table>          describe a table\n"
        "  \\dbs                list databases\n"
        "  \\use <name>         switch active DB in this session\n"
        "  \\pretty             toggle pretty JSON output\n"
        "  Multi-line Cypher is buffered until `;`.",
        file=sys.stderr,
    )


def _handle_meta(line: str, *, current_db: str | None, pretty: bool) -> tuple[bool, str | None, bool]:
    """Return (handled, new_db, new_pretty). When handled, the line consumed a meta cmd."""
    parts = line.strip().split()
    if not parts:
        return False, current_db, pretty
    head = parts[0]
    if head in (r"\quit", r"\q", r"\exit"):
        raise EOFError
    if head in (r"\help", r"\?"):
        _print_help()
        return True, current_db, pretty
    if head == r"\schema":
        emit(schema.show(db_name=current_db), pretty=pretty)
        return True, current_db, pretty
    if head == r"\stats":
        emit(schema.stats(db_name=current_db), pretty=pretty)
        return True, current_db, pretty
    if head == r"\d" and len(parts) >= 2:
        snap = schema.show(db_name=current_db)
        target = parts[1]
        found = next(
            (t for t in snap["nodes"] + snap["rels"] if t["name"] == target), None
        )
        emit(found if found else {"error": f"table not found: {target}"}, pretty=pretty)
        return True, current_db, pretty
    if head == r"\dbs":
        emit({"root": str(data_root()), "databases": list_dbs()}, pretty=pretty)
        return True, current_db, pretty
    if head == r"\use" and len(parts) >= 2:
        return True, parts[1], pretty
    if head == r"\pretty":
        return True, current_db, not pretty
    return False, current_db, pretty


def run(*, db_name: str | None, pretty: bool) -> None:
    rl = _setup_readline()
    print(
        f"kazoo REPL — db: {db_name or os.environ.get('KAZOO_DB') or 'default'}\n"
        r"Type a Cypher statement (end with `;`) or `\help`. Ctrl-D to exit.",
        file=sys.stderr,
    )

    conn = open_db(db_name)
    current_db = db_name
    current_pretty = pretty
    buffer: list[str] = []

    try:
        while True:
            prompt = "kazoo> " if not buffer else "   ... "
            try:
                line = input(prompt)
            except EOFError:
                print(file=sys.stderr)
                break
            except KeyboardInterrupt:
                buffer = []
                print("^C", file=sys.stderr)
                continue

            if not buffer and line.startswith("\\"):
                try:
                    handled, new_db, new_pretty = _handle_meta(
                        line, current_db=current_db, pretty=current_pretty
                    )
                except EOFError:
                    break
                except (RuntimeError, ValueError) as e:
                    print(f"error: {e}", file=sys.stderr)
                    continue
                if handled:
                    if new_db != current_db:
                        current_db = new_db
                        conn = open_db(current_db)
                    current_pretty = new_pretty
                    continue

            buffer.append(line)
            joined = "\n".join(buffer)
            if ";" not in joined:
                continue
            statements = split_statements(joined)
            if not statements:
                buffer = []
                continue
            # Check whether the source ends after a complete statement (trailing ;).
            stripped = joined.rstrip()
            if not stripped.endswith(";"):
                # last statement is partial; keep buffering
                statements = statements[:-1]
                buffer = [joined.rsplit(";", 1)[-1]]
                if not statements:
                    continue
            else:
                buffer = []

            for stmt in statements:
                try:
                    result = conn.execute(stmt + ";")
                except (RuntimeError, ValueError) as e:
                    print(f"error: {e}", file=sys.stderr)
                    continue
                rows = (
                    [result_to_rows(r) for r in result]
                    if isinstance(result, list)
                    else result_to_rows(result)
                )
                emit(rows, pretty=current_pretty)
    finally:
        if rl is not None:
            try:
                rl.write_history_file(str(_history_path()))
            except OSError:
                pass
