import random

from twisted.enterprise import adbapi, row
from twisted.internet import main


# TODO: turn this into real unit test!!!!


"""Schema for this test program:

DROP TABLE rooms;

CREATE TABLE rooms
(
  room_id  int,
  town_id  int,
  name     varchar(64),
  owner    varchar(64),
  posx     int,
  posy     int,
  width    int,
  height   int
);


INSERT INTO rooms VALUES (10, 100, 'testroom1', 'someguy', 10, 10, 20, 20);
INSERT INTO rooms VALUES (11, 100, 'testroom2', 'someguy', 30, 10, 20, 20);
INSERT INTO rooms VALUES (12, 100, 'testroom3', 'someguy', 50, 10, 20, 20);
INSERT INTO rooms VALUES (13, 100, 'testroom4', 'someguy', 10, 30, 20, 20);
INSERT INTO rooms VALUES (14, 100, 'testroom5', 'someguy', 10, 50, 20, 20);

"""

class RoomRow(row.RowObject):

    def moveTo(self, x, y):
        self.posx = x
        self.posy = y
        
    def __repr__(self):
        return "<Room #%d: %s (%s) (%d,%d)>" % (self.room_id, self.name, self.owner, self.posx, self.posy)

def gotRooms(rooms):
    print "got Rooms.", dir(rooms[0])
    
    for room in rooms:
        print "  ROOM:", room
        if room.room_id == 10:
            room.moveTo( int(random.random() * 100) , int(random.random() * 100) )
            room.updateRow()

    room.deleteRow()

    # create a new room
    newRoom = RoomRow( room_id=int(random.random() * 1000))
    newRoom.town_id = 20
    newRoom.name = 'newRoom1'
    newRoom.owner = 'fred'
    newRoom.posx = 100
    newRoom.posy = 100
    newRoom.width = 15
    newRoom.height = 20
    
    # insert row into database
    newRoom.insertRow()

def selected(room):
    print "\ngot Room:", room
    main.shutDown()

def test(stuff):
    global newRoom
    print "stuff:",stuff
    manager.loadObjectsFrom("rooms", [("room_id", "int4")], RoomRow).addCallback(gotRooms).arm()
    qRoom = RoomRow( room_id=11)
    qRoom.selectRow().addCallback(selected).arm()
    
dbpool = adbapi.ConnectionPool("pyPgSQL.PgSQL", "crue:5432", database="sean-test")
manager = adbapi.Augmentation(dbpool)
newRoom = None

# Create Twisted application object
application = main.Application("testApp")

row.populateRowClass(manager, RoomRow, "rooms", [("room_id", "int4")]).addCallback(test).arm()

application.run()


    
