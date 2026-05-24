from __future__ import annotations


def test_info_empty_db(run):
    _, data = run("info")
    assert data["name"] == "default"
    assert data["exists"] is False
    assert "kazoo_version" in data
    assert "kuzu_version" in data


def test_info_populated_db(run):
    run("db init")
    run("schema create-node Person --prop name:STRING --pk name")
    run("query 'CREATE (:Person {name: \"Alice\"});'")
    _, data = run("info")
    assert data["exists"] is True
    assert data["size_bytes"] > 0
    assert data["stats"]["nodes"]["Person"] == 1
    assert [n["name"] for n in data["schema"]["nodes"]] == ["Person"]


def test_schema_add_column(run):
    run("db init")
    run("schema create-node Person --prop name:STRING --pk name")
    _, data = run("schema add-column Person bio:STRING")
    assert data["added"] == "bio"
    _, snap = run("schema show")
    cols = {p["name"] for p in snap["nodes"][0]["properties"]}
    assert "bio" in cols


def test_schema_drop_column(run):
    run("db init")
    run("schema create-node Person --prop name:STRING --prop age:INT64 --pk name")
    _, data = run("schema drop-column Person age")
    assert data["dropped"] == "age"
    _, snap = run("schema show")
    cols = {p["name"] for p in snap["nodes"][0]["properties"]}
    assert cols == {"name"}


def test_schema_add_column_with_default(run):
    run("db init")
    run("schema create-node Person --prop name:STRING --pk name")
    _, data = run("schema add-column Person score:INT64 --default 0")
    assert "DEFAULT 0" in data["ddl"]


def test_data_clear_node_table(run):
    run("db init")
    run("schema create-node Person --prop name:STRING --pk name")
    run("query 'CREATE (:Person {name: \"Alice\"}), (:Person {name: \"Bob\"});'")
    _, data = run("data clear Person --yes")
    assert data["cleared"] == "Person"
    _, stats = run("db stats")
    assert stats["nodes"]["Person"] == 0


def test_data_clear_rel_table(run):
    run("db init")
    run("schema create-node A --prop id:INT64 --pk id")
    run("schema create-node B --prop id:INT64 --pk id")
    run("schema create-rel R --from A --to B")
    run("query 'CREATE (:A {id:1}), (:B {id:2});'")
    run("query 'MATCH (a:A {id:1}), (b:B {id:2}) CREATE (a)-[:R]->(b);'")
    _, _ = run("data clear R --yes")
    _, stats = run("db stats")
    assert stats["rels"]["R"] == 0
    # nodes untouched
    assert stats["nodes"]["A"] == 1


def test_data_clear_unknown(run):
    run("db init")
    result, _ = run("data clear Ghost --yes", expect_ok=False)
    assert result.exit_code != 0


def test_query_explain(run):
    run("db init")
    run("schema create-node Person --prop name:STRING --pk name")
    _, data = run("query 'MATCH (p:Person) RETURN p' --explain")
    assert isinstance(data, list)
    # EXPLAIN should return a non-empty plan structure.
    assert len(data) >= 1


def test_query_explain_and_profile_conflict(run):
    run("db init")
    result, _ = run("query 'RETURN 1' --explain --profile", expect_ok=False)
    assert result.exit_code != 0
