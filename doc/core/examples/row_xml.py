import random

from twisted.internet import reactor

from twisted.enterprise import adbapi, row, sqlreflector, xmlreflector, reflector

from row_util import *

""" Load objects from postgres DB
    Writes the objects out to XML DB
    Loads the objects from the XML DB
"""

class DataException(Exception): pass

xmanager = None
manager = None

def runTests(ignore=0):
    global manager
    print "running tests."
    manager.loadObjectsFrom("testrooms").addCallbacks(gotDBRooms, fail)

def fail(failure):
    print "FAILURE"
    print failure.getErrorMessage()
    reactor.stop()

def dumpRooms(rooms):
    if not rooms:
        raise DataException, "no rooms found!"

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
    for obj in manager.rowCache.values():
        xmanager.insertRow(obj)

    d = xmanager.loadObjectsFrom("testrooms", data=None,
                                 whereClause=[("roomId",reflector.EQUAL, 12)])
    d.addCallback(gotXMLRooms)
    d.addErrback(fail)

def gotXMLRooms(rooms):
    print "------------ got rooms from XML ------------"    
    dumpRooms(rooms)
    d = xmanager.loadObjectsFrom("testrooms", data=None,
                                 whereClause=[("roomId",reflector.EQUAL, 12)])
    d.addCallback(gotXMLRooms2)
    d.addErrback(fail)

def gotXMLRooms2(rooms):
    print "------------ got rooms from XML again! ------------"        
    reactor.stop()
    
def tick():
    reactor.callLater(0.5, tick)

dbpool = adbapi.ConnectionPool("pyPgSQL.PgSQL", database="test")
#dbpool = adbapi.ConnectionPool("psycopg", "dbname=test")

def kickOffTests(ignoredResult=0):
    global manager, xmanager
    xmanager = xmlreflector.XMLReflector("myXMLdb", [RoomRow, FurnitureRow, RugRow, LampRow] )    
    manager = sqlreflector.SQLReflector(dbpool, [RoomRow, FurnitureRow, RugRow, LampRow])
    runTests()

# make sure we can be shut down on windows.
reactor.callLater(0.5, tick)
reactor.callLater(0.4, kickOffTests)
reactor.run()
