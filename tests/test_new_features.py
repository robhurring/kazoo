from __future__ import annotations

import json
from pathlib import Path


def _setup_data(run):
    run("db init")
    run("schema create-node Person --prop name:STRING --prop age:INT64 --pk name")
    run("schema create-node Movie --prop title:STRING --pk title")
    run("schema create-rel Likes --from Person --to Movie")
    run("query 'CREATE (:Person {name: \"Alice\", age: 30});'")
    run("query 'CREATE (:Person {name: \"Bob\", age: 40});'")
    run("query 'CREATE (:Movie {title: \"Inception\"});'")


def test_ndjson_emits_one_object_per_line(run, runner):
    from kazoo.cli import app

    _setup_data(run)
    result = runner.invoke(
        app, ["query", "MATCH (p:Person) RETURN p.name AS name ORDER BY p.name;", "-f", "ndjson"]
    )
    assert result.exit_code == 0
    lines = [ln for ln in result.stdout.strip().splitlines() if ln]
    rows = [json.loads(ln) for ln in lines]
    assert rows == [{"name": "Alice"}, {"name": "Bob"}]


def test_db_stats(run):
    _setup_data(run)
    _, data = run("db stats")
    assert data["nodes"] == {"Person": 2, "Movie": 1}
    assert data["rels"] == {"Likes": 0}


def test_db_rm_requires_confirmation(run):
    run("db init")
    # Without --yes, confirm prompt gets no input -> aborted.
    result, data = run("db rm default", input="\n", expect_ok=False)
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


def test_db_backup_and_restore(run, tmp_path, monkeypatch):
    _setup_data(run)
    backup_dest = tmp_path / "backup.graph"
    _, data = run(f"db backup --out {backup_dest}")
    assert Path(data["to"]).exists()
    # Restore as a new DB name; original still present.
    _, restored = run(f"db restore {backup_dest} --as restored")
    assert restored["restored"] == "restored"
    _, listing = run("db list")
    assert "restored" in listing["databases"]
    assert "default" in listing["databases"]
    # The restored DB has the data.
    _, stats_data = run("--db restored db stats")
    assert stats_data["nodes"]["Person"] == 2


def test_db_restore_refuses_overwrite(run, tmp_path):
    _setup_data(run)
    backup_dest = tmp_path / "backup.graph"
    run(f"db backup --out {backup_dest}")
    result, _ = run(f"db restore {backup_dest} --as default", expect_ok=False)
    assert result.exit_code != 0


def test_db_backup_default_destination(run, tmp_path, monkeypatch):
    _setup_data(run)
    monkeypatch.chdir(tmp_path)
    _, data = run("db backup")
    out_path = Path(data["to"])
    assert out_path.parent == tmp_path
    assert out_path.suffix == ".graph"
    assert out_path.name.startswith("default-")
