import random

from twisted.internet import reactor

from twisted.enterprise import adbapi, row, reflector, sqlreflector

from row_util import *

""" This example show using twisted.enterpise.row to load objects from
a database and manipulate them.
"""

manager = None

def gotRooms(rooms):
    print "got Rooms.", rooms
    if not rooms:
        print "no rooms found!"
        reactor.stop()

    for room in rooms:
        print "room  ", room
        for child in room.furniture:
            print "furn     ", child            
            if hasattr(child, "childRows"):
                for inner in child.childRows:
                    print "inner        ", inner

    room.moveTo( int(random.random() * 100) , int(random.random() * 100) )
    manager.updateRow(room).addCallback(onUpdate)

def gotFurniture(furniture):
    for f in furniture:
        print f
    reactor.stop()
        
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
    return manager.loadObjectsFrom("furniture", whereClause=[("furnId",reflector.EQUAL,53)], forceChildren=1 ).addCallback(onSelected)

def onSelected(furn):
    for f in furn:
        print "\ngot Furn:", f
        if hasattr(f, "childRows"):
            for l in f.childRows:
                print "   ", l
    reactor.stop()

def gotRooms2(rooms):
    print "got more rooms", rooms
    reactor.stop()

def tick():
    reactor.callLater(0.5, tick)

newRoom = None


# use this line for postgresql test
dbpool = adbapi.ConnectionPool("pyPgSQL.PgSQL", database="test")

# use this line for SQLite test
#dbpool = adbapi.ConnectionPool("sqlite", db="test")

# use this line for Interbase / Firebird
#dbpool = adbapi.ConnectionPool("kinterbasdb", dsn="localhost:/test.gdb",user="SYSDBA",password="masterkey")

# use this for MySQL
#dbpool = adbapi.ConnectionPool("MySQLdb", db="test", passwd="pass")


def kickOffTests(ignoredResult=0):
    global manager
    manager = sqlreflector.SQLReflector(dbpool, [RoomRow, FurnitureRow, RugRow, LampRow])
    manager.loadObjectsFrom("testrooms", forceChildren=1).addCallback(gotRooms)

kf = KeyFactory(100000, 50000)

# make sure we can be shut down on windows.
reactor.callLater(0.5, tick)
reactor.callLater(0.4, kickOffTests)
reactor.run()
