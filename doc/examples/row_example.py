import random

from twisted.enterprise import adbapi, row
from twisted.internet import app, main


# TODO: turn this into real unit test!!!!


testSchema = """

-- DROP TABLE testrooms;

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

def createSchema():
    return dbpool.runOperation(testSchema).addCallbacks(kickOffTests, kickOffTests)

def gotRooms(rooms):
    print "got Rooms.", dir(rooms[0])

    for room in rooms:
        print "  ROOM:", room
        if room.roomId == 10:
            room.moveTo( int(random.random() * 100) , int(random.random() * 100) )
            manager.updateRow(room).addCallback(onUpdate).arm()

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
    manager.insertRow(newRoom).addCallback(onInsert).arm()

def onInsert(data):
    print "row inserted", newRoom.roomId
    manager.deleteRow(newRoom).addCallback(onDelete).arm()

def onDelete(data):
    print "row deleted."
    newRoom2 = RoomRow()
    newRoom2.assignKeyAttr("roomId", 10)
    manager.selectRow(newRoom2).addCallback(onSelected).arm()


def onSelected(room):
    print "\ngot Room:", room
    main.shutDown()

def tick():
    main.addTimeout(tick, 0.5)



newRoom = None

dbpool = adbapi.ConnectionPool("pyPgSQL.PgSQL")
stubs = [ (RoomRow, "testrooms", [("roomId","int4")]) ]

# Create Twisted application object
application = app.Application("testApp")

def kickOffTests(ignoredResult):
    global manager
    manager = row.DBReflector(dbpool, stubs, runTests)

createSchema().addCallback(kickOffTests).arm()

kf = row.KeyFactory(100000,50000)

# make sure we can be shut down on windows.
main.addTimeout(tick, 0.5)

application.run(save=0)
