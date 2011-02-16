# -*- test-case-name: twisted.test.test_enterprise -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


import warnings, types

from twisted.python.versions import Version, getVersionString
from twisted.python.deprecate import deprecated
from twisted.enterprise.adbapi import _safe

# Common deprecation decorator used for all deprecations.
_deprecatedVersion = Version("Twisted", 8, 0, 0)
_releasedDeprecation = deprecated(_deprecatedVersion)

warnings.warn(
    "twisted.enterprise.util is deprecated since %s." % (
        getVersionString(_deprecatedVersion),),
    category=DeprecationWarning)

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
getKeyColumn = _releasedDeprecation(getKeyColumn)



def quote(value, typeCode, string_escaper=_safe):
    """Add quotes for text types and no quotes for integer types.
    NOTE: uses Postgresql type codes.
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
        if not isinstance(value, types.StringType) and \
               not isinstance(value, types.UnicodeType):
            value = str(value)
        return "'%s'" % string_escaper(value)
quote = _releasedDeprecation(quote)


def safe(text):
    """
    Make a string safe to include in an SQL statement.
    """
    return _safe(text)

safe = _releasedDeprecation(safe)


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
makeKW = _releasedDeprecation(makeKW)


def defaultFactoryMethod(rowClass, data, kw):
    """Used by loadObjects to create rowObject instances.
    """
    newObject = rowClass()
    newObject.__dict__.update(kw)
    return newObject
defaultFactoryMethod = _releasedDeprecation(defaultFactoryMethod)

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


__all__ = ['NOQUOTE', 'USEQUOTE', 'dbTypeMap', 'DBError', 'getKeyColumn',
           'safe', 'quote']
