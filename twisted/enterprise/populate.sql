DELETE FROM twisted_services;
DELETE FROM twisted_identities;
DELETE FROM twisted_perspectives;


INSERT INTO twisted_services VALUES ('twisted.words');
INSERT INTO twisted_services VALUES ('twisted.web');
INSERT INTO twisted_services VALUES ('twisted.metrics');
INSERT INTO twisted_services VALUES ('twisted.dbauth');
INSERT INTO twisted_services VALUES ('twisted.forum');

INSERT INTO twisted_identities VALUES ('testAccount1', 'Gh3JHJBzJcaScd3wyUS8cg=='); -- password is "pass"
INSERT INTO twisted_identities VALUES ('testAccount2', 'Gh3JHJBzJcaScd3wyUS8cg=='); -- password is "pass"
INSERT INTO twisted_identities VALUES ('testAccount3', 'Gh3JHJBzJcaScd3wyUS8cg=='); -- password is "pass"
INSERT INTO twisted_identities VALUES ('testAccount4', 'Gh3JHJBzJcaScd3wyUS8cg=='); -- password is "pass"
INSERT INTO twisted_identities VALUES ('testAccount5', 'Gh3JHJBzJcaScd3wyUS8cg=='); -- password is "pass"
INSERT INTO twisted_identities VALUES ('localMachine', 'Gh3JHJBzJcaScd3wyUS8cg=='); -- password is "pass"
INSERT INTO twisted_identities VALUES ('remoteMachine','Gh3JHJBzJcaScd3wyUS8cg=='); -- password is "pass"
INSERT INTO twisted_identities VALUES ('admin',        'Gh3JHJBzJcaScd3wyUS8cg=='); -- password is "pass"

INSERT INTO twisted_perspectives VALUES ('testAccount1', 'testUser1', 'twisted.words', NULL);
INSERT INTO twisted_perspectives VALUES ('testAccount1', 'another1', 'twisted.words', NULL);
INSERT INTO twisted_perspectives VALUES ('testAccount1', 'another2', 'twisted.words', NULL);
INSERT INTO twisted_perspectives VALUES ('testAccount1', 'chatalias', 'twisted.words', NULL);
INSERT INTO twisted_perspectives VALUES ('testAccount1', 'someguy', 'twisted.web', NULL);
INSERT INTO twisted_perspectives VALUES ('testAccount1', 'postingalias', 'twisted.forum', NULL);
INSERT INTO twisted_perspectives VALUES ('testAccount2', 'testUser2', 'twisted.words', NULL);
INSERT INTO twisted_perspectives VALUES ('testAccount3', 'testUser3', 'twisted.words', NULL);
INSERT INTO twisted_perspectives VALUES ('testAccount3', 'poster', 'twisted.forum', NULL);
INSERT INTO twisted_perspectives VALUES ('testAccount4', 'testUser4', 'twisted.words', NULL);
INSERT INTO twisted_perspectives VALUES ('testAccount5', 'testUser5', 'twisted.words', NULL);
INSERT INTO twisted_perspectives VALUES ('admin',        'admin',     'twisted.dbauth', NULL);
INSERT INTO twisted_perspectives VALUES ('localMachine', 'localMachine', 'twisted.metrics', NULL);
INSERT INTO twisted_perspectives VALUES ('remoteMachine', 'remoteMachine', 'twisted.metrics', NULL);

