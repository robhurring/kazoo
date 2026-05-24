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


def test_db_backup_writes_bytes_to_stdout(run, runner, tmp_path):
    """`db backup` streams the DB file bytes to stdout."""
    from kazoo.cli import app

    _setup_data(run)
    # Capture binary stdout
    import sys
    import io

    # CliRunner's stdout is text-mode by default; for binary it stashes raw bytes too.
    result = runner.invoke(app, ["db", "backup"])
    assert result.exit_code == 0
    # stdout_bytes attribute holds raw bytes
    raw = result.stdout_bytes if hasattr(result, "stdout_bytes") else result.stdout.encode("latin-1")
    assert len(raw) > 100, "expected non-trivial DB file content"
    # Round-trip: write to temp file and verify it's the same as the source.
    expected = (tmp_path / "ref.graph")
    from kazoo.db import db_path
    expected.write_bytes(db_path(None).read_bytes())
    assert raw == expected.read_bytes()


def test_db_restore_reads_bytes_from_stdin(run, runner):
    """`db restore` reads bytes from stdin into the active DB."""
    from kazoo.cli import app
    from kazoo.db import db_path

    _setup_data(run)
    payload = db_path(None).read_bytes()
    result = runner.invoke(app, ["--db", "copy", "db", "restore"], input=payload)
    assert result.exit_code == 0, result.stdout
    _, listing = run("db list")
    assert "copy" in listing["databases"]
    _, stats_data = run("--db copy db stats")
    assert stats_data["nodes"]["Person"] == 2


def test_db_restore_refuses_overwrite(run, runner):
    from kazoo.cli import app
    from kazoo.db import db_path

    _setup_data(run)
    payload = db_path(None).read_bytes()
    result = runner.invoke(app, ["db", "restore"], input=payload)
    assert result.exit_code != 0
    assert "already exists" in result.stdout


def test_db_restore_force_overwrites(run, runner):
    from kazoo.cli import app
    from kazoo.db import db_path

    _setup_data(run)
    payload = db_path(None).read_bytes()
    # Force-restoring onto default itself should succeed.
    result = runner.invoke(app, ["db", "restore", "--force"], input=payload)
    assert result.exit_code == 0


def test_db_restore_without_stdin_fails(run, runner):
    """In TTY mode (no piped input), restore must refuse rather than hang."""
    from kazoo.cli import app

    run("db init")
    # No `input=` so stdin remains a TTY-ish in CliRunner; runner forces stdin closed.
    result = runner.invoke(app, ["db", "restore"])
    # With CliRunner, stdin.isatty() is True by default — bail expected.
    assert result.exit_code != 0
