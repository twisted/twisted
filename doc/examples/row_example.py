import random

from twisted.internet import reactor
from twisted.internet import main
from twisted.internet.app import Application

from twisted.enterprise import adbapi, row, reflector, sqlreflector

# TODO: turn this into real unit test!!!!

""" This example show using twisted.enterpise.row to load objects from
a database and manipulate them.
"""

testSchema = """

 DROP TABLE testrooms;
 DROP TABLE furniture;
 DROP TABLE rugs;
 DROP TABLE lamps;

CREATE TABLE testrooms
(
  roomId  int,
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
  furnId int,
  roomId int,
  name   varchar(64),
  posx   int,
  posy   int
);

CREATE TABLE rugs
(
  rugId int,
  roomId int,
  name varchar(64)
);

CREATE TABLE lamps
(
  lampId int,
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
"""

manager = None
manager = None

##################################################
########## Definitions of Row Classes ############
##################################################

def myRowFactory(rowClass, data, kw):
    newRow = rowClass()
    newRow.__dict__.update(kw)
    return newRow

class RoomRow(row.RowObject):
    rowColumns       = ["roomId", "town_id", "name", "owner", "posx", "posy", "width", "height" ]
    rowKeyColumns    = [("roomId","int4")]
    rowTableName     = "testrooms"
    rowFactoryMethod = [myRowFactory]
    
    def moveTo(self, x, y):
        self.posx = x
        self.posy = y
        
    def __repr__(self):
        return "<Room #%d: %s (%s) (%d,%d)>" % (self.roomId, self.name, self.owner, self.posx, self.posy)

class FurnitureRow(row.RowObject):
    rowColumns      = ["furnId", "roomId", "name", "posx", "posy"]
    rowKeyColumns   = [("furnId","int4")]
    rowTableName    = "furniture"
    rowForeignKeys  = [("testrooms", [("roomId","int4")], [("roomId","int4")]) ]

    def __repr__(self):
        return "Furniture #%d: room #%d (%s) (%d,%d)" % (self.furnId, self.roomId, self.name, self.posx, self.posy)

class RugRow(row.RowObject):
    rowColumns       = ["rugId", "roomId", "name"]
    rowKeyColumns    = [("rugId","int4")]
    rowTableName     = "rugs"
    rowFactoryMethod = [myRowFactory]
    rowForeignKeys   = [( "testrooms", [("roomId","int4")],[("roomId","int4")]) ]
    
    def __repr__(self):
        return "Rug %#d: room #%d, (%s)" % (self.rugId, self.roomId, self.name)

class LampRow(row.RowObject):
    rowColumns      = ["lampId", "furnId", "furnName", "lampName"]
    rowKeyColumns   = [("lampId","int4")]
    rowTableName    = "lamps"
    rowForeignKeys  = [("furniture", [("furnId","int4"),("furnName", "varchar")],
                      [("furnId","int4"),("name", "varchar")]) ]
    
    def __repr__(self):
        return "Lamp #%d" % self.lampId

##################################################
########## Code to run the tests      ############
##################################################

def runTests(ignore=0):
    global manager, manager
    print "running tests."
    manager.loadObjectsFrom("testrooms").addCallback(gotRooms)

def createSchema():
    return dbpool.runOperation(testSchema).addCallbacks(kickOffTests)

def gotRooms(rooms):
    print "got Rooms.", rooms
    if not rooms:
        print "no rooms found!"
        main.shutDown()

    for room in rooms:
        print "  ", room
        if hasattr(room,"container"):
            for child in room.container:
                print "     ", child
                if hasattr(child, "container"):
                    for inner in child.container:
                        print "        ", inner

    room.moveTo( int(random.random() * 100) , int(random.random() * 100) )
    manager.updateRow(room).addCallback(onUpdate)



def gotFurniture(furniture):
    for f in furniture:
        print f
        
    main.shutDown()
        
def onUpdate(data):
    print "updated row."
    # create a new room
    global newRoom
    newRoom = RoomRow()
    newRoom.assignKeyAttr("roomId", kf.getNextKey())
    newRoom.town_id = 20
    newRoom.name = 'newRoom1'
    newRoom.owner = 'fred'
    newRoom.posx = 100
    newRoom.posy = 100
    newRoom.width = 15
    newRoom.height = 20
    
    #insert row into database
    manager.insertRow(newRoom).addCallback(onInsert)

def onInsert(data):
    global newRoom
    print "row inserted"
    print newRoom.roomId
    manager.deleteRow(newRoom).addCallback(onDelete)

def onDelete(data):
    print "row deleted."
    return manager.loadObjectsFrom("testrooms", whereClause=[("roomId",reflector.EQUAL,10)] ).addCallback(onSelected)

def onSelected(rooms):
    print "\ngot Room:", rooms
    main.shutDown()    

def gotRooms2(rooms):
    print "got more rooms", rooms
    main.shutDown()

def tick():
    main.addTimeout(tick, 0.5)

newRoom = None

dbpool = adbapi.ConnectionPool("pyPgSQL.PgSQL", database="sean", host="localhost", port=5432)

# Create Twisted application object
application = Application("testApp")

def kickOffTests(ignoredResult=0):
    global manager, manager
    manager = sqlreflector.SQLReflector(dbpool, [RoomRow, FurnitureRow, RugRow, LampRow], runTests)


#createSchema()

kf = row.KeyFactory(100000,50000)

# make sure we can be shut down on windows.
main.addTimeout(tick, 0.5)
main.addTimeout(kickOffTests, 0.4)
reactor.run()
