# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import weakref

from twisted.enterprise.util import DBError

class Reflector:
    """Base class for enterprise reflectors. This implements row caching.
    """
    populated = 0

    def __init__(self, rowClasses):
        """
        Initialize me against a database.

        @param rowClasses: a list of row class objects that describe the
            database schema.
        """

        self.rowCache = weakref.WeakValueDictionary() # does not hold references to cached rows.
        self.rowClasses = rowClasses
        self.schema = {}
        self._populate()

    def __getstate__(self):
        d = self.__dict__.copy()
        del d['rowCache']
        return d

    def __setstate__(self, state):
        self.__dict__ = state
        self.rowCache = weakref.WeakValueDictionary()
        self._populate()

    def _populate(self):
        """Implement me to populate schema information for the reflector.
        """
        raise DBError("not implemented")

    def populateSchemaFor(self, tableInfo):
        """This is called once for each registered rowClass to add it
        and its foreign key relationships for that rowClass to the
        schema."""

        self.schema[ tableInfo.rowTableName ] = tableInfo

        # add the foreign key to the foreign table.
        for foreignTableName, childColumns, parentColumns, containerMethod, autoLoad in tableInfo.rowForeignKeys:
            self.schema[foreignTableName].addForeignKey(childColumns,
                                                        parentColumns, tableInfo.rowClass,
                                                        containerMethod, autoLoad)

    def getTableInfo(self, rowObject):
        """Get a TableInfo record about a particular instance.

        This record contains various information about the instance's
        class as registered with this reflector.

        @param rowObject: a L{RowObject} instance of a class previously
            registered with me.
        @raises twisted.enterprise.row.DBError: raised if this class was not
            previously registered.
        """
        try:
            return self.schema[rowObject.rowTableName]
        except KeyError:
            raise DBError("class %s was not registered with %s" % (
                rowObject.__class__, self))

    def buildWhereClause(self, relationship, row):
        """util method used by reflectors. builds a where clause to link a row to another table.
        """
        whereClause = []
        for i in range(0,len(relationship.childColumns)):
            value = getattr(row, relationship.parentColumns[i][0])
            whereClause.append( [relationship.childColumns[i][0], EQUAL, value] )
        return whereClause

    def addToParent(self, parentRow, rows, tableName):
        """util method used by reflectors. adds these rows to the parent row object.
        If a rowClass does not have a containerMethod, then a list attribute "childRows"
        will be used.
        """
        parentInfo = self.getTableInfo(parentRow)
        relationship = parentInfo.getRelationshipFor(tableName)
        if not relationship:
            raise DBError("no relationship from %s to %s" % ( parentRow.rowTableName, tableName) )

        if not relationship.containerMethod:
            if hasattr(parentRow, "childRows"):
                for row in rows:
                    if row not in parentRow.childRows:
                        parentRow.childRows.append(row)
            else:
                parentRow.childRows = rows
            return

        if not hasattr(parentRow, relationship.containerMethod):
            raise DBError("parent row (%s) doesnt have container method <%s>!" % (parentRow, relationship.containerMethod))

        meth = getattr(parentRow, relationship.containerMethod)
        for row in rows:
            meth(row)

    ####### Row Cache ########

    def addToCache(self, rowObject):
        """NOTE: Should this be recursive?! requires better container knowledge..."""
        self.rowCache[ rowObject.getKeyTuple() ] = rowObject

    def findInCache(self, rowClass, kw):
        keys = []
        keys.append(rowClass.rowTableName)
        for keyName, keyType in rowClass.rowKeyColumns:
            keys.append( kw[keyName] )
        keyTuple = tuple(keys)
        if self.rowCache.has_key(keyTuple):
            return self.rowCache[keyTuple]
        return None

    def removeFromCache(self, rowObject):
        """NOTE: should this be recursive!??"""
        key = rowObject.getKeyTuple()
        if self.rowCache.has_key(key):
            del self.rowCache[key]

    ####### Row Operations ########

    def loadObjectsFrom(self, tableName, parent=None, data=None,
                        whereClause=[], loadChildren=1):
        """Implement me to load objects from the database.

        @param whereClause: a list of tuples of (columnName, conditional, value)
            so it can be parsed by all types of reflectors. eg.::
              whereClause = [("name", EQUALS, "fred"), ("age", GREATERTHAN, 18)]
        """
        raise DBError("not implemented")

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

# conditionals
EQUAL       = 0
LESSTHAN    = 1
GREATERTHAN = 2
LIKE        = 3
