
-- Schema for twisted bugs database.

DROP TABLE bugs_items;      
DROP TABLE bugs_admins;     
DROP TABLE bugs_comments;
DROP TABLE bugs_status;
DROP TABLE bugs_types;
CREATE TABLE bugs_status (
        name  varchar(16)     UNIQUE
);
INSERT INTO bugs_status VALUES ('open');
INSERT INTO bugs_status VALUES ('closed');
INSERT INTO bugs_status VALUES ('rejected');

CREATE TABLE bugs_types (
    name  varchar(16)     UNIQUE
);
    
INSERT INTO bugs_types VALUES ('wishlist');
INSERT INTO bugs_types VALUES ('minor');
INSERT INTO bugs_types VALUES ('normal');
INSERT INTO bugs_types VALUES ('critical');

CREATE TABLE bugs_admins (
    identity_name     varchar(64)  PRIMARY KEY,
    user_name         varchar(64)  UNIQUE,
    email             varchar(128)
    );
    
CREATE TABLE bugs_items (
    bug_id          serial          PRIMARY KEY,
    submittor_name  varchar(64),
    submittor_email varchar(128),
    assigned        varchar(64)     CONSTRAINT assigned_users
                            REFERENCES bugs_admins (user_name),
    date_submitted  timestamp,
    date_modified   timestamp,
    version     varchar(16),
    os              varchar(32),
    security        boolean,
        type            varchar(16)     CONSTRAINT bug_item_type
                                        REFERENCES bugs_types (name),
    status          varchar(16)     CONSTRAINT bug_item_status
                                        REFERENCES bugs_status (name),
    summary         varchar(100),
    description     text
    );
    
CREATE TABLE bugs_comments (
    post_id      serial  PRIMARY KEY,
    bug_id       int     CONSTRAINT comment_bug_ids
                         REFERENCES bugs_items (bug_id),
    submittor_name  varchar(64),
    submittor_email varchar(128),
    date     timestamp,
    comment      text
);

