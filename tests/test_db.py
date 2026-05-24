from __future__ import annotations


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


def test_db_path_rejects_separator(run):
    result, _ = run("--db ../escape db path", expect_ok=False)
    assert result.exit_code != 0


def test_kazoo_db_env_var(run, monkeypatch):
    monkeypatch.setenv("KAZOO_DB", "fromenv")
    _, data = run("db path")
    assert data["name"] == "fromenv"
