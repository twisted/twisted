import random

from twisted.enterprise import adbapi, row
from twisted.internet import main


# TODO: turn this into real unit test!!!!


"""Schema for this test program:

DROP TABLE testrooms;

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


INSERT INTO testrooms VALUES (10, 100, 'testroom1', 'someguy', 10, 10, 20, 20);
INSERT INTO testrooms VALUES (11, 100, 'testroom2', 'someguy', 30, 10, 20, 20);
INSERT INTO testrooms VALUES (12, 100, 'testroom3', 'someguy', 50, 10, 20, 20);
INSERT INTO testrooms VALUES (13, 100, 'testroom4', 'someguy', 10, 30, 20, 20);
INSERT INTO testrooms VALUES (14, 100, 'testroom5', 'someguy', 10, 50, 20, 20);

"""

class RoomRow(row.RowObject):

    rowColumns = [
        "roomId",
        "town_id",
        "name",
        "owner",
        "posx",
        "posy",
        "width",
        "height"
        ]

    def moveTo(self, x, y):
        self.posx = x
        self.posy = y
        
    def __repr__(self):
        return "<Room #%d: %s (%s) (%d,%d)>" % (self.roomId, self.name, self.owner, self.posx, self.posy)


def runTests(stuff):
    global manager
    manager.loadObjectsFrom("testrooms", [("roomId", "int4")], None, RoomRow).addCallback(gotRooms).arm()

def gotRooms(rooms):
    print "got Rooms.", dir(rooms[0])
    
    for room in rooms:
        print "  ROOM:", room
        if room.roomId == 10:
            room.moveTo( int(random.random() * 100) , int(random.random() * 100) )
            room.updateRow().addCallback(onUpdate).arm()

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
    newRoom.insertRow().addCallback(onInsert).arm()

def onInsert(data):
    print "row inserted", newRoom.roomId
    newRoom.deleteRow().addCallback(onDelete).arm()    

def onDelete(data):
    print "row deleted."
    newRoom2 = RoomRow()
    newRoom2.assignKeyAttr("roomId", 10)
    newRoom2.selectRow().addCallback(onSelected).arm()
    

def onSelected(room):
    print "\ngot Room:", room
    main.shutDown()


newRoom = None

dbpool = adbapi.ConnectionPool("pyPgSQL.PgSQL", "localhost:5432", database="sean")
manager = adbapi.Augmentation(dbpool)

# Create Twisted application object
application = main.Application("testApp")

stubs = [ (RoomRow, "testrooms", [("roomId","int4")]) ]
reflector = row.DBReflector(manager, stubs)
reflector.populate().addCallback(runTests).arm()

kf = row.KeyFactory(100000,50000)

application.run()
