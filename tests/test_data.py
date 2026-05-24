from __future__ import annotations

from pathlib import Path


def test_data_load_csv(run, tmp_path):
    run("db init")
    run("schema create-node Person --prop name:STRING --prop age:INT64 --pk name")
    csv_path = tmp_path / "people.csv"
    csv_path.write_text("Alice,30\nBob,40\n")
    _, data = run(f"data load Person {csv_path}")
    assert data["loaded"] == "Person"
    _, stats = run("db stats")
    assert stats["nodes"]["Person"] == 2


def test_data_dump_table_csv(run, tmp_path, runner):
    from kazoo.cli import app

    run("db init")
    run("schema create-node Person --prop name:STRING --prop age:INT64 --pk name")
    csv_in = tmp_path / "in.csv"
    csv_in.write_text("Alice,30\nBob,40\n")
    run(f"data load Person {csv_in}")
    result = runner.invoke(app, ["data", "dump", "Person", "-f", "csv"])
    assert result.exit_code == 0, result.stdout
    assert "Alice" in result.stdout
    assert "Bob" in result.stdout


def test_data_dump_table_json(run, runner):
    from kazoo.cli import app

    run("db init")
    run("schema create-node Person --prop name:STRING --prop age:INT64 --pk name")
    run("query 'CREATE (:Person {name: \"Alice\", age: 30});'")
    result = runner.invoke(app, ["data", "dump", "Person"])
    assert result.exit_code == 0, result.stdout
    import json as _json
    rows = _json.loads(result.stdout)
    # Dump aliases properties to their bare names, not Kuzu's `n.col` prefix.
    assert isinstance(rows, list) and rows[0]["name"] == "Alice"


def test_data_dump_query(run, runner):
    from kazoo.cli import app

    run("db init")
    run("schema create-node Person --prop name:STRING --prop age:INT64 --pk name")
    run("query 'CREATE (:Person {name: \"Alice\", age: 30});'")
    result = runner.invoke(
        app,
        ["data", "dump", "(MATCH (p:Person) RETURN p.name AS n, p.age AS a)", "-f", "csv"],
    )
    assert result.exit_code == 0, result.stdout
    assert "Alice" in result.stdout


def test_data_load_invalid_table(run, tmp_path):
    run("db init")
    csv = tmp_path / "x.csv"
    csv.write_text("a,1\n")
    result, _ = run(f"data load 'bad name' {csv}", expect_ok=False)
    assert result.exit_code != 0


def test_data_dump_invalid_source(run):
    run("db init")
    result, data = run("data dump 'MATCH (n) RETURN n'", expect_ok=False)
    assert result.exit_code != 0
    assert "parenthesized" in data["error"]


def test_data_dump_csv_has_clean_header(run, runner):
    """A bare-table dump in CSV must use the schema's bare column names, not `n.col`."""
    from kazoo.cli import app

    run("db init")
    run("schema create-node Person --prop name:STRING --prop age:INT64 --pk name")
    run('query \'CREATE (:Person {name: "Alice", age: 30});\'')
    result = runner.invoke(app, ["data", "dump", "Person", "-f", "csv"])
    assert result.exit_code == 0
    header = result.stdout.splitlines()[0]
    assert header == "name,age"


def test_data_dump_unknown_format(run):
    run("db init")
    run("schema create-node Person --prop name:STRING --pk name")
    result, data = run("data dump Person -f yaml", expect_ok=False)
    assert result.exit_code != 0
    assert "unknown format" in data["error"]


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


def test_schema_apply_atomic_rolls_back(run, tmp_path):
    """A failing statement in --atomic mode must leave the schema untouched."""
    run("db init")
    bad = tmp_path / "bad.cypher"
    bad.write_text(
        "CREATE NODE TABLE A (id INT64, PRIMARY KEY (id));\n"
        "CREATE NODE TABLE A (id INT64, PRIMARY KEY (id));\n"  # duplicate
    )
    result, _ = run(f"schema apply {bad}", expect_ok=False)
    assert result.exit_code != 0
    _, snap = run("schema show")
    assert snap["nodes"] == []


def test_schema_apply_no_atomic_keeps_partial(run, tmp_path):
    run("db init")
    mixed = tmp_path / "mixed.cypher"
    mixed.write_text(
        "CREATE NODE TABLE A (id INT64, PRIMARY KEY (id));\n"
        "CREATE NODE TABLE A (id INT64, PRIMARY KEY (id));\n"
    )
    result, _ = run(f"schema apply {mixed} --no-atomic", expect_ok=False)
    assert result.exit_code != 0
    _, snap = run("schema show")
    assert [n["name"] for n in snap["nodes"]] == ["A"]
