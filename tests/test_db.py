from __future__ import annotations

from pathlib import Path


# -- init / list / path -------------------------------------------------------


def test_db_list_empty(run):
    _, data = run("db list")
    assert data["databases"] == []


def test_db_init_default(run):
    _, data = run("db init")
    assert data["initialized"] == "default"
    assert data["path"].endswith("/default.graph")


def test_db_init_named(run):
    _, data = run("--db mygraph db init")
    assert data["initialized"] == "mygraph"


def test_db_list_after_inits(run):
    run("db init")
    run("--db other db init")
    _, data = run("db list")
    assert data["databases"] == ["default", "other"]


def test_db_path_for_missing(run):
    _, data = run("--db ghost db path")
    assert data["exists"] is False
    assert data["name"] == "ghost"


def test_db_name_rejects_special_segments(run):
    """Bare names like '..' or '.' are not valid DB names."""
    result, _ = run("--db .. db path", expect_ok=False)
    assert result.exit_code != 0


def test_kazoo_db_env_var(run, monkeypatch):
    monkeypatch.setenv("KAZOO_DB", "fromenv")
    _, data = run("db path")
    assert data["name"] == "fromenv"


def test_db_extension_is_graph(run):
    _, data = run("db init")
    assert data["path"].endswith(".graph")


# -- XDG path conventions -----------------------------------------------------


def test_xdg_default_path_uses_dot_local_share(run, monkeypatch, tmp_path):
    """Even on macOS, ~/.local/share (or $XDG_DATA_HOME) is used — not ~/Library/."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    _, data = run("db path")
    assert data["path"] == str(fake_home / ".local" / "share" / "kazoo" / "default.graph")


def test_xdg_data_home_env_var_wins(run, monkeypatch, tmp_path):
    custom = tmp_path / "elsewhere"
    monkeypatch.setenv("XDG_DATA_HOME", str(custom))
    _, data = run("db path")
    assert data["path"] == str(custom / "kazoo" / "default.graph")


# -- rename -------------------------------------------------------------------


def test_db_rename(run):
    run("db init")
    run("schema create-node Person --prop name:STRING --pk name")
    _, data = run("db rename default mygraph")
    assert data["renamed"] == "mygraph"
    _, listing = run("db list")
    assert listing["databases"] == ["mygraph"]
    _, snap = run("--db mygraph schema show")
    assert [n["name"] for n in snap["nodes"]] == ["Person"]


def test_db_rename_missing_source(run):
    result, _ = run("db rename ghost other", expect_ok=False)
    assert result.exit_code != 0


def test_db_rename_target_exists(run):
    run("db init")
    run("--db other db init")
    result, _ = run("db rename default other", expect_ok=False)
    assert result.exit_code != 0


# -- stats / rm ---------------------------------------------------------------


def _seed(run):
    run("db init")
    run("schema create-node Person --prop name:STRING --prop age:INT64 --pk name")
    run("schema create-node Movie --prop title:STRING --pk title")
    run("schema create-rel Likes --from Person --to Movie")
    run('query \'CREATE (:Person {name: "Alice", age: 30});\'')
    run('query \'CREATE (:Person {name: "Bob", age: 40});\'')
    run('query \'CREATE (:Movie {title: "Inception"});\'')


def test_db_stats(run):
    _seed(run)
    _, data = run("db stats")
    assert data["nodes"] == {"Person": 2, "Movie": 1}
    assert data["rels"] == {"Likes": 0}


def test_db_rm_requires_confirmation(run):
    run("db init")
    result, _ = run("db rm default", input="\n", expect_ok=False)
    assert result.exit_code != 0


def test_db_rm_with_yes(run):
    run("db init")
    _, data = run("db rm default --yes")
    assert data["removed"] == "default"
    _, listing = run("db list")
    assert listing["databases"] == []


def test_db_rm_missing(run):
    result, _ = run("db rm nonexistent --yes", expect_ok=False)
    assert result.exit_code != 0


# -- export / import (stdout / stdin) ----------------------------------------


def test_db_export_writes_bytes_to_stdout(run, runner):
    from kazoo.cli import app
    from kazoo.db import db_path

    _seed(run)
    result = runner.invoke(app, ["db", "export"])
    assert result.exit_code == 0
    raw = result.stdout_bytes if hasattr(result, "stdout_bytes") else result.stdout.encode("latin-1")
    assert len(raw) > 100
    assert raw == db_path(None).read_bytes()


def test_db_import_reads_bytes_from_stdin(run, runner):
    from kazoo.cli import app
    from kazoo.db import db_path

    _seed(run)
    payload = db_path(None).read_bytes()
    result = runner.invoke(app, ["--db", "copy", "db", "import"], input=payload)
    assert result.exit_code == 0
    _, listing = run("db list")
    assert "copy" in listing["databases"]
    _, stats_data = run("--db copy db stats")
    assert stats_data["nodes"]["Person"] == 2


def test_db_import_refuses_overwrite(run, runner):
    from kazoo.cli import app
    from kazoo.db import db_path

    _seed(run)
    payload = db_path(None).read_bytes()
    result = runner.invoke(app, ["db", "import"], input=payload)
    assert result.exit_code != 0
    assert "already exists" in result.stdout


def test_db_import_force_overwrites(run, runner):
    from kazoo.cli import app
    from kazoo.db import db_path

    _seed(run)
    payload = db_path(None).read_bytes()
    result = runner.invoke(app, ["db", "import", "--force"], input=payload)
    assert result.exit_code == 0


def test_db_import_empty_stdin_fails(run, runner):
    from kazoo.cli import app

    run("db init")
    result = runner.invoke(app, ["--db", "x", "db", "import"], input=b"")
    assert result.exit_code != 0


# -- --db can be a file path -------------------------------------------------


def test_db_flag_accepts_path(run, runner, tmp_path):
    """A --db value containing '/' or ending with .graph is treated as a file path."""
    from kazoo.cli import app
    from kazoo.db import db_path

    _seed(run)
    snapshot = tmp_path / "snap.graph"
    snapshot.write_bytes(db_path(None).read_bytes())
    result = runner.invoke(app, ["--db", str(snapshot), "db", "stats"])
    assert result.exit_code == 0, result.stdout
    import json as _json
    stats = _json.loads(result.stdout)
    assert stats["nodes"]["Person"] == 2


def test_db_flag_relative_dotgraph_is_path(run, tmp_path, monkeypatch):
    """`--db ./foo.graph` is a path, not a name; doesn't go under XDG."""
    from kazoo.db import db_path

    monkeypatch.chdir(tmp_path)
    p = db_path("./local.graph")
    assert p == (tmp_path / "local.graph").resolve() or p == tmp_path / "local.graph" or str(p).endswith("local.graph")


# -- info ---------------------------------------------------------------------


def test_info_empty_db(run):
    _, data = run("info")
    assert data["name"] == "default"
    assert data["exists"] is False
    assert "kazoo_version" in data
    assert "kuzu_version" in data


def test_info_populated_db(run):
    run("db init")
    run("schema create-node Person --prop name:STRING --pk name")
    run('query \'CREATE (:Person {name: "Alice"});\'')
    _, data = run("info")
    assert data["exists"] is True
    assert data["size_bytes"] > 0
    assert data["stats"]["nodes"]["Person"] == 1
    assert [n["name"] for n in data["schema"]["nodes"]] == ["Person"]
