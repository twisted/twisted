DELETE FROM users;
INSERT INTO users VALUES (1, 'someguy', 'come get me');
INSERT INTO users VALUES (2, 'duke', 'come get some');

DELETE FROM forums;
INSERT INTO FORUMS (forum_id, name) VALUES (101, 'Twisted Forum discussion');
INSERT INTO FORUMS (forum_id, name) VALUES (102, 'Python development discussion');

DELETE FROM posts;
INSERT INTO posts (forum_id, parent_id, thread_id, subject, poster_id, posted, body) VALUES 
                  (101, 0, 0, 'testing1', 1, now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, poster_id, posted, body) VALUES 
                  (101, 0, 0, 'another msg goes here but it is long', 2, now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, poster_id, posted, body) VALUES 
                  (101, 0, 0, 'testing3', 1, now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, poster_id, posted, body) VALUES 
                  (101, 0, 0, 'testing4', 1, now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, poster_id, posted, body) VALUES 
                  (101, 0, 0, 'stuff', 1, now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, poster_id, posted, body) VALUES 
                  (101, 0, 0, 'RE: stuff', 2, now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, poster_id, posted, body) VALUES 
                  (101, 0, 0, 'other stuff', 2, now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, poster_id, posted, body) VALUES 
                  (101, 0, 0, 'hello!!', 1, now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, poster_id, posted, body) VALUES 
                  (101, 0, 0, 'testing9', 1, now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, poster_id, posted, body) VALUES 
                  (101, 1, 1, 'testing child msg', 2, now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, poster_id, posted, body) VALUES 
                  (101, 1, 1, 'child msg 2', 1, now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, poster_id, posted, body) VALUES 
                  (101, 11, 1, 'alksdhk2', 1, now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, poster_id, posted, body) VALUES 
                  (101, 11, 1, 'here it is!', 2, now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, poster_id, posted, body) VALUES 
                  (101, 12, 1, 'RE: msg 2', 1, now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, poster_id, posted, body) VALUES 
                  (101, 5, 5, 'out of order', 2, now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, poster_id, posted, body) VALUES 
                  (101, 6, 6, 'another one', 1, now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, poster_id, posted, body) VALUES 
                  (101, 16, 5, 'RE: another one', 1, now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, poster_id, posted, body) VALUES 
                  (101, 17, 5, 'RE: another one', 1, now(), 'This if the body of the message');
INSERT INTO posts (forum_id, parent_id, thread_id, subject, poster_id, posted, body) VALUES 
                  (101, 18, 5, 'RE: another one', 1, now(), 'This if the body of the message');
