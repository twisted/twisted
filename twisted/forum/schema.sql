DROP TABLE forum_permissions;
DROP TABLE posts;
DROP TABLE forums;
DROP TABLE forum_perspectives;
DROP SEQUENCE forums_forum_id_seq;
DROP SEQUENCE posts_post_id_seq;

CREATE TABLE forum_perspectives
(
    identity_name     varchar(64)  PRIMARY KEY,
    user_name         varchar(64)  UNIQUE,
    signature         varchar(64)  NOT NULL
);

CREATE TABLE forums
(
    forum_id       serial        PRIMARY KEY,
    name           varchar(64)   NOT NULL,
    description    text          NOT NULL,
    default_access integer       NOT NULL
);

CREATE TABLE posts
(
    post_id        serial        PRIMARY KEY,
    forum_id       int           CONSTRAINT forum_id_posts
                                 REFERENCES forums (forum_id),
    parent_id      int           NOT NULL,
    thread_id      int           NOT NULL,
    previous_id    int           NOT NULL,
    subject        varchar(64)   NOT NULL,
    user_name      varchar(64)   CONSTRAINT user_name_posts
                                 REFERENCES forum_perspectives (user_name),
    posted         timestamp     NOT NULL,
    body           text          NOT NULL
);

CREATE TABLE forum_permissions
(
    user_name         varchar(64) NOT NULL,
    forum_id          integer,
    read_access       integer,
    post_access       integer,
    CONSTRAINT perm_key PRIMARY KEY (user_name, forum_id)
);
