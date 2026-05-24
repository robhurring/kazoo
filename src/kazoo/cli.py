from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from . import __version__, data, db, query, repl, schema
from .output import emit


app = typer.Typer(
    name="kazoo",
    help="CLI for Kuzu graph databases. JSON output by default.",
    no_args_is_help=True,
)
schema_app = typer.Typer(help="Inspect and manage the schema.", no_args_is_help=True)
db_app = typer.Typer(help="Manage databases under the XDG data dir.", no_args_is_help=True)
data_app = typer.Typer(help="Bulk-load and dump table data.", no_args_is_help=True)
app.add_typer(schema_app, name="schema")
app.add_typer(db_app, name="db")
app.add_typer(data_app, name="data")


VALID_FORMATS = ("json", "ndjson", "csv", "tsv")


class State:
    db_name: str | None = None
    pretty: bool = False


state = State()


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    db_name: Annotated[
        str | None,
        typer.Option("--db", "-d", help="Named DB under the XDG data dir. Defaults to $KAZOO_DB or 'default'."),
    ] = None,
    pretty: Annotated[bool, typer.Option("--pretty", "-p", help="Indent JSON output.")] = False,
    _version: Annotated[
        bool | None,
        typer.Option("--version", "-V", callback=_version_callback, is_eager=True, help="Show version and exit."),
    ] = None,
) -> None:
    state.db_name = db_name
    state.pretty = pretty


def _bail(msg: str, code: int = 1) -> NoReturn:
    emit({"error": msg}, pretty=state.pretty)
    raise typer.Exit(code)


@contextmanager
def _handle_errors():
    """Map common exceptions to JSON error output + exit codes."""
    try:
        yield
    except ValueError as e:
        _bail(str(e), code=2)
    except (FileNotFoundError, FileExistsError) as e:
        _bail(str(e))
    except RuntimeError as e:
        _bail(f"kuzu: {e}")


_COMPLETION_SHELLS = ("bash", "zsh", "fish")


@app.command("completions")
def completions_cmd(
    shell: Annotated[
        str,
        typer.Argument(help=f"Shell to emit a completion script for: {', '.join(_COMPLETION_SHELLS)}."),
    ],
) -> None:
    """Print a shell completion script to stdout. Pipe into your shell's completion dir.

    Examples:
        kazoo completions zsh  > "${fpath[1]}/_kazoo"
        kazoo completions bash > /usr/local/etc/bash_completion.d/kazoo
        kazoo completions fish > ~/.config/fish/completions/kazoo.fish
    """
    if shell not in _COMPLETION_SHELLS:
        _bail(f"unknown shell: {shell!r} (choose from {', '.join(_COMPLETION_SHELLS)})", code=2)
    from click.shell_completion import get_completion_class

    cmd = typer.main.get_command(app)
    cls = get_completion_class(shell)
    if cls is None:
        _bail(f"completion class unavailable for {shell}")
    comp = cls(cli=cmd, ctx_args={}, prog_name="kazoo", complete_var="_KAZOO_COMPLETE")
    sys.stdout.write(comp.source())


@app.command("repl")
def repl_cmd() -> None:
    """Start an interactive Cypher REPL with readline history."""
    repl.run(db_name=state.db_name, pretty=state.pretty)


@app.command("info")
def info_cmd() -> None:
    """Show a one-shot summary: db path, size, version, schema, stats."""
    import kuzu

    path = db.db_path(state.db_name)
    payload: dict[str, object] = {
        "kazoo_version": __version__,
        "kuzu_version": getattr(kuzu, "__version__", "unknown"),
        "name": path.stem,
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
    }
    if path.exists():
        try:
            conn = db.open_db(state.db_name)
            payload["schema"] = schema.show(conn=conn)
            payload["stats"] = schema.stats(conn=conn)
        except RuntimeError as e:
            payload["error"] = f"kuzu: {e}"
    emit(payload, pretty=state.pretty)


@app.command("query")
def query_cmd(
    cypher: Annotated[str | None, typer.Argument(help="Cypher query. Omit to read from stdin (pipe a file with `< file`).")] = None,
    param: Annotated[
        list[str],
        typer.Option("--param", help="Bind a parameter as NAME=VALUE (JSON value or string). Repeatable."),
    ] = [],
    explain: Annotated[
        bool, typer.Option("--explain", help="Prefix with EXPLAIN — return the query plan instead of results.")
    ] = False,
    profile: Annotated[
        bool, typer.Option("--profile", help="Prefix with PROFILE — return per-operator timings.")
    ] = False,
    fmt: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help=f"Output format: {', '.join(VALID_FORMATS)}. Default: json. Pipe stdout to a file.",
        ),
    ] = "json",
) -> None:
    """Execute a Cypher query and print results to stdout."""
    if fmt not in VALID_FORMATS:
        _bail(f"unknown format: {fmt!r} (choose from {', '.join(VALID_FORMATS)})", code=2)
    with _handle_errors():
        query.run_query(
            inline=cypher,
            db_name=state.db_name,
            pretty=state.pretty,
            params=param,
            fmt=fmt,
            explain=explain,
            profile=profile,
        )


