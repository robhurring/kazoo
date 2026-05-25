from __future__ import annotations


# -- init / info --------------------------------------------------------------


def test_db_init_default(run):
    _, data = run("db init")
    assert data["initialized"] == "default"
    assert data["path"].endswith("/default.kuzu")


def test_db_init_named(run):
    _, data = run("--db mygraph db init")
    assert data["initialized"] == "mygraph"


def test_db_extension_is_kuzu(run):
    _, data = run("db init")
    assert data["path"].endswith(".kuzu")


def test_info_reports_path_and_existence(run):
    _, data = run("info")
    assert data["name"] == "default"
    assert data["exists"] is False
    _, data = run("db init")
    _, data = run("info")
    assert data["exists"] is True
    assert data["path"].endswith("/default.kuzu")


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
    assert data["path"] == str(fake_home / ".local" / "share" / "kazoo" / "default.kuzu")


def test_xdg_data_home_env_var_wins(run, monkeypatch, tmp_path):
    custom = tmp_path / "elsewhere"
    monkeypatch.setenv("XDG_DATA_HOME", str(custom))
    _, data = run("info")
    assert data["path"] == str(custom / "kazoo" / "default.kuzu")


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


# -- --db can be a file path -------------------------------------------------


def test_db_flag_accepts_path(run, runner, tmp_path):
    """A --db value containing '/' or ending with .kuzu is treated as a file path."""
    from kazoo.cli import app
    from kazoo.db import db_path

    _seed(run)
    snapshot = tmp_path / "snap.kuzu"
    snapshot.write_bytes(db_path(None).read_bytes())
    result = runner.invoke(app, ["--db", str(snapshot), "info"])
    assert result.exit_code == 0
    import json as _json
    info = _json.loads(result.stdout)
    assert info["stats"]["nodes"]["Person"] == 2


def test_db_flag_relative_dotkuzu_is_path(monkeypatch, tmp_path):
    """`--db ./foo.kuzu` is a path, not a name; doesn't go under XDG."""
    from kazoo.db import db_path

    monkeypatch.chdir(tmp_path)
    p = db_path("./local.kuzu")
    assert str(p).endswith("local.kuzu")
    assert str(p) != "/local.kuzu"


# -- committed example databases ---------------------------------------------


def test_example_databases_query_in_place(tmp_path):
    """The committed example .kuzu files open on the current Kuzu, return data,
    and a read query (via a real CLI process) leaves the file byte-identical —
    so exploring an example never dirties the working tree.

    Uses a subprocess, not the in-process runner: Kuzu sets a transient "open"
    header flag that is only cleared when the process exits and the database
    closes, which an in-process invoke wouldn't observe.
    """
    import hashlib
    import json as _json
    import shutil
    import subprocess
    import sys
    from pathlib import Path

    examples = Path(__file__).resolve().parent.parent / "examples"
    for name in ("office/office.kuzu", "social/social.kuzu"):
        src = examples / name
        assert src.exists(), f"missing committed example: {src}"
        # Copy out of the repo so a stray .wal can't touch the working tree.
        work = tmp_path / Path(name).name
        shutil.copy2(src, work)
        before = hashlib.sha256(work.read_bytes()).hexdigest()
        proc = subprocess.run(
            [sys.executable, "-m", "kazoo", "--db", str(work), "query", "MATCH (n) RETURN count(n) AS n;"],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
        rows = _json.loads(proc.stdout)
        assert rows[0]["n"] > 0
        assert hashlib.sha256(work.read_bytes()).hexdigest() == before, "read query mutated the database file"


# -- explore (Kuzu Explorer via Docker) --------------------------------------


def test_explorer_command_builds_docker_argv(run):
    from kazoo.db import db_path, explorer_command

    _seed(run)
    path = db_path(None)
    cmd = explorer_command(None, port=9999)
    assert cmd[:3] == ["docker", "run", "--rm"]
    assert "9999:8000" in cmd
    assert f"{path.parent.resolve()}:/database" in cmd
    assert f"KUZU_FILE={path.name}" in cmd
    assert cmd[-1] == "kuzudb/explorer:latest"


def test_explorer_command_missing_db():
    import pytest

    from kazoo.db import explorer_command

    with pytest.raises(FileNotFoundError):
        explorer_command("ghost")
