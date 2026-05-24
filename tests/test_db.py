from __future__ import annotations


# -- init / info --------------------------------------------------------------


def test_db_init_default(run):
    _, data = run("db init")
    assert data["initialized"] == "default"
    assert data["path"].endswith("/default.graph")


def test_db_init_named(run):
    _, data = run("--db mygraph db init")
    assert data["initialized"] == "mygraph"


def test_db_extension_is_graph(run):
    _, data = run("db init")
    assert data["path"].endswith(".graph")


def test_info_reports_path_and_existence(run):
    _, data = run("info")
    assert data["name"] == "default"
    assert data["exists"] is False
    _, data = run("db init")
    _, data = run("info")
    assert data["exists"] is True
    assert data["path"].endswith("/default.graph")


def test_info_for_named_missing_db(run):
    _, data = run("--db ghost info")
    assert data["name"] == "ghost"
    assert data["exists"] is False


def test_db_name_rejects_special_segments(run):
    """Bare names like '..' or '.' are not valid DB names."""
    result, _ = run("--db .. info", expect_ok=False)
    assert result.exit_code != 0


def test_kazoo_db_env_var(run, monkeypatch):
    monkeypatch.setenv("KAZOO_DB", "fromenv")
    _, data = run("info")
    assert data["name"] == "fromenv"


# -- XDG path conventions -----------------------------------------------------


def test_xdg_default_path_uses_dot_local_share(run, monkeypatch, tmp_path):
    """Even on macOS, ~/.local/share (or $XDG_DATA_HOME) is used — not ~/Library/."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    _, data = run("info")
    assert data["path"] == str(fake_home / ".local" / "share" / "kazoo" / "default.graph")


def test_xdg_data_home_env_var_wins(run, monkeypatch, tmp_path):
    custom = tmp_path / "elsewhere"
    monkeypatch.setenv("XDG_DATA_HOME", str(custom))
    _, data = run("info")
    assert data["path"] == str(custom / "kazoo" / "default.graph")


# -- auto-create default ------------------------------------------------------


def test_default_db_auto_creates_on_query(run):
    """`kazoo query ...` with no --db auto-creates the default DB."""
    _, info0 = run("info")
    assert info0["exists"] is False
    _, rows = run("query 'RETURN 1 AS one;'")
    assert rows == [{"one": 1}]
    _, info1 = run("info")
    assert info1["exists"] is True


def test_named_db_does_not_auto_create(run):
    """An explicit --db points at a typed name; missing → error, no silent create."""
    result, payload = run("--db typo query 'RETURN 1;'", expect_ok=False)
    assert result.exit_code != 0
    assert "database does not exist" in payload["error"]


def test_kazoo_db_env_does_not_auto_create(run, monkeypatch):
    """$KAZOO_DB counts as explicit — also must exist."""
    monkeypatch.setenv("KAZOO_DB", "fromenv")
    result, _ = run("query 'RETURN 1;'", expect_ok=False)
    assert result.exit_code != 0


# -- rename -------------------------------------------------------------------


def test_db_rename(run):
    run("db init")
    run("schema create-node Person --prop name:STRING --pk name")
    _, data = run("db rename default mygraph")
    assert data["renamed"] == "mygraph"
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


# -- info with seeded data ---------------------------------------------------


def _seed(run):
    run("db init")
    run("schema create-node Person --prop name:STRING --prop age:INT64 --pk name")
    run("schema create-node Movie --prop title:STRING --pk title")
    run("schema create-rel Likes --from Person --to Movie")
    run('query \'CREATE (:Person {name: "Alice", age: 30});\'')
    run('query \'CREATE (:Person {name: "Bob", age: 40});\'')
    run('query \'CREATE (:Movie {title: "Inception"});\'')


def test_info_reports_schema_and_stats(run):
    _seed(run)
    _, data = run("info")
    assert data["stats"]["nodes"] == {"Person": 2, "Movie": 1}
    assert data["stats"]["rels"] == {"Likes": 0}
    assert {n["name"] for n in data["schema"]["nodes"]} == {"Person", "Movie"}


# -- rm -----------------------------------------------------------------------


def test_db_rm_requires_confirmation(run):
    run("db init")
    result, _ = run("db rm default", input="\n", expect_ok=False)
    assert result.exit_code != 0


def test_db_rm_with_yes(run):
    run("db init")
    _, data = run("db rm default --yes")
    assert data["removed"] == "default"
    from kazoo.db import db_path
    assert not db_path(None).exists()


def test_db_rm_missing(run):
    result, _ = run("db rm nonexistent --yes", expect_ok=False)
    assert result.exit_code != 0


# -- export / import (stdout / stdin) ----------------------------------------


def test_db_export_writes_gzipped_bytes(run, runner):
    """Export emits a gzipped (.grz) stream — magic bytes must be present."""
    import gzip

    from kazoo.cli import app
    from kazoo.db import db_path

    _seed(run)
    result = runner.invoke(app, ["db", "export"])
    assert result.exit_code == 0
    raw = result.stdout_bytes if hasattr(result, "stdout_bytes") else result.stdout.encode("latin-1")
    assert raw[:2] == b"\x1f\x8b"
    assert gzip.decompress(raw) == db_path(None).read_bytes()


def test_db_import_round_trips_via_export(run, runner):
    from kazoo.cli import app
    from kazoo.db import db_path

    _seed(run)
    src_bytes = db_path(None).read_bytes()
    export_result = runner.invoke(app, ["db", "export"])
    gz = export_result.stdout_bytes if hasattr(export_result, "stdout_bytes") else export_result.stdout.encode("latin-1")
    import_result = runner.invoke(app, ["--db", "copy", "db", "import"], input=gz)
    assert import_result.exit_code == 0, import_result.stdout
    assert db_path("copy").read_bytes() == src_bytes
    _, info = run("--db copy info")
    assert info["stats"]["nodes"]["Person"] == 2


def test_db_import_accepts_raw_graph(run, runner):
    from kazoo.cli import app
    from kazoo.db import db_path

    _seed(run)
    raw = db_path(None).read_bytes()
    result = runner.invoke(app, ["--db", "copy", "db", "import"], input=raw)
    assert result.exit_code == 0
    assert db_path("copy").read_bytes() == raw


def test_db_import_always_replaces(run, runner):
    from kazoo.cli import app
    from kazoo.db import db_path

    _seed(run)
    snapshot = db_path(None).read_bytes()
    run("data clear Person --yes")
    _, info0 = run("info")
    assert info0["stats"]["nodes"]["Person"] == 0
    result = runner.invoke(app, ["db", "import"], input=snapshot)
    assert result.exit_code == 0
    _, info1 = run("info")
    assert info1["stats"]["nodes"]["Person"] == 2


def test_db_import_empty_stdin_fails(runner):
    from kazoo.cli import app

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
    result = runner.invoke(app, ["--db", str(snapshot), "info"])
    assert result.exit_code == 0
    import json as _json
    info = _json.loads(result.stdout)
    assert info["stats"]["nodes"]["Person"] == 2


def test_db_flag_relative_dotgraph_is_path(monkeypatch, tmp_path):
    """`--db ./foo.graph` is a path, not a name; doesn't go under XDG."""
    from kazoo.db import db_path

    monkeypatch.chdir(tmp_path)
    p = db_path("./local.graph")
    assert str(p).endswith("local.graph")
    assert str(p) != "/local.graph"