@schema_app.command("show")
def schema_show() -> None:
    """Show nodes, rels, and their properties as JSON."""
    with _handle_errors():
        emit(schema.show(db_name=state.db_name), pretty=state.pretty)


@schema_app.command("describe")
def schema_describe(
    name: Annotated[str, typer.Argument(help="Table name (node or rel).")],
) -> None:
    """Show one table's properties (and connections for rels) as JSON."""
    with _handle_errors():
        emit(schema.describe(db_name=state.db_name, name=name), pretty=state.pretty)


@schema_app.command("apply")
def schema_apply(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True, help="DDL file.")],
    atomic: Annotated[
        bool,
        typer.Option(
            "--atomic/--no-atomic",
            help="Wrap statements in a transaction so partial failures roll back. Default: on.",
        ),
    ] = True,
) -> None:
    """Apply Cypher DDL statements from a file (semicolon-separated)."""
    with _handle_errors():
        emit(schema.apply_file(db_name=state.db_name, path=path, atomic=atomic), pretty=state.pretty)


@schema_app.command("export")
def schema_export() -> None:
    """Export the current schema as Cypher DDL to stdout. Pipe to a file."""
    with _handle_errors():
        sys.stdout.write(schema.export(db_name=state.db_name))


@schema_app.command("create-node")
def schema_create_node(
    name: Annotated[str, typer.Argument(help="Node table name.")],
    prop: Annotated[list[str], typer.Option("--prop", help="Property as NAME:TYPE. Repeatable.")] = [],
    pk: Annotated[str | None, typer.Option("--pk", help="Primary key property name.")] = None,
    if_not_exists: Annotated[
        bool, typer.Option("--if-not-exists", help="Skip without error if the table already exists.")
    ] = False,
) -> None:
    """Create a NODE TABLE."""
    with _handle_errors():
        emit(
            schema.create_node(
                db_name=state.db_name, name=name, props=prop, pk=pk, if_not_exists=if_not_exists
            ),
            pretty=state.pretty,
        )


@schema_app.command("create-rel")
def schema_create_rel(
    name: Annotated[str, typer.Argument(help="Rel table name.")],
    from_table: Annotated[str, typer.Option("--from", help="Source node table.")],
    to_table: Annotated[str, typer.Option("--to", help="Destination node table.")],
    prop: Annotated[list[str], typer.Option("--prop", help="Property as NAME:TYPE. Repeatable.")] = [],
    if_not_exists: Annotated[
        bool, typer.Option("--if-not-exists", help="Skip without error if the table already exists.")
    ] = False,
) -> None:
    """Create a REL TABLE between two node tables."""
    with _handle_errors():
        emit(
            schema.create_rel(
                db_name=state.db_name,
                name=name,
                from_table=from_table,
                to_table=to_table,
                props=prop,
                if_not_exists=if_not_exists,
            ),
            pretty=state.pretty,
        )


@schema_app.command("add-column")
def schema_add_column(
    table: Annotated[str, typer.Argument(help="Table to alter.")],
    spec: Annotated[str, typer.Argument(help="Column spec as NAME:TYPE.")],
    default: Annotated[
        str | None,
        typer.Option("--default", help="Default value expression (e.g. 0, 'foo', CURRENT_TIMESTAMP)."),
    ] = None,
) -> None:
    """ALTER TABLE … ADD <column> <type> [DEFAULT …]."""
    with _handle_errors():
        emit(
            schema.add_column(db_name=state.db_name, table=table, spec=spec, default=default),
            pretty=state.pretty,
        )


@schema_app.command("drop-column")
def schema_drop_column(
    table: Annotated[str, typer.Argument(help="Table to alter.")],
    column: Annotated[str, typer.Argument(help="Column to drop.")],
) -> None:
    """ALTER TABLE … DROP <column>."""
    with _handle_errors():
        emit(
            schema.drop_column(db_name=state.db_name, table=table, column=column),
            pretty=state.pretty,
        )


@schema_app.command("drop")
def schema_drop(
    name: Annotated[str, typer.Argument(help="Table to drop.")],
    if_exists: Annotated[
        bool, typer.Option("--if-exists", help="Skip without error if the table does not exist.")
    ] = False,
) -> None:
    """Drop a NODE or REL table."""
    with _handle_errors():
        emit(schema.drop(db_name=state.db_name, name=name, if_exists=if_exists), pretty=state.pretty)


