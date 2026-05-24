from __future__ import annotations

import json


def _setup(run):
    run("db init")
    run("schema create-node Person --prop name:STRING --prop age:INT64 --pk name")


# -- input shape --------------------------------------------------------------


def test_query_inline(run):
    _setup(run)
    run('query \'CREATE (:Person {name: "Alice", age: 30});\'')
    _, data = run("query 'MATCH (p:Person) RETURN p.name AS name, p.age AS age;'")
    assert data == [{"name": "Alice", "age": 30}]


def test_query_from_stdin(run):
    _setup(run)
    run("query", input='CREATE (:Person {name: "Bob", age: 40});')
    _, data = run("query 'MATCH (p:Person) RETURN p.name AS name;'")
    assert data == [{"name": "Bob"}]


def test_query_from_stdin_file_redirect(run):
    """No --file flag: pipe a file in via stdin (Unix idiom)."""
    _setup(run)
    run("query", input='CREATE (:Person {name: "Carol", age: 50});')
    _, data = run("query", input="MATCH (p:Person) RETURN p.name AS name;")
    assert data == [{"name": "Carol"}]


def test_query_empty_stdin(run):
    _setup(run)
    result, data = run("query", input="", expect_ok=False)
    assert result.exit_code != 0
    assert "empty query" in data["error"]


# -- output formats -----------------------------------------------------------


def test_query_format_csv(run, runner):
    from kazoo.cli import app

    _setup(run)
    run('query \'CREATE (:Person {name: "Alice"});\'')
    result = runner.invoke(
        app, ["query", "MATCH (p:Person) RETURN p.name AS name;", "-f", "csv"]
    )
    assert result.exit_code == 0
    assert result.stdout.strip().splitlines() == ["name", "Alice"]


def test_query_format_tsv(run, runner):
    from kazoo.cli import app

    _setup(run)
    run('query \'CREATE (:Person {name: "Alice"});\'')
    result = runner.invoke(
        app, ["query", "MATCH (p:Person) RETURN p.name AS name;", "-f", "tsv"]
    )
    assert result.exit_code == 0
    assert result.stdout.strip().splitlines() == ["name", "Alice"]


def test_query_format_ndjson(run, runner):
    from kazoo.cli import app

    _setup(run)
    run('query \'CREATE (:Person {name: "Alice", age: 30});\'')
    run('query \'CREATE (:Person {name: "Bob", age: 40});\'')
    result = runner.invoke(
        app,
        ["query", "MATCH (p:Person) RETURN p.name AS name ORDER BY p.name;", "-f", "ndjson"],
    )
    assert result.exit_code == 0
    rows = [json.loads(ln) for ln in result.stdout.strip().splitlines() if ln]
    assert rows == [{"name": "Alice"}, {"name": "Bob"}]


def test_query_unknown_format(run):
    _setup(run)
    result, data = run("query 'RETURN 1;' -f yaml", expect_ok=False)
    assert result.exit_code != 0
    assert "unknown format" in data["error"]


# -- explain / profile --------------------------------------------------------


def test_query_explain(run):
    run("db init")
    run("schema create-node Person --prop name:STRING --pk name")
    _, data = run("query 'MATCH (p:Person) RETURN p' --explain")
    assert isinstance(data, list)
    assert len(data) >= 1


def test_query_explain_and_profile_conflict(run):
    run("db init")
    result, _ = run("query 'RETURN 1' --explain --profile", expect_ok=False)
    assert result.exit_code != 0
