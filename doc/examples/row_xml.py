import random

from twisted.internet import reactor
from twisted.internet import main
from twisted.internet.app import Application

from twisted.enterprise import adbapi, row, sqlreflector, xmlreflector, reflector

from row_util import *

""" Load objects from postgres DB
    Writes the objects out to XML DB
    Loads the objects from the XML DB
"""

xmanager = None
manager = None

def runTests(ignore=0):
    global manager
    print "running tests."
    manager.loadObjectsFrom("testrooms").addCallback(gotDBRooms)

def dumpRooms(rooms):
    if not rooms:
        print "no rooms found!"
        main.shutDown()

    for room in rooms:
        print "  ", room
        for child in room.furniture:
            print "     ", child            
            if hasattr(child, "childRows"):
                for inner in child.childRows:
                    print "        ", inner
    
def gotDBRooms(rooms):
    print "------------ got rooms from database ------------"
    dumpRooms(rooms)
    for obj in xmanager.rowCache.values():
        xmanager.insertRow(obj)

    xmanager.loadObjectsFrom("testrooms", data=None, whereClause=[("roomId",reflector.EQUAL, 12)]).addCallback(gotXMLRooms)

def gotXMLRooms(rooms):
    print "------------ got rooms from XML ------------"    
    dumpRooms(rooms)
    xmanager.loadObjectsFrom("testrooms", data=None, whereClause=[("roomId",reflector.EQUAL, 12)]).addCallback(gotXMLRooms2)

def gotXMLRooms2(rooms):
    print "------------ got rooms from XML again! ------------"        
    main.shutDown()
    
def tick():
    main.addTimeout(tick, 0.5)

dbpool = adbapi.ConnectionPool("pyPgSQL.PgSQL", database="sean", host="localhost", port=5432)

# Create Twisted application object
application = Application("testApp")

def kickOffTests(ignoredResult=0):
    global manager, xmanager
    xmanager = xmlreflector.XMLReflector("myXMLdb", [RoomRow, FurnitureRow, RugRow, LampRow] )    
    manager = sqlreflector.SQLReflector(dbpool, [RoomRow, FurnitureRow, RugRow, LampRow], runTests)

# make sure we can be shut down on windows.
main.addTimeout(tick, 0.5)
main.addTimeout(kickOffTests, 0.4)
reactor.run()
