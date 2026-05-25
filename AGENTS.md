# AGENTS.md — kazoo for autonomous agents

This document is a runbook for **AI agents and tooling** that drive `kazoo` programmatically. Humans can read it too. The contract: every kazoo command emits **JSON on stdout** by default and **non-zero exits with a single-line `{"error": "..."}` JSON object**. That's the whole interface — no spinners, no colored output, no interactive prompts unless you ask for them.

## What kazoo is

A small Python CLI wrapping [Kuzu](https://kuzudb.github.io/docs) — an embedded graph database that speaks Cypher. Databases are single files under `$XDG_DATA_HOME/kazoo/<name>.kuzu` (default `~/.local/share/kazoo/<name>.kuzu`).

If you're building an agent that needs a graph backing store — entity/relationship memory, knowledge graphs, plan-and-execute state, social graphs, dependency graphs — kazoo gives you a Cypher REPL and a scriptable CLI without standing up a server.

## Install

```bash
uv tool install kazoo                      # from PyPI
uv tool install --reinstall /path/to/repo  # from a checkout
```

## The shapes you can rely on

### Output discipline

- **Success:** JSON on stdout. `--pretty` to indent.
- **Failure:** non-zero exit, `{"error": "<message>"}` on stdout.
- **`query -f <format>`:** `json` (default), `ndjson` (one row per line — pipe-friendly), `csv`, `tsv`.
- **REPL** (`kazoo repl`): meta-commands (`\schema`, `\stats`, `\d <table>`, `\use <db>`, `\quit`) emit JSON; SQL/Cypher emits result rows.

### Exit codes

- `0`: success
- `1`: runtime error (Kuzu error, missing file, write error)
- `2`: validation error (bad arg, invalid identifier, conflicting flags)

### Picking a database

| Method | How |
|---|---|
| `--db <name>` flag | `kazoo --db ledger query "..."` |
| `--db <path>` flag | `kazoo --db ./snapshots/ledger.kuzu query "..."` |
| `KAZOO_DB` env | `KAZOO_DB=ledger kazoo query "..."` |
| Default | falls back to `default` |

If `--db` contains `/` or ends with `.kuzu` it's treated as a file path;
otherwise it must be a plain identifier (no slashes, no `..`, no empty string).

## Cheat sheet

```bash
# Create a DB and apply schema/data scripts
kazoo --db agent db init
kazoo --db agent schema apply           < schema.cypher
kazoo --db agent schema apply --no-atomic < seed.cypher

# Query inline / from stdin / with parameters
kazoo --db agent query 'MATCH (n:Entity) RETURN count(n) AS n;'
kazoo --db agent query < complex_query.cypher
kazoo --db agent query 'MATCH (e:Entity {id: $id}) RETURN e' --param id=42

# Streaming for big results (one JSON object per line)
kazoo --db agent query 'MATCH (n) RETURN n' -f ndjson | jq -c 'select(.n.type == "Person")'

# Plan / profile
kazoo --db agent query 'MATCH (a)-[:KNOWS*1..3]->(b) RETURN count(*)' --explain
kazoo --db agent query 'MATCH (a)-[:KNOWS*1..3]->(b) RETURN count(*)' --profile

# Inspect
kazoo --db agent info                     # version + path + size + schema + stats
kazoo --db agent schema show              # schema only
kazoo --db agent schema describe Person   # one table

# Bulk data
kazoo --db agent data load Person people.csv                                       # COPY FROM
kazoo --db agent query 'MATCH (n:Person) RETURN n.id, n.name;' -f csv > out.csv    # export query results
kazoo --db agent data clear Person --yes                                           # truncate

# Back up / restore a whole DB — it's a single file (path from `kazoo info`)
gzip   < ~/.local/share/kazoo/agent.kuzu > snapshot.kuzu.gz
gunzip < snapshot.kuzu.gz > ~/.local/share/kazoo/replica.kuzu

# Query a .kuzu file anywhere on disk directly (no copy into the XDG dir)
kazoo --db ./snapshot.kuzu schema show
```

## Conventions for building agents on kazoo

1. **One DB per concern.** Don't multiplex unrelated graphs into one DB. `--db <name>` is cheap; databases are isolated files.
2. **Define your schema explicitly.** Kuzu is strict — nodes require a primary key. Use `schema apply` with a checked-in DDL file rather than ad-hoc `CREATE NODE TABLE` calls scattered through code.
3. **Bind parameters, don't concatenate.** Use `--param name=value` to pass values into queries — values are parsed as JSON if possible, otherwise as strings.
4. **Stream large results.** Use `-f ndjson` and pipe to `jq`/`awk`/your reader. Avoid materializing huge JSON arrays.
5. **Snapshot by copying the file.** A DB is one self-contained `.kuzu` file — `cp`/`gzip` it to branch, share, or roll back agent state, and point `--db <path>` straight at any copy (no import step). Find the path with `kazoo info`.
6. **Treat `info` as your health check.** It returns kazoo + kuzu versions, the DB path, byte size, full schema, and per-table counts — everything an agent needs to verify state in one call.

## Errors agents should handle

- `{"error": "kuzu: ..."}` — Cypher or DDL error. Read the message and adjust the query.
- `{"error": "invalid <kind>: '...'"}` — identifier validation rejected your input. Sanitize before passing.
- `{"error": "database does not exist: ..."}` — call `db init` first.
- `{"error": "unknown table: '...'"}` — `schema describe` it before assuming it's there.

## Examples to learn from

[`examples/`](examples/) contains two ready-to-query graphs:

- **office** — people / teams / projects / reporting lines / project assignments.
- **social** — users / posts / follows / likes / timestamps.

Each ships as a committed `.kuzu` file you can query directly — e.g.
`kazoo --db ./examples/office/office.kuzu query '...'`. Sample queries are in
[`examples/README.md`](examples/README.md).

## Embedding kazoo

If your agent needs more than the CLI gives you, the same Python modules are importable:

```python
from kazoo.db import open_db
from kazoo.schema import show, stats
from kazoo.output import result_to_rows

conn = open_db("agent")
rows = result_to_rows(conn.execute("MATCH (n:Entity) RETURN n.id AS id, n.kind AS kind;"))
```

But the CLI/JSON contract is the stable surface — internal modules may change.

## Limits and quirks

- Kuzu node tables **require** a primary key. `schema create-node` enforces `--pk`.
- `data load` accepts CSV, Parquet, and JSON (the last requires Kuzu's `json` extension, which kazoo loads automatically when it sees a `.json`/`.ndjson`/`.jsonl` path).
- `schema apply` reads DDL from stdin and splits on `;` honoring strings (`'`, `"`, `` ` ``) and comments (`//`, `/* */`). Default is atomic — wraps in a transaction so partial failures roll back.
- For per-query CSV/TSV/NDJSON exports, write the Cypher you want and pipe `query -f <format>` to a file. `data dump` was removed because it overlapped with `query`. For whole-DB snapshots, copy the single `.kuzu` file (`cp`/`gzip`).

## Filing issues / contributing

The test suite is your friend — `uv run pytest`. New behavior wants a test. CLI changes should preserve the JSON-on-stdout contract above.
