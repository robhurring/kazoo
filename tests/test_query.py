from __future__ import annotations


def _setup(run):
    run("db init")
    run("schema create-node Person --prop name:STRING --prop age:INT64 --pk name")


def test_query_inline(run):
    _setup(run)
    run("query 'CREATE (:Person {name: \"Alice\", age: 30});'")
    _, data = run("query 'MATCH (p:Person) RETURN p.name AS name, p.age AS age;'")
    assert data == [{"name": "Alice", "age": 30}]


def test_query_from_stdin(run):
    _setup(run)
    run(
        "query",
        input='CREATE (:Person {name: "Bob", age: 40});',
    )
    _, data = run("query 'MATCH (p:Person) RETURN p.name AS name;'")
    assert data == [{"name": "Bob"}]


def test_query_from_file(run, tmp_path):
    _setup(run)
    q = tmp_path / "q.cypher"
    q.write_text('CREATE (:Person {name: "Carol", age: 50});')
    run(f"query --file {q}")
    q2 = tmp_path / "find.cypher"
    q2.write_text("MATCH (p:Person) RETURN p.name AS name;")
    _, data = run(f"query --file {q2}")
    assert data == [{"name": "Carol"}]


def test_query_empty_stdin(run):
    _setup(run)
    result, data = run("query", input="", expect_ok=False)
    assert result.exit_code != 0
    assert "empty query" in data["error"]


def test_query_arg_and_file_conflict(run, tmp_path):
    _setup(run)
    q = tmp_path / "q.cypher"
    q.write_text("MATCH (p:Person) RETURN p.name;")
    result, _ = run(f"query 'MATCH (n) RETURN n' --file {q}", expect_ok=False)
    assert result.exit_code != 0
