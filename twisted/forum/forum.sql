DROP TABLE forums;
DROP SEQUENCE forums_forum_id_seq;
CREATE TABLE forums
(
  forum_id       serial        PRIMARY KEY,
  name           varchar(64)   NOT NULL,
  description    varchar(256)  NOT NULL,
  moderator      varchar(64)
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
  user_name    varchar(64)   NOT NULL,
  posted         timestamp     NOT NULL,
  body           varchar(1024) NOT NULL
);

DROP TABLE forum_perpectives;
CREATE TABLE forum_perspectives
(
  identity_name     varchar(64)  PRIMARY KEY,
  user_name         varchar(64)  NOT NULL,
  signature         varchar(64)  NOT NULL
);
