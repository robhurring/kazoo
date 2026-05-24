from __future__ import annotations


def _setup(run):
    run("db init")
    run("schema create-node Person --prop name:STRING --prop age:INT64 --pk name")
    run("query 'CREATE (:Person {name: \"Alice\", age: 30});'")
    run("query 'CREATE (:Person {name: \"Bob\", age: 40});'")


def test_query_with_string_param(run):
    _setup(run)
    _, data = run(
        "query 'MATCH (p:Person {name: $who}) RETURN p.age AS age;' --param who=Alice"
    )
    assert data == [{"age": 30}]


def test_query_with_int_param(run):
    _setup(run)
    _, data = run(
        "query 'MATCH (p:Person) WHERE p.age > $min RETURN p.name AS name ORDER BY p.name;' --param min=35"
    )
    assert data == [{"name": "Bob"}]


def test_query_param_json_value(run):
    _setup(run)
    _, data = run(
        'query \'MATCH (p:Person) WHERE p.age IN $ages RETURN p.name AS name ORDER BY p.name;\' --param ages=[30,40]'
    )
    assert [r["name"] for r in data] == ["Alice", "Bob"]


def test_param_invalid_spec(run):
    _setup(run)
    result, data = run("query 'RETURN 1' --param noequals", expect_ok=False)
    assert result.exit_code != 0
    assert "NAME=VALUE" in data["error"]
