from __future__ import annotations

import io
import sys


def test_repl_basic_flow(monkeypatch, tmp_path):
    """Drive the REPL by replacing input() with a script and capturing stdout."""
    from kazoo import repl as repl_mod
    from kazoo.cli import app
    from typer.testing import CliRunner

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

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
    assert '"nodes"' in text
    assert "Alice" in text
