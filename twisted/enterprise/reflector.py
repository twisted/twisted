import string
import weakref

from twisted.enterprise import adbapi
from twisted.enterprise.util import DBError, getKeyColumn, quote, _TableInfo, _TableRelationship
from twisted.enterprise.row import RowObject


class Reflector:
    """Base class for enterprise reflectors.
    """
    populated = 0

    def __init__(self, rowClasses, populatedCallback):
        """
        Initialize me against a database.

        Arguments:
          * rowClasses: a list of row class objects that describe the database schema.

          * populatedCallback: method to be called when all database initialization is done
        """

        self.rowCache = weakref.WeakValueDictionary() # doesnt hold references to cached rows.
        self.rowClasses = rowClasses
        self.schema = {}        
        self.populatedCallback = populatedCallback
        self._populate()
        
    def __setstate__(self, state):
        self.__dict__ = state
        self._populate()

    def _populate(self):
        
        # egregiously bad hack, obviously, but we need to avoid calling a
        # cached callback before persistence is really done, and while the
        # mainloop is not running.  I'm not sure what the correct behavior here
        # should be. --glyph
        
        from twisted.internet import reactor
        reactor.callLater(0, self._really_populate)

    def _really_populate(self):
        """Implement me to populate schema information for the reflector.
        """
        raise DBError("not implemented")
    
    def loadObjectsFrom(self, tableName, data = None, whereClause = "1 = 1", parent = None):
        """Implement me to load objects from the database.
        """
        raise DBError("not implemented")

    def populateSchemaFor(self, tableInfo):
        self.schema[ tableInfo.rowTableName ] = tableInfo
        
        # add the foreign key to the parent table.
        for foreignTableName, localColumns, foreignColumns in tableInfo.rowForeignKeys:
            self.schema[foreignTableName].addForeignKey(tableInfo.rowTableName, localColumns, foreignColumns, tableInfo.rowClass)

    ####### Row Cache ########
    
    def addToCache(self, rowObject):
        """NOTE: Should this be recursive?! requires better container knowledge..."""
        self.rowCache[ rowObject.getKeyTuple() ] = rowObject
        #print "Adding to Cache <%s> %s" % (keys, rowObject)

    def findInCache(self, rowClass, kw):
        keys = []
        keys.append(rowClass.rowTableName)
        for keyName, keyType in rowClass.rowKeyColumns:
            keys.append( kw[keyName] )
        keyTuple = tuple(keys)
        if self.rowCache.has_key(keyTuple):
            #print "found object in cache:", keyTuple
            return self.rowCache[keyTuple]
        return None

    def removeFromCache(self, rowObject):
        """NOTE: should this be recursive!??"""
        key = rowObject.getKeyTuple()
        if not self.rowCache.has_key(key):
            raise DBError("Row object not in cache: %s", rowObject)
        del self.rowCache[key]

    ####### Row Operations ########
        
    def updateRow(self, rowObject):
        """update this rowObject to the database.
        """
        raise DBError("not implemented")
    
    def insertRow(self, rowObject):
        """insert a new row for this object instance.
        """
        raise DBError("not implemented")

    def deleteRow(self, rowObject):
        """delete the row for this object from the database.
        """
        raise DBError("not implemented")        

    def selectRow(self, rowObject):
        """load this rows current values from the database.
        """
        raise DBError("not implemented")                


