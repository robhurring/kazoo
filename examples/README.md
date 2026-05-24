# Examples

Two ready-to-query graphs: an office org chart and a social network.

## Three ways to use them

### 1. Query directly from the .graph.gz snapshot (no install)

`--db <path>` accepts any file ending in `.graph`. Decompress on the fly:

```bash
gunzip -c examples/office/office.graph.gz > /tmp/office.graph
kazoo --db /tmp/office.graph schema show
kazoo --db /tmp/office.graph query 'MATCH (p:Person) RETURN p.name AS name ORDER BY name;'
```

### 2. Import into your XDG dir

Imports the snapshot as a managed DB so `kazoo --db office ...` just works:

```bash
./examples/build.sh           # imports both
./examples/build.sh office    # just office
```

### 3. Rebuild from cypher sources (source of truth)

```bash
./examples/build.sh --rebuild           # drop, re-seed, re-snapshot
./examples/build.sh --rebuild office
```

Each DB lands at `$XDG_DATA_HOME/kazoo/<name>.graph`
(default `~/.local/share/kazoo/<name>.graph`).

---

## Office graph

**Schema:** `Person`, `Team`, `Project` nodes; `MEMBER_OF`, `REPORTS_TO`, `WORKS_ON` rels.
**Source:** [`office/schema.cypher`](office/schema.cypher), [`office/seed.cypher`](office/seed.cypher)

```bash
# Everyone reporting (directly or transitively) to Grace Hopper
kazoo --db office query --param boss=2 \
  'MATCH (p:Person)-[:REPORTS_TO*1..]->(b:Person {id: $boss})
   RETURN p.name AS report, p.title AS title ORDER BY report;'

# Who works on the Graph DB rewrite, and at what allocation?
kazoo --db office query \
  'MATCH (p:Person)-[w:WORKS_ON]->(proj:Project {name: "Graph DB rewrite"})
   RETURN p.name AS person, w.role AS role, w.allocation_pct AS pct
   ORDER BY pct DESC;'

# Cross-team collaboration: pairs of people on the same project from different teams
kazoo --db office query \
  'MATCH (a:Person)-[:MEMBER_OF]->(ta:Team),
         (b:Person)-[:MEMBER_OF]->(tb:Team),
         (a)-[:WORKS_ON]->(p:Project)<-[:WORKS_ON]-(b)
   WHERE a.id < b.id AND ta.name <> tb.name
   RETURN p.name AS project, a.name AS person_a, ta.name AS team_a,
          b.name AS person_b, tb.name AS team_b
   ORDER BY project;'

# Dump the roster as CSV (write the Cypher you want, pipe through `query -f csv`)
kazoo --db office query \
  'MATCH (p:Person) RETURN p.id AS id, p.name AS name, p.title AS title;' \
  -f csv > roster.csv
```

---

## Social graph

**Schema:** `User`, `Post` nodes; `FOLLOWS`, `POSTED`, `LIKES` rels.
**Source:** [`social/schema.cypher`](social/schema.cypher), [`social/seed.cypher`](social/seed.cypher)

```bash
# Posts by people Ada (@ada) follows, newest first
kazoo --db social query \
  'MATCH (me:User {handle: "@ada"})-[:FOLLOWS]->(f:User)-[:POSTED]->(p:Post)
   RETURN f.handle AS author, p.title AS title, p.posted_at AS posted_at
   ORDER BY posted_at DESC;'

# Mutual follows
kazoo --db social query \
  'MATCH (a:User)-[:FOLLOWS]->(b:User)-[:FOLLOWS]->(a)
   WHERE a.id < b.id
   RETURN a.handle AS a, b.handle AS b ORDER BY a;'

# Friend-of-friend suggestions for @grace (people she doesn't already follow)
kazoo --db social query \
  'MATCH (me:User {handle: "@grace"})-[:FOLLOWS]->(f:User)-[:FOLLOWS]->(suggested:User)
   WHERE NOT (me)-[:FOLLOWS]->(suggested) AND me <> suggested
   RETURN DISTINCT suggested.handle AS handle, suggested.name AS name;'

# Most-liked posts
kazoo --db social query \
  'MATCH (p:Post)<-[l:LIKES]-()
   RETURN p.title AS title, count(l) AS likes
   ORDER BY likes DESC LIMIT 5;'
```

---

## Cleanup

```bash
kazoo --db office db rm --yes
kazoo --db social db rm --yes
```
