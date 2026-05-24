# kazoo

A CLI for [Kuzu](https://kuzudb.com/) graph databases. Query, manage schema, and inspect — all with JSON output.

## Install

```bash
uv tool install .
# or from a published package:
# uv tool install kazoo
```

## Quick start

```bash
# Run a Cypher query against the default DB
kazoo query "MATCH (n) RETURN n LIMIT 10"

# Use a named DB
kazoo --db mygraph query "MATCH (n) RETURN n"

# Pipe a query in
echo "MATCH (n) RETURN count(n)" | kazoo query

# Run a query file (Unix style: pipe it in)
kazoo query < queries/find_friends.cypher

# Pick an output format (default: json). Pipe to a file the Unix way.
kazoo query 'MATCH (p:Person) RETURN p' -f json   > people.json
kazoo query 'MATCH (p:Person) RETURN p' -f ndjson | jq .
kazoo query 'MATCH (p:Person) RETURN p.name, p.age' -f csv > people.csv
kazoo query 'MATCH (p:Person) RETURN p.name, p.age' -f tsv > people.tsv

# Interactive REPL (multi-line, ; terminates, \help for meta-commands)
kazoo repl

# Parameter binding (JSON values; bare strings ok). `-p` is an alias for --param.
kazoo query 'MATCH (p:Person {name: $who}) RETURN p' --param who=Alice
kazoo query 'MATCH (p:Person) WHERE p.age IN $ages RETURN p' --param ages='[30,40]'

# One-shot summary: version, db path, size, schema, stats
kazoo info

# Show the schema
kazoo schema show

# Plan / profile a query
kazoo query "MATCH (p:Person) RETURN p" --explain
kazoo query "MATCH (p:Person) RETURN p" --profile

# Apply DDL from stdin (atomic by default — rolls back on partial failure)
kazoo schema apply              < schema.cypher
kazoo schema apply --no-atomic  < schema.cypher   # apply best-effort, keep partial

# Export the schema as Cypher DDL
kazoo schema export

# Create a node table
kazoo schema create-node Person --prop name:STRING --prop age:INT64 --pk name

# Idempotent (no error if it already exists)
kazoo schema create-node Person --prop name:STRING --pk name --if-not-exists

# Create a relationship table
kazoo schema create-rel Follows --from Person --to Person --prop since:DATE

# Alter a table
kazoo schema add-column Person bio:STRING
kazoo schema add-column Person score:INT64 --default 0
kazoo schema drop-column Person score

# Drop a table (with optional idempotency)
kazoo schema drop Person --if-exists

# List databases / show DB path / counts
kazoo db list
kazoo db path mygraph
kazoo db stats

# Snapshot a whole DB (schema+data, gzipped) and restore it elsewhere
kazoo --db mydb db export > last-backup.grz
kazoo --db imported db import < last-backup.grz   # always replaces

# Rename / delete
kazoo db rename old new
kazoo db rm imported --yes

# Bulk-load (CSV / Parquet / JSON auto-detected from extension)
kazoo data load Person people.csv

# Truncate a table
kazoo data clear Person --yes

# Shell completion — eval in your shell's rc file
# ~/.zshrc:
eval "$(kazoo completions zsh)"
# ~/.bashrc:
eval "$(kazoo completions bash)"
# fish needs a file (its completion loader scans this dir):
kazoo completions fish > ~/.config/fish/completions/kazoo.fish
```

## Database locations

Databases live under `$XDG_DATA_HOME/kazoo/` (defaults to `~/.local/share/kazoo/` on every OS, including macOS).

- Default DB: `$XDG_DATA_HOME/kazoo/default.graph`
- Named DBs: `$XDG_DATA_HOME/kazoo/<name>.graph`

`--db` accepts either a bare name (resolved under the XDG dir) or a path to a
`.graph` file (anything containing `/` or ending in `.graph` is taken as-is).

## File types

| Extension | What it is |
|-----------|------------|
| `.graph`  | A live Kuzu database — schema, nodes, rels, indexes, everything. This is what `--db` reads. |
| `.grz`    | A gzipped snapshot of a `.graph` produced by `db export`. Pipe one back into `db import` to recreate the DB elsewhere. |

Select with `--db <name>` or `$KAZOO_DB`.

## Output

All commands emit JSON to stdout. Use `--pretty` for indented output.

## Examples

Two ready-to-query graphs ship in [`examples/`](examples/) — an office org chart and a social network. Import either snapshot in one line:

```bash
kazoo --db office db import < examples/office/office.grz
kazoo --db social db import < examples/social/social.grz
```

Sample queries and a `build.sh` helper live in [`examples/README.md`](examples/README.md).

## For agents

Building something that drives kazoo programmatically? [`AGENTS.md`](AGENTS.md) documents the JSON-on-stdout contract, exit codes, error shapes, and conventions for using kazoo as a graph backing store.
