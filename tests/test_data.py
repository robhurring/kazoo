from __future__ import annotations


# -- load (COPY FROM) ---------------------------------------------------------


def test_data_load_csv(run, tmp_path):
    run("db init")
    run("schema create-node Person --prop name:STRING --prop age:INT64 --pk name")
    csv_path = tmp_path / "people.csv"
    csv_path.write_text("Alice,30\nBob,40\n")
    _, data = run(f"data load Person {csv_path}")
    assert data["loaded"] == "Person"
    _, stats = run("db stats")
    assert stats["nodes"]["Person"] == 2


def test_data_load_invalid_table(run, tmp_path):
    run("db init")
    csv = tmp_path / "x.csv"
    csv.write_text("a,1\n")
    result, _ = run(f"data load 'bad name' {csv}", expect_ok=False)
    assert result.exit_code != 0


# -- clear (truncate) ---------------------------------------------------------


def test_data_clear_node_table(run):
    run("db init")
    run("schema create-node Person --prop name:STRING --pk name")
    run('query \'CREATE (:Person {name: "Alice"}), (:Person {name: "Bob"});\'')
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
    run("data clear R --yes")
    _, stats = run("db stats")
    assert stats["rels"]["R"] == 0
    assert stats["nodes"]["A"] == 1


def test_data_clear_unknown(run):
    run("db init")
    result, _ = run("data clear Ghost --yes", expect_ok=False)
    assert result.exit_code != 0
