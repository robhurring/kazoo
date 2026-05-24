// Office graph — people, projects, teams, reporting lines.
CREATE NODE TABLE Person  (id INT64, name STRING, title STRING, PRIMARY KEY (id));
CREATE NODE TABLE Team    (name STRING, department STRING, PRIMARY KEY (name));
CREATE NODE TABLE Project (id INT64, name STRING, status STRING, PRIMARY KEY (id));

CREATE REL TABLE MEMBER_OF  (FROM Person TO Team);
CREATE REL TABLE REPORTS_TO (FROM Person TO Person);
CREATE REL TABLE WORKS_ON   (FROM Person TO Project, role STRING, allocation_pct INT64);
