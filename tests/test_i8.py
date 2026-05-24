from __future__ import annotations

from pathlib import Path


def test_xdg_default_path_uses_dot_local_share(run, monkeypatch, tmp_path):
    """Even on macOS, ~/.local/share (or $XDG_DATA_HOME) is used — not ~/Library/."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    _, data = run("db path")
    assert data["path"] == str(fake_home / ".local" / "share" / "kazoo" / "default.graph")
    assert data["path"].endswith("default.graph")


def test_xdg_data_home_env_var_wins(run, monkeypatch, tmp_path):
    custom = tmp_path / "elsewhere"
    monkeypatch.setenv("XDG_DATA_HOME", str(custom))
    _, data = run("db path")
    assert data["path"] == str(custom / "kazoo" / "default.graph")


def test_db_extension_is_graph(run):
    _, data = run("db init")
    assert data["path"].endswith(".graph")


def test_schema_describe_node(run):
    run("db init")
    run("schema create-node Person --prop name:STRING --prop age:INT64 --pk name")
    _, data = run("schema describe Person")
    assert data["name"] == "Person"
    assert data["type"] == "NODE"
    assert {p["name"] for p in data["properties"]} == {"name", "age"}


def test_schema_describe_rel(run):
    run("db init")
    run("schema create-node A --prop id:INT64 --pk id")
    run("schema create-node B --prop id:INT64 --pk id")
    run("schema create-rel R --from A --to B")
    _, data = run("schema describe R")
    assert data["type"] == "REL"
    assert data["connections"] == [{"from": "A", "to": "B"}]


def test_schema_describe_unknown(run):
    run("db init")
    result, payload = run("schema describe Ghost", expect_ok=False)
    assert result.exit_code != 0
    assert "table not found" in payload["error"]
