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

import string
import adbapi

NOQUOTE = 1
USEQUOTE = 2

dbTypeMap = {
    "bool": NOQUOTE,
    "int2": NOQUOTE,
    "int4": NOQUOTE,
    "int": NOQUOTE,
    "float8": NOQUOTE,
    "char": USEQUOTE,
    "varchar": USEQUOTE,
    "text": USEQUOTE,
    "timestamp": USEQUOTE
    }

class DBError(Exception):
    pass

### Utility functions

def getKeyColumn(rowClass, name):
    for keyColumn, type in rowClass.rowKeyColumns:
        if string.lower(name) == keyColumn:
            return name
    return None

def quote(value, typeCode):
    """Add quotes for text types and no quotes for integer types.
    NOTE: uses Postgresql type codes..
    """
    q = dbTypeMap.get(typeCode, None)
    if q is None:
        raise DBError("Type %s not known" % typeCode)
    if q == NOQUOTE:
        return value
    elif q == USEQUOTE:
        return "'%s'" % adbapi.safe(value)


def makeKW(rowClass, args):
    """Utility method to construct a dictionary for the attributes
    of an object from set of args. This also fixes the case of column names.
    """
    kw = {}
    for i in range(0,len(args)):
        columnName = rowClass.dbColumns[i][0]
        for attr in rowClass.rowColumns:
            if string.lower(attr) == string.lower(columnName):
                kw[attr] = args[i]
                break
    return kw

def defaultFactoryMethod(rowClass, data, kw):
    """Used by loadObjects to create rowObject instances.
    """
    newObject = rowClass()
    newObject.__dict__.update(kw)
    return newObject

### utility classes

class _TableInfo:
    """(internal)

    Info about a table/class and it's relationships. Also serves as a container for
    generated SQL.
    """
    def __init__(self, rc):
        self.rowClass = rc
        self.rowTableName = rc.rowTableName
        self.rowKeyColumns = rc.rowKeyColumns
        
        if hasattr(rc, "rowForeignKeys"):
            self.rowForeignKeys = rc.rowForeignKeys
        else:
            self.rowForeignKeys = []

        if hasattr(rc, "rowFactoryMethod"):
            if rc.rowFactoryMethod:
                self.rowFactoryMethod = rc.rowFactoryMethod
            else:
                self.rowFactoryMethod = [defaultFactoryMethod]
        else:
            self.rowFactoryMethod = [defaultFactoryMethod]

        self.selectSQL = None
        self.updateSQL = None
        self.deleteSQL = None
        self.insertSQL = None
        self.relationships = []
        self.dbColumns = []

    def addForeignKey(self, childTableName, childColumns, localColumns, childRowClass, containerMethod, autoLoad):
        self.relationships.append( _TableRelationship(childTableName, localColumns, childColumns, childRowClass, containerMethod, autoLoad) )

    def getRelationshipFor(self, tableName):
        for relationship in self.relationships:
            if relationship.childTableName == tableName:
                return relationship
        return None
    
class _TableRelationship:
    """(Internal)
    
    A foreign key relationship between two tables.
    """
    def __init__(self, childTableName,
                 parentColumns,
                 childColumns,
                 childRowClass,
                 containerMethod,
                 autoLoad):
        self.childTableName = childTableName            
        self.parentColumns = parentColumns
        self.childColumns = childColumns
        self.childRowClass = childRowClass
        self.containerMethod = containerMethod
        self.autoLoad = autoLoad
