# kazoo

```
●       ●
│      ╱
●     ●
│    ╱           k a z o o
●───●        ────────────────────────
│    ╲       a CLI for Kuzu graph DBs
●     ●
│      ╲
●       ●
```

A CLI for [Kuzu](https://kuzudb.github.io/docs) graph databases. Query, manage, explore, and inspect.

A composable shell wrapper around Kuzu, so the AI tools on your machine can build and query graphs without an SDK or a server.

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

# Query from a file
kazoo query < queries/find_friends.cypher

# Output formats
kazoo query 'MATCH (p:Person) RETURN p' -f json   > people.json
kazoo query 'MATCH (p:Person) RETURN p' -f ndjson | jq .
kazoo query 'MATCH (p:Person) RETURN p.name, p.age' -f csv > people.csv
kazoo query 'MATCH (p:Person) RETURN p.name, p.age' -f tsv > people.tsv

# Interactive REPL
kazoo repl

# Visual exploration in the browser (Kuzu Explorer via Docker; requires Docker)
kazoo --db mydb explore            # prompts to open http://localhost:8000
kazoo --db mydb explore --port 9000 --no-open

# Parameter binding
kazoo query 'MATCH (p:Person {name: $who}) RETURN p' --param who=Alice
kazoo query 'MATCH (p:Person) WHERE p.age IN $ages RETURN p' --param ages='[30,40]'

# Summary
kazoo info

# Show the schema
kazoo schema show

# Plan / profile a query
kazoo query "MATCH (p:Person) RETURN p" --explain
kazoo query "MATCH (p:Person) RETURN p" --profile

# Apply DDL
kazoo schema apply             < schema.cypher
kazoo schema apply --no-atomic < schema.cypher

# Export the schema as Cypher DDL
kazoo schema export

# Create a node table
kazoo schema create-node Person --prop name:STRING --prop age:INT64 --pk name
kazoo schema create-node Person --prop name:STRING --pk name --if-not-exists

# Create a relationship table
kazoo schema create-rel Follows --from Person --to Person --prop since:DATE

# Alter a table
kazoo schema add-column Person bio:STRING
kazoo schema add-column Person score:INT64 --default 0
kazoo schema drop-column Person score

# Drop a table
kazoo schema drop Person --if-exists

# Back up / restore — a DB is a single file (find it with `kazoo info`)
gzip   < ~/.local/share/kazoo/mydb.kuzu > last-backup.kuzu.gz
gunzip < last-backup.kuzu.gz > ~/.local/share/kazoo/mydb.kuzu

# Rename / delete
mv ~/.local/share/kazoo/old.kuzu ~/.local/share/kazoo/new.kuzu   # rename
kazoo db rm imported --yes                                        # delete (guarded)

# Bulk-load
kazoo data load Person people.csv

# Truncate a table
kazoo data clear Person --yes

# Shell completion
# ~/.zshrc:
eval "$(kazoo completions zsh)"
# ~/.bashrc:
eval "$(kazoo completions bash)"
# fish:
kazoo completions fish > ~/.config/fish/completions/kazoo.fish
```

## Database locations

Databases live under `$XDG_DATA_HOME/kazoo/` (defaults to `~/.local/share/kazoo/` on every OS, including macOS).

- Default DB: `$XDG_DATA_HOME/kazoo/default.kuzu` — auto-created on first use, no setup needed.
- Named DBs: `$XDG_DATA_HOME/kazoo/<name>.kuzu` — must be initialized explicitly (`kazoo --db <name> db init`).

`--db` accepts either a bare name (resolved under the XDG dir) or a path to a `.kuzu` file (anything containing `/` or ending in `.kuzu` is taken as-is). `$KAZOO_DB` selects the same way.

Pointing at a missing named DB errors instead of silently creating one — that's only the default's behavior.

## File types

| Extension | What it is |
|-----------|------------|
| `.kuzu`   | A live Kuzu database — schema, nodes, rels, indexes, everything. This is what `--db` reads. |

Select with `--db <name>` or `$KAZOO_DB`. A `.kuzu` file is self-contained: back it up with `cp`/`gzip`, move it with `mv`.

## Output

All commands emit JSON to stdout. Use `--pretty` for indented output.

## Examples

Two ready-to-query graphs ship in [`examples/`](examples/) — an office org chart and a social network. Point `--db` straight at the committed database file:

```bash
kazoo --db ./examples/office/office.kuzu query 'MATCH (p:Person) RETURN p.name;'
kazoo --db ./examples/social/social.kuzu query 'MATCH (u:User) RETURN u.handle;'
```

More sample queries live in [`examples/README.md`](examples/README.md).

## For agents

Building something that drives kazoo programmatically? [`AGENTS.md`](AGENTS.md) documents the JSON-on-stdout contract, exit codes, error shapes, and conventions for using kazoo as a graph backing store.
