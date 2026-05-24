from __future__ import annotations


def test_schema_show_empty(run):
    run("db init")
    _, data = run("schema show")
    assert data == {"nodes": [], "rels": []}


def test_create_node_requires_pk(run):
    run("db init")
    result, data = run(
        "schema create-node Note --prop body:STRING",
        expect_ok=False,
    )
    assert result.exit_code != 0
    assert "primary key" in data["error"].lower() or "--pk" in data["error"]


def test_create_node_and_show(run):
    run("db init")
    _, data = run("schema create-node Person --prop name:STRING --prop age:INT64 --pk name")
    assert data["created"] == "NODE"
    _, snap = run("schema show")
    assert [n["name"] for n in snap["nodes"]] == ["Person"]
    props = {p["name"]: p for p in snap["nodes"][0]["properties"]}
    assert props["name"]["primary_key"] is True
    assert props["age"]["primary_key"] is False


def test_create_rel(run):
    run("db init")
    run("schema create-node Person --prop name:STRING --pk name")
    run("schema create-node Movie --prop title:STRING --pk title")
    _, data = run("schema create-rel Likes --from Person --to Movie --prop since:DATE")
    assert data["created"] == "REL"
    _, snap = run("schema show")
    assert [r["name"] for r in snap["rels"]] == ["Likes"]
    assert snap["rels"][0]["connections"] == [{"from": "Person", "to": "Movie"}]


def test_schema_apply_from_file(run, tmp_path):
    run("db init")
    schema_file = tmp_path / "schema.cypher"
    schema_file.write_text(
        "CREATE NODE TABLE A (id INT64, PRIMARY KEY (id));\n"
        "CREATE NODE TABLE B (id INT64, PRIMARY KEY (id));\n"
        "CREATE REL TABLE R (FROM A TO B);\n"
    )
    _, data = run(f"schema apply {schema_file}")
    assert data["applied"] == 3
    _, snap = run("schema show")
    assert {n["name"] for n in snap["nodes"]} == {"A", "B"}
    assert [r["name"] for r in snap["rels"]] == ["R"]


def test_schema_export_round_trips(run, tmp_path):
    run("db init")
    run("schema create-node Person --prop name:STRING --pk name")
    run("schema create-node Movie --prop title:STRING --pk title")
    run("schema create-rel Likes --from Person --to Movie")
    result, _ = run("schema export")
    ddl = result.stdout
    assert "CREATE NODE TABLE Person" in ddl
    assert "CREATE NODE TABLE Movie" in ddl
    assert "CREATE REL TABLE Likes" in ddl
    assert "FROM Person TO Movie" in ddl


def test_schema_drop(run):
    run("db init")
    run("schema create-node Person --prop name:STRING --pk name")
    _, data = run("schema drop Person")
    assert data["dropped"] == "Person"
    _, snap = run("schema show")
    assert snap["nodes"] == []


def test_invalid_identifiers_are_rejected(run):
    run("db init")
    result, data = run(
        "schema create-node 'bad name' --prop x:INT64 --pk x", expect_ok=False
    )
    assert result.exit_code != 0
    assert "invalid" in data["error"].lower()


def test_invalid_prop_spec(run):
    run("db init")
    result, data = run(
        "schema create-node Person --prop badspec --pk badspec", expect_ok=False
    )
    assert result.exit_code != 0
    assert "NAME:TYPE" in data["error"]
