// People
CREATE (:Person {id: 1,  name: 'Ada Lovelace',     title: 'CTO'});
CREATE (:Person {id: 2,  name: 'Grace Hopper',     title: 'VP Engineering'});
CREATE (:Person {id: 3,  name: 'Alan Turing',      title: 'Principal Engineer'});
CREATE (:Person {id: 4,  name: 'Linus Torvalds',   title: 'Staff Engineer'});
CREATE (:Person {id: 5,  name: 'Margaret Hamilton',title: 'Engineering Manager'});
CREATE (:Person {id: 6,  name: 'Dennis Ritchie',   title: 'Senior Engineer'});
CREATE (:Person {id: 7,  name: 'Barbara Liskov',   title: 'Senior Engineer'});
CREATE (:Person {id: 8,  name: 'Ken Thompson',     title: 'Engineer'});
CREATE (:Person {id: 9,  name: 'Brian Kernighan',  title: 'Engineer'});
CREATE (:Person {id: 10, name: 'Donald Knuth',     title: 'Engineer'});

// Teams
CREATE (:Team {name: 'Platform',     department: 'Engineering'});
CREATE (:Team {name: 'Storage',      department: 'Engineering'});
CREATE (:Team {name: 'Developer Experience', department: 'Engineering'});

// Projects
CREATE (:Project {id: 100, name: 'Graph DB rewrite',     status: 'in_progress'});
CREATE (:Project {id: 101, name: 'Auth migration',       status: 'in_progress'});
CREATE (:Project {id: 102, name: 'Onboarding revamp',    status: 'planning'});
CREATE (:Project {id: 103, name: 'Build cache overhaul', status: 'complete'});

// Reporting lines
MATCH (g:Person {id:2}), (a:Person {id:1}) CREATE (g)-[:REPORTS_TO]->(a);
MATCH (t:Person {id:3}), (g:Person {id:2}) CREATE (t)-[:REPORTS_TO]->(g);
MATCH (l:Person {id:4}), (g:Person {id:2}) CREATE (l)-[:REPORTS_TO]->(g);
MATCH (m:Person {id:5}), (g:Person {id:2}) CREATE (m)-[:REPORTS_TO]->(g);
MATCH (d:Person {id:6}), (m:Person {id:5}) CREATE (d)-[:REPORTS_TO]->(m);
MATCH (b:Person {id:7}), (m:Person {id:5}) CREATE (b)-[:REPORTS_TO]->(m);
MATCH (k:Person {id:8}), (m:Person {id:5}) CREATE (k)-[:REPORTS_TO]->(m);
MATCH (br:Person {id:9}), (m:Person {id:5}) CREATE (br)-[:REPORTS_TO]->(m);
MATCH (kn:Person {id:10}), (m:Person {id:5}) CREATE (kn)-[:REPORTS_TO]->(m);

// Team membership
MATCH (p:Person {id:3}),  (t:Team {name:'Platform'}) CREATE (p)-[:MEMBER_OF]->(t);
MATCH (p:Person {id:4}),  (t:Team {name:'Storage'})  CREATE (p)-[:MEMBER_OF]->(t);
MATCH (p:Person {id:6}),  (t:Team {name:'Storage'})  CREATE (p)-[:MEMBER_OF]->(t);
MATCH (p:Person {id:7}),  (t:Team {name:'Platform'}) CREATE (p)-[:MEMBER_OF]->(t);
MATCH (p:Person {id:8}),  (t:Team {name:'Platform'}) CREATE (p)-[:MEMBER_OF]->(t);
MATCH (p:Person {id:9}),  (t:Team {name:'Developer Experience'}) CREATE (p)-[:MEMBER_OF]->(t);
MATCH (p:Person {id:10}), (t:Team {name:'Developer Experience'}) CREATE (p)-[:MEMBER_OF]->(t);
MATCH (p:Person {id:5}),  (t:Team {name:'Storage'})  CREATE (p)-[:MEMBER_OF]->(t);

// Project assignments
MATCH (p:Person {id:3}),  (pr:Project {id:100}) CREATE (p)-[:WORKS_ON {role: 'tech lead',  allocation_pct: 70}]->(pr);
MATCH (p:Person {id:7}),  (pr:Project {id:100}) CREATE (p)-[:WORKS_ON {role: 'engineer',   allocation_pct: 80}]->(pr);
MATCH (p:Person {id:8}),  (pr:Project {id:100}) CREATE (p)-[:WORKS_ON {role: 'engineer',   allocation_pct: 50}]->(pr);
MATCH (p:Person {id:4}),  (pr:Project {id:101}) CREATE (p)-[:WORKS_ON {role: 'tech lead',  allocation_pct: 60}]->(pr);
MATCH (p:Person {id:6}),  (pr:Project {id:101}) CREATE (p)-[:WORKS_ON {role: 'engineer',   allocation_pct: 100}]->(pr);
MATCH (p:Person {id:9}),  (pr:Project {id:102}) CREATE (p)-[:WORKS_ON {role: 'designer',   allocation_pct: 50}]->(pr);
MATCH (p:Person {id:10}), (pr:Project {id:102}) CREATE (p)-[:WORKS_ON {role: 'pm',         allocation_pct: 30}]->(pr);
MATCH (p:Person {id:5}),  (pr:Project {id:103}) CREATE (p)-[:WORKS_ON {role: 'manager',    allocation_pct: 20}]->(pr);
MATCH (p:Person {id:3}),  (pr:Project {id:101}) CREATE (p)-[:WORKS_ON {role: 'advisor',    allocation_pct: 10}]->(pr);
