DELETE FROM forum_perspectives;
INSERT INTO forum_perspectives VALUES ('testAccount1', 'postingalias', 'come get me');
INSERT INTO forum_perspectives VALUES ('testAccount3', 'poster', 'come get some');

DELETE FROM forums;
INSERT INTO FORUMS (forum_id, name, description, moderator) VALUES 
   (101, 'Twisted Forum discussion', 'Information about the development of the Twisted server framework and associated technologies.', 'poster');
INSERT INTO FORUMS (forum_id, name, description, moderator) VALUES 
   (102, 'Python development discussion', 'Development of the language python and lots of other really boring stuff.', 'poster');

DELETE FROM posts;
INSERT INTO posts (forum_id, parent_id, thread_id, subject, user_name, posted, body) VALUES 
                  (101, 0, 0, 'testing1', 'poster', now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, user_name, posted, body) VALUES 
                  (101, 0, 0, 'another msg goes here but it is long', 'poster', now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, user_name, posted, body) VALUES 
                  (101, 0, 0, 'testing3', 'poster', now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, user_name, posted, body) VALUES 
                  (101, 0, 0, 'testing4', 'poster', now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, user_name, posted, body) VALUES 
                  (101, 0, 0, 'stuff', 'poster', now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, user_name, posted, body) VALUES 
                  (101, 0, 0, 'RE: stuff', 'poster', now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, user_name, posted, body) VALUES 
                  (101, 0, 0, 'other stuff', 'postingalias', now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, user_name, posted, body) VALUES 
                  (101, 0, 0, 'hello!!', 'postingalias', now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, user_name, posted, body) VALUES 
                  (101, 0, 0, 'testing9', 'poster', now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, user_name, posted, body) VALUES 
                  (101, 1, 1, 'testing child msg', 'poster', now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, user_name, posted, body) VALUES 
                  (101, 1, 1, 'child msg 2', 'poster', now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, user_name, posted, body) VALUES 
                  (101, 11, 1, 'alksdhk2', 'postingalias', now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, user_name, posted, body) VALUES 
                  (101, 11, 1, 'here it is!', 'postingalias', now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, user_name, posted, body) VALUES 
                  (101, 12, 1, 'RE: msg 2', 'poster', now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, user_name, posted, body) VALUES 
                  (101, 5, 5, 'out of order', 'postingalias', now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, user_name, posted, body) VALUES 
                  (101, 6, 6, 'another one', 'postingalias', now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, user_name, posted, body) VALUES 
                  (101, 16, 5, 'RE: another one', 'poster', now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, user_name, posted, body) VALUES 
                  (101, 17, 5, 'RE: another one', 'poster', now(), 'is if the body of the message');

INSERT INTO posts (forum_id, parent_id, thread_id, subject, user_name, posted, body) VALUES (101, 18, 5, 'one', 'poster', now(), 'message');
