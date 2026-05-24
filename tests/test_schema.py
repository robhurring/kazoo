from __future__ import annotations

from kazoo.schema import split_statements


# -- show / create / drop -----------------------------------------------------


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


# -- apply / export -----------------------------------------------------------


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


def test_apply_file_with_semicolon_in_string(run, tmp_path):
    run("db init")
    f = tmp_path / "data.cypher"
    f.write_text(
        "CREATE NODE TABLE Note (id INT64, body STRING, PRIMARY KEY (id));\n"
        "CREATE (:Note {id: 1, body: 'hello; world'});\n"
    )
    _, data = run(f"schema apply {f}")
    assert data["applied"] == 2
    _, rows = run("query 'MATCH (n:Note) RETURN n.body AS b;'")
    assert rows == [{"b": "hello; world"}]


def test_schema_export_round_trips(run):
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


# -- describe -----------------------------------------------------------------


def test_schema_describe_node(run):
    run("db init")
    run("schema create-node Person --prop name:STRING --prop age:INT64 --pk name")
    _, data = run("schema describe Person")
    assert data["name"] == "Person"
    assert data["type"] == "NODE"
    assert {p["name"] for p in data["properties"]} == {"name", "age"}


def test_schema_describe_rel(run):
    run("db init")
    run("schema create-node A --prop id:INT64 --pk id")
    run("schema create-node B --prop id:INT64 --pk id")
    run("schema create-rel R --from A --to B")
    _, data = run("schema describe R")
    assert data["type"] == "REL"
    assert data["connections"] == [{"from": "A", "to": "B"}]


def test_schema_describe_unknown(run):
    run("db init")
    result, payload = run("schema describe Ghost", expect_ok=False)
    assert result.exit_code != 0
    assert "table not found" in payload["error"]


# -- ALTER (add/drop column) --------------------------------------------------


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


# -- split_statements (unit) --------------------------------------------------


def test_split_simple():
    assert split_statements("CREATE A; CREATE B;") == ["CREATE A", "CREATE B"]


def test_split_no_trailing_semicolon():
    assert split_statements("RETURN 1") == ["RETURN 1"]


def test_split_ignores_semicolon_in_single_quote_string():
    assert split_statements("CREATE (:N {s: 'hello; world'}); RETURN 1;") == [
        "CREATE (:N {s: 'hello; world'})",
        "RETURN 1",
    ]


def test_split_ignores_semicolon_in_double_quote_string():
    assert split_statements('RETURN "a;b;c";') == ['RETURN "a;b;c"']


def test_split_ignores_semicolon_in_backtick():
    assert split_statements("RETURN `weird;name`;") == ["RETURN `weird;name`"]


def test_split_ignores_line_comment():
    assert split_statements("RETURN 1; // a; comment\nRETURN 2;") == [
        "RETURN 1",
        "// a; comment\nRETURN 2",
    ]


def test_split_ignores_block_comment():
    assert split_statements("RETURN 1; /* a; b; */ RETURN 2;") == [
        "RETURN 1",
        "/* a; b; */ RETURN 2",
    ]


def test_split_escape_in_string():
    assert split_statements("RETURN 'it\\'s; ok';") == ["RETURN 'it\\'s; ok'"]
