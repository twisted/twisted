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

import types
import adbapi

NOQUOTE = 1
USEQUOTE = 2

dbTypeMap = {
    "bigint": NOQUOTE,
    "bool": USEQUOTE,
    "boolean": USEQUOTE,
    "bytea": USEQUOTE,
    "date": USEQUOTE,
    "int2": NOQUOTE,
    "int4": NOQUOTE,
    "int8": NOQUOTE,
    "int": NOQUOTE,
    "integer": NOQUOTE,
    "float4": NOQUOTE,
    "float8": NOQUOTE,
    "numeric": NOQUOTE,
    "real": NOQUOTE,
    "smallint": NOQUOTE,
    "char": USEQUOTE,
    "text": USEQUOTE,
    "time": USEQUOTE,
    "timestamp": USEQUOTE,
    "varchar": USEQUOTE
    }

class DBError(Exception):
    pass

### Utility functions

def getKeyColumn(rowClass, name):
    lcname = name.lower()
    for keyColumn, type in rowClass.rowKeyColumns:
        if lcname == keyColumn.lower():
            return name
    return None

def quote(value, typeCode, string_escaper=adbapi.safe):
    """Add quotes for text types and no quotes for integer types.
    NOTE: uses Postgresql type codes..
    """
    q = dbTypeMap.get(typeCode, None)
    if q is None:
        raise DBError("Type %s not known" % typeCode)
    if value is None:
        return 'null'
    if q == NOQUOTE:
        return str(value)
    elif q == USEQUOTE:
        if typeCode.startswith('bool'):
            if value:
                value = '1'
            else:
                value = '0'
        if typeCode == "bytea":
            l = ["'"]
            for c in value:
                i = ord(c)
                if i == 0:
                    l.append("\\\\000")
                elif i == 92:
                    l.append(c * 4)
                elif 32 <= i <= 126:
                    l.append(c)
                else:
                    l.append("\\%03o" % i)
            l.append("'")
            return "".join(l)
        if not isinstance(value, types.StringType):
            value = str(value)
        return "'%s'" % string_escaper(value)

def makeKW(rowClass, args):
    """Utility method to construct a dictionary for the attributes
    of an object from set of args. This also fixes the case of column names.
    """
    kw = {}
    for i in range(0,len(args)):
        columnName = rowClass.dbColumns[i][0].lower()
        for attr in rowClass.rowColumns:
            if attr.lower() == columnName:
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
        self.rowColumns = rc.rowColumns

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

        self.updateSQL = None
        self.deleteSQL = None
        self.insertSQL = None
        self.relationships = []
        self.dbColumns = []

    def addForeignKey(self, childColumns, parentColumns, childRowClass, containerMethod, autoLoad):
        """This information is attached to the "parent" table
                childColumns - columns of the "child" table
                parentColumns - columns of the "parent" table, the one being joined to... the "foreign" table
        """
        self.relationships.append( _TableRelationship(childColumns, parentColumns,
                                                      childRowClass, containerMethod, autoLoad) )

    def getRelationshipFor(self, tableName):
        for relationship in self.relationships:
            if relationship.childRowClass.rowTableName == tableName:
                return relationship
        return None

class _TableRelationship:
    """(Internal)

    A foreign key relationship between two tables.
    """
    def __init__(self,
                 childColumns,
                 parentColumns,
                 childRowClass,
                 containerMethod,
                 autoLoad):
        self.childColumns = childColumns
        self.parentColumns = parentColumns
        self.childRowClass = childRowClass
        self.containerMethod = containerMethod
        self.autoLoad = autoLoad
