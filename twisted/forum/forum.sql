DROP TABLE forums;
DROP SEQUENCE forums_forum_id_seq;
CREATE TABLE forums
(
  forum_id       serial        PRIMARY KEY,
  name           varchar(64)   NOT NULL
);

DROP TABLE posts;
DROP SEQUENCE posts_post_id_seq;
CREATE TABLE posts
(
  post_id        serial        PRIMARY KEY,
  forum_id       int           NOT NULL,
  parent_id      int           NOT NULL,
  thread_id      int           NOT NULL,
  subject        varchar(64)   NOT NULL,
  poster_id      int           NOT NULL,
  posted         timestamp     NOT NULL,
  body           varchar(1024) NOT NULL
);

DROP TABLE users;
CREATE TABLE users
(
  user_id      int             PRIMARY KEY,
  name         varchar(64)     NOT NULL,
  sig          varchar(64)     NOT NULL
);
