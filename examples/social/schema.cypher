// Social graph — users, posts, follows/likes.
CREATE NODE TABLE User (id INT64, handle STRING, name STRING, city STRING, joined DATE, PRIMARY KEY (id));
CREATE NODE TABLE Post (id INT64, title STRING, posted_at TIMESTAMP, PRIMARY KEY (id));

CREATE REL TABLE FOLLOWS (FROM User TO User, since DATE);
CREATE REL TABLE POSTED  (FROM User TO Post);
CREATE REL TABLE LIKES   (FROM User TO Post, at TIMESTAMP);