@db_app.command("list")
def db_list() -> None:
    """List databases under the XDG data dir."""
    emit({"root": str(db.data_root()), "databases": db.list_dbs()}, pretty=state.pretty)


@db_app.command("path")
def db_path(
    name: Annotated[str | None, typer.Argument(help="DB name. Defaults to the active DB.")] = None,
) -> None:
    """Print the filesystem path for a database."""
    target = name or state.db_name
    with _handle_errors():
        path = db.db_path(target)
    emit({"name": path.stem, "path": str(path), "exists": path.exists()}, pretty=state.pretty)


@db_app.command("init")
def db_init(
    name: Annotated[str | None, typer.Argument(help="DB name. Defaults to the active DB.")] = None,
) -> None:
    """Create an empty database file."""
    target = name or state.db_name
    db.open_db(target, create=True)
    path = db.db_path(target)
    emit({"initialized": path.stem, "path": str(path)}, pretty=state.pretty)


@db_app.command("rename")
def db_rename(
    old: Annotated[str, typer.Argument(help="Current DB name.")],
    new: Annotated[str, typer.Argument(help="New DB name.")],
) -> None:
    """Rename a database file."""
    with _handle_errors():
        src, dest = db.rename_db(old, new)
    emit({"renamed": new, "from": str(src), "to": str(dest)}, pretty=state.pretty)


@db_app.command("rm")
def db_rm(
    name: Annotated[str, typer.Argument(help="DB name to delete.")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
) -> None:
    """Delete a database file."""
    with _handle_errors():
        path = db.db_path(name)
    if not path.exists():
        _bail(f"database does not exist: {path}")
    if not yes and not typer.confirm(f"Delete {path}?", default=False):
        _bail("aborted", code=1)
    db.remove_db(name)
    emit({"removed": name, "path": str(path)}, pretty=state.pretty)


@db_app.command("stats")
def db_stats() -> None:
    """Show per-table row counts."""
    with _handle_errors():
        emit(schema.stats(db_name=state.db_name), pretty=state.pretty)


@db_app.command("backup")
def db_backup(
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Destination file or directory. Defaults to <name>-<ts>.graph in cwd."),
    ] = None,
) -> None:
    """Copy the active DB file to a backup location."""
    import datetime as dt

    target = state.db_name
    src = db.db_path(target)
    if out is None:
        ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        out = Path.cwd() / f"{src.stem}-{ts}{db.DB_SUFFIX}"
    with _handle_errors():
        dest = db.backup_db(target, out)
    emit({"backed_up": src.stem, "from": str(src), "to": str(dest)}, pretty=state.pretty)


@db_app.command("restore")
def db_restore(
    src: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True, help="Backup file.")],
    as_name: Annotated[
        str | None,
        typer.Option("--as", help="Restore under this DB name. Defaults to the active DB or the backup's stem."),
    ] = None,
) -> None:
    """Restore a backup as a new database (will not overwrite an existing one)."""
    target = as_name or state.db_name or src.stem
    with _handle_errors():
        dest = db.restore_db(src, target)
    emit({"restored": target, "from": str(src), "to": str(dest)}, pretty=state.pretty)


@data_app.command("load")
def data_load(
    table: Annotated[str, typer.Argument(help="Destination table name.")],
    file: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True, help="Input file (csv/parquet/json).")],
) -> None:
    """Bulk-load a table from a file (COPY FROM)."""
    with _handle_errors():
        emit(data.load(db_name=state.db_name, table=table, path=file), pretty=state.pretty)


@data_app.command("clear")
def data_clear(
    table: Annotated[str, typer.Argument(help="Table to truncate.")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
) -> None:
    """Delete all rows from a node or rel table (DETACH DELETE for nodes)."""
    if not yes and not typer.confirm(f"Delete all rows from {table}?", default=False):
        _bail("aborted", code=1)
    with _handle_errors():
        emit(data.clear(db_name=state.db_name, table=table), pretty=state.pretty)


@data_app.command("dump")
def data_dump(
    source: Annotated[
        str,
        typer.Argument(
            help="Table name, or a parenthesized query like '(MATCH (n:Person) RETURN n.*)'.",
        ),
    ],
    fmt: Annotated[
        str,
        typer.Option("--format", "-f", help=f"Output format: {', '.join(VALID_FORMATS)}. Default: json."),
    ] = "json",
) -> None:
    """Dump a table or query result to stdout. Pipe to a file."""
    if fmt not in VALID_FORMATS:
        _bail(f"unknown format: {fmt!r} (choose from {', '.join(VALID_FORMATS)})", code=2)
    with _handle_errors():
        data.dump(db_name=state.db_name, source=source, fmt=fmt)


if __name__ == "__main__":
    app()
