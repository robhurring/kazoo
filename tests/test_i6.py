from __future__ import annotations

import json
from pathlib import Path

from kazoo.schema import split_statements


def test_split_simple():
    assert split_statements("CREATE A; CREATE B;") == ["CREATE A", "CREATE B"]


def test_split_no_trailing_semicolon():
    assert split_statements("RETURN 1") == ["RETURN 1"]


def test_split_ignores_semicolon_in_single_quote_string():
    assert split_statements("CREATE (:N {s: 'hello; world'}); RETURN 1;") == [
        "CREATE (:N {s: 'hello; world'})",
        "RETURN 1",
    ]


def test_split_ignores_semicolon_in_double_quote_string():
    assert split_statements('RETURN "a;b;c";') == ['RETURN "a;b;c"']


def test_split_ignores_semicolon_in_backtick():
    assert split_statements("RETURN `weird;name`;") == ["RETURN `weird;name`"]


def test_split_ignores_line_comment():
    assert split_statements("RETURN 1; // a; comment\nRETURN 2;") == [
        "RETURN 1",
        "// a; comment\nRETURN 2",
    ]


def test_split_ignores_block_comment():
    assert split_statements("RETURN 1; /* a; b; */ RETURN 2;") == [
        "RETURN 1",
        "/* a; b; */ RETURN 2",
    ]


def test_split_escape_in_string():
    assert split_statements("RETURN 'it\\'s; ok';") == ["RETURN 'it\\'s; ok'"]


def test_apply_file_with_semicolon_in_data(run, tmp_path):
    run("db init")
    f = tmp_path / "data.cypher"
    f.write_text(
        "CREATE NODE TABLE Note (id INT64, body STRING, PRIMARY KEY (id));\n"
        "CREATE (:Note {id: 1, body: 'hello; world'});\n"
    )
    _, data = run(f"schema apply {f}")
    assert data["applied"] == 2
    _, rows = run("query 'MATCH (n:Note) RETURN n.body AS b;'")
    assert rows == [{"b": "hello; world"}]


def test_query_format_csv(run, runner):
    from kazoo.cli import app

    run("db init")
    run("schema create-node Person --prop name:STRING --pk name")
    run("query 'CREATE (:Person {name: \"Alice\"});'")
    result = runner.invoke(
        app, ["query", "MATCH (p:Person) RETURN p.name AS name;", "-f", "csv"]
    )
    assert result.exit_code == 0
    assert result.stdout.strip().splitlines() == ["name", "Alice"]


def test_query_format_tsv(run, runner):
    from kazoo.cli import app

    run("db init")
    run("schema create-node Person --prop name:STRING --pk name")
    run("query 'CREATE (:Person {name: \"Alice\"});'")
    result = runner.invoke(
        app, ["query", "MATCH (p:Person) RETURN p.name AS name;", "-f", "tsv"]
    )
    assert result.exit_code == 0
    assert result.stdout.strip().splitlines() == ["name", "Alice"]


def test_query_unknown_format(run):
    run("db init")
    result, data = run("query 'RETURN 1;' -f yaml", expect_ok=False)
    assert result.exit_code != 0
    assert "unknown format" in data["error"]


def test_repl_basic_flow(monkeypatch, tmp_path):
    """Drive the REPL by replacing input() with a script and capturing stdout."""
    from kazoo import repl as repl_mod

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    # Seed a DB with one node.
    from kazoo.cli import app
    from typer.testing import CliRunner
    r = CliRunner()
    r.invoke(app, ["db", "init"])
    r.invoke(app, ["schema", "create-node", "Person", "--prop", "name:STRING", "--pk", "name"])
    r.invoke(app, ["query", 'CREATE (:Person {name: "Alice"});'])

    inputs = iter([
        r"\schema",
        "MATCH (p:Person) RETURN p.name AS name;",
        r"\quit",
    ])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    import io
    import sys
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        try:
            repl_mod.run(db_name=None, pretty=False)
        except EOFError:
            pass
    finally:
        sys.stdout = old_stdout

    text = buf.getvalue()
    # The \schema output and the MATCH output both went to stdout as JSON.
    assert '"nodes"' in text
    assert "Alice" in text
