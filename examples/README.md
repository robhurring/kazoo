# Examples

Two ready-to-query graphs: an office org chart and a social network. Each ships
as a committed Kuzu database file — point `--db` straight at it, no import step:

```bash
kazoo --db ./examples/office/office.kuzu query 'MATCH (p:Person) RETURN p.name;'
kazoo --db ./examples/social/social.kuzu query 'MATCH (u:User) RETURN u.handle;'
```

These files are built with the repo's current Kuzu version. A read query leaves
them untouched; a write query will modify them, so copy one elsewhere first if
you want to experiment. Inspect the schema any time with `schema export`:

```bash
kazoo --db ./examples/office/office.kuzu schema export
```

---

## Office graph

**Schema:** `Person`, `Team`, `Project` nodes; `MEMBER_OF`, `REPORTS_TO`, `WORKS_ON` rels.

```bash
# Everyone reporting (directly or transitively) to Grace Hopper
kazoo --db ./examples/office/office.kuzu query --param boss='Grace Hopper' \
  'MATCH (p:Person)-[:REPORTS_TO*1..]->(b:Person {name: $boss})
   RETURN p.name AS report, p.title AS title ORDER BY report;'

# Who works on the Graph DB rewrite, and at what allocation?
kazoo --db ./examples/office/office.kuzu query --param project='Graph DB rewrite' \
  'MATCH (p:Person)-[w:WORKS_ON]->(proj:Project {name: $project})
   RETURN p.name AS person, w.role AS role, w.allocation_pct AS pct
   ORDER BY pct DESC;'

# Cross-team collaboration: pairs of people on the same project from different teams
kazoo --db ./examples/office/office.kuzu query \
  'MATCH (a:Person)-[:MEMBER_OF]->(ta:Team),
         (b:Person)-[:MEMBER_OF]->(tb:Team),
         (a)-[:WORKS_ON]->(p:Project)<-[:WORKS_ON]-(b)
   WHERE a.id < b.id AND ta.name <> tb.name
   RETURN p.name AS project, a.name AS person_a, ta.name AS team_a,
          b.name AS person_b, tb.name AS team_b
   ORDER BY project;'

# Dump the roster as CSV (write the Cypher you want, pipe through `query -f csv`)
kazoo --db ./examples/office/office.kuzu query \
  'MATCH (p:Person) RETURN p.id AS id, p.name AS name, p.title AS title;' \
  -f csv > roster.csv
```

---

## Social graph

**Schema:** `User`, `Post` nodes; `FOLLOWS`, `POSTED`, `LIKES` rels.

```bash
# Posts by people Ada (@ada) follows, newest first
kazoo --db ./examples/social/social.kuzu query \
  'MATCH (me:User {handle: "@ada"})-[:FOLLOWS]->(f:User)-[:POSTED]->(p:Post)
   RETURN f.handle AS author, p.title AS title, p.posted_at AS posted_at
   ORDER BY posted_at DESC;'

# Mutual follows
kazoo --db ./examples/social/social.kuzu query \
  'MATCH (a:User)-[:FOLLOWS]->(b:User)-[:FOLLOWS]->(a)
   WHERE a.id < b.id
   RETURN a.handle AS a, b.handle AS b ORDER BY a.handle;'

# Friend-of-friend suggestions for @grace (people she doesn't already follow)
kazoo --db ./examples/social/social.kuzu query \
  'MATCH (me:User {handle: "@grace"})-[:FOLLOWS]->(f:User)-[:FOLLOWS]->(suggested:User)
   WHERE NOT (me)-[:FOLLOWS]->(suggested) AND me <> suggested
   RETURN DISTINCT suggested.handle AS handle, suggested.name AS name;'

# Most-liked posts
kazoo --db ./examples/social/social.kuzu query \
  'MATCH (p:Post)<-[l:LIKES]-()
   RETURN p.title AS title, count(l) AS likes
   ORDER BY likes DESC LIMIT 5;'
```
