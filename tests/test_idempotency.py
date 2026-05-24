from __future__ import annotations


def test_create_node_if_not_exists_idempotent(run):
    run("db init")
    run("schema create-node Person --prop name:STRING --pk name")
    _, data = run(
        "schema create-node Person --prop name:STRING --pk name --if-not-exists"
    )
    assert data["created"] == "NODE"


def test_create_node_duplicate_fails_without_flag(run):
    run("db init")
    run("schema create-node Person --prop name:STRING --pk name")
    result, data = run(
        "schema create-node Person --prop name:STRING --pk name",
        expect_ok=False,
    )
    assert result.exit_code != 0
    assert "kuzu" in data["error"].lower() or "exist" in data["error"].lower()


def test_drop_if_exists_idempotent(run):
    run("db init")
    _, data = run("schema drop NonExistent --if-exists")
    assert data["dropped"] == "NonExistent"


def test_drop_without_flag_fails(run):
    run("db init")
    result, _ = run("schema drop NonExistent", expect_ok=False)
    assert result.exit_code != 0


def test_create_rel_if_not_exists(run):
    run("db init")
    run("schema create-node A --prop id:INT64 --pk id")
    run("schema create-node B --prop id:INT64 --pk id")
    run("schema create-rel R --from A --to B")
    _, data = run("schema create-rel R --from A --to B --if-not-exists")
    assert data["created"] == "REL"
