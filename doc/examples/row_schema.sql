DROP TABLE testrooms;
DROP TABLE furniture;
DROP TABLE rugs;
DROP TABLE lamps;

CREATE TABLE testrooms
(
  roomId  int  PRIMARY KEY,
  town_id  int,
  name     varchar(64),
  owner    varchar(64),
  posx     int,
  posy     int,
  width    int,
  height   int
);

CREATE TABLE furniture
(
  furnId int PRIMARY KEY,
  roomId int,
  name   varchar(64),
  posx   int,
  posy   int
);

CREATE TABLE rugs
(
  rugId int PRIMARY KEY,
  roomId int,
  name varchar(64)
);

CREATE TABLE lamps
(
  lampId int PRIMARY KEY,
  furnId int,
  furnName varchar(64),
  lampName varchar(64)
);    

  
INSERT INTO testrooms VALUES (10, 100, 'testroom1', 'someguy', 10, 10, 20, 20);
INSERT INTO testrooms VALUES (11, 100, 'testroom2', 'someguy', 30, 10, 20, 20);
INSERT INTO testrooms VALUES (12, 100, 'testroom3', 'someguy', 50, 10, 20, 20);

INSERT INTO furniture  VALUES (50, 10, 'chair1', 10, 10);
INSERT INTO furniture  VALUES (51, 10, 'chair2', 14, 10);
INSERT INTO furniture  VALUES (52, 12, 'chair3', 14, 10);
INSERT INTO furniture  VALUES (53, 12, 'chair4', 10, 12);
INSERT INTO furniture  VALUES (54, 12, 'chair5', 18, 13);
INSERT INTO furniture  VALUES (55, 12, 'couch', 22,  3);

INSERT INTO rugs VALUES (81, 10, 'a big rug');
INSERT INTO rugs VALUES (82, 10, 'a blue rug');
INSERT INTO rugs VALUES (83, 11, 'a red rug');
INSERT INTO rugs VALUES (84, 11, 'a green rug');
INSERT INTO rugs VALUES (85, 12, 'a dirty rug');

INSERT INTO lamps VALUES (21, 50, 'chair1', 'a big lamp1');
INSERT INTO lamps VALUES (22, 50, 'chair1', 'a big lamp2');
INSERT INTO lamps VALUES (23, 53, 'chair4', 'a big lamp3');
INSERT INTO lamps VALUES (24, 53, 'chair4', 'a big lamp4');
INSERT INTO lamps VALUES (25, 53, 'chair4', 'a big lamp5');
INSERT INTO lamps VALUES (26, 54, 'couch',  'a big lamp6');
