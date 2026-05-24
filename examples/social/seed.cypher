// Users
CREATE (:User {id: 1, handle: '@ada',     name: 'Ada Lovelace',     city: 'London',     joined: date('2023-01-04')});
CREATE (:User {id: 2, handle: '@grace',   name: 'Grace Hopper',     city: 'New York',   joined: date('2023-02-12')});
CREATE (:User {id: 3, handle: '@alan',    name: 'Alan Turing',      city: 'Manchester', joined: date('2023-03-09')});
CREATE (:User {id: 4, handle: '@linus',   name: 'Linus Torvalds',   city: 'Portland',   joined: date('2023-04-18')});
CREATE (:User {id: 5, handle: '@margaret',name: 'Margaret Hamilton',city: 'Boston',     joined: date('2023-05-01')});
CREATE (:User {id: 6, handle: '@dennis',  name: 'Dennis Ritchie',   city: 'New York',   joined: date('2023-06-23')});
CREATE (:User {id: 7, handle: '@barbara', name: 'Barbara Liskov',   city: 'Boston',     joined: date('2023-07-08')});

// Posts
CREATE (:Post {id: 1001, title: 'Notes on the analytical engine',     posted_at: timestamp('2024-01-15 09:30:00')});
CREATE (:Post {id: 1002, title: 'Compiling is just translation',      posted_at: timestamp('2024-01-20 12:00:00')});
CREATE (:Post {id: 1003, title: 'On decidability',                    posted_at: timestamp('2024-02-02 18:45:00')});
CREATE (:Post {id: 1004, title: 'Linux turns 33',                     posted_at: timestamp('2024-08-25 10:00:00')});
CREATE (:Post {id: 1005, title: 'Onboard guidance and recovery',      posted_at: timestamp('2024-03-14 14:20:00')});
CREATE (:Post {id: 1006, title: 'Why simplicity matters in kernels',  posted_at: timestamp('2024-04-09 08:00:00')});
CREATE (:Post {id: 1007, title: 'Abstraction and substitution',       posted_at: timestamp('2024-05-30 11:11:00')});

// Follows
MATCH (a:User {id:1}), (b:User {id:2}) CREATE (a)-[:FOLLOWS {since: date('2023-02-20')}]->(b);
MATCH (a:User {id:1}), (b:User {id:3}) CREATE (a)-[:FOLLOWS {since: date('2023-03-15')}]->(b);
MATCH (a:User {id:2}), (b:User {id:1}) CREATE (a)-[:FOLLOWS {since: date('2023-02-21')}]->(b);
MATCH (a:User {id:2}), (b:User {id:5}) CREATE (a)-[:FOLLOWS {since: date('2023-05-04')}]->(b);
MATCH (a:User {id:3}), (b:User {id:1}) CREATE (a)-[:FOLLOWS {since: date('2023-04-01')}]->(b);
MATCH (a:User {id:4}), (b:User {id:6}) CREATE (a)-[:FOLLOWS {since: date('2023-06-25')}]->(b);
MATCH (a:User {id:5}), (b:User {id:2}) CREATE (a)-[:FOLLOWS {since: date('2023-05-10')}]->(b);
MATCH (a:User {id:5}), (b:User {id:7}) CREATE (a)-[:FOLLOWS {since: date('2023-07-12')}]->(b);
MATCH (a:User {id:6}), (b:User {id:4}) CREATE (a)-[:FOLLOWS {since: date('2023-06-30')}]->(b);
MATCH (a:User {id:7}), (b:User {id:5}) CREATE (a)-[:FOLLOWS {since: date('2023-07-13')}]->(b);
MATCH (a:User {id:7}), (b:User {id:1}) CREATE (a)-[:FOLLOWS {since: date('2023-08-01')}]->(b);

// Authorship
MATCH (u:User {id:1}), (p:Post {id:1001}) CREATE (u)-[:POSTED]->(p);
MATCH (u:User {id:2}), (p:Post {id:1002}) CREATE (u)-[:POSTED]->(p);
MATCH (u:User {id:3}), (p:Post {id:1003}) CREATE (u)-[:POSTED]->(p);
MATCH (u:User {id:4}), (p:Post {id:1004}) CREATE (u)-[:POSTED]->(p);
MATCH (u:User {id:5}), (p:Post {id:1005}) CREATE (u)-[:POSTED]->(p);
MATCH (u:User {id:4}), (p:Post {id:1006}) CREATE (u)-[:POSTED]->(p);
MATCH (u:User {id:7}), (p:Post {id:1007}) CREATE (u)-[:POSTED]->(p);

// Likes
MATCH (u:User {id:2}), (p:Post {id:1001}) CREATE (u)-[:LIKES {at: timestamp('2024-01-15 10:05:00')}]->(p);
MATCH (u:User {id:3}), (p:Post {id:1001}) CREATE (u)-[:LIKES {at: timestamp('2024-01-15 11:20:00')}]->(p);
MATCH (u:User {id:1}), (p:Post {id:1002}) CREATE (u)-[:LIKES {at: timestamp('2024-01-20 12:30:00')}]->(p);
MATCH (u:User {id:5}), (p:Post {id:1002}) CREATE (u)-[:LIKES {at: timestamp('2024-01-20 14:00:00')}]->(p);
MATCH (u:User {id:1}), (p:Post {id:1003}) CREATE (u)-[:LIKES {at: timestamp('2024-02-02 19:00:00')}]->(p);
MATCH (u:User {id:5}), (p:Post {id:1004}) CREATE (u)-[:LIKES {at: timestamp('2024-08-25 10:30:00')}]->(p);
MATCH (u:User {id:6}), (p:Post {id:1004}) CREATE (u)-[:LIKES {at: timestamp('2024-08-25 11:00:00')}]->(p);
MATCH (u:User {id:7}), (p:Post {id:1005}) CREATE (u)-[:LIKES {at: timestamp('2024-03-14 15:00:00')}]->(p);
MATCH (u:User {id:2}), (p:Post {id:1007}) CREATE (u)-[:LIKES {at: timestamp('2024-05-30 12:00:00')}]->(p);
