DROP TABLE posts;
DROP SEQUENCE posts_post_id_seq;
CREATE TABLE posts
(
  post_id        serial PRIMARY KEY,
  parent_id      int,
  subject        varchar(32),
  poster_id      int,
  posted         timestamp,
  body           varchar(1024)
);

DROP TABLE users;
CREATE TABLE users
(
  user_id      int PRIMARY KEY,
  name         varchar(32),
  sig          varchar(64)
);

  
