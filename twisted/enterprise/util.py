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
        self.childTables = []
        self.dbColumns = []

    def addForeignKey(self, childTableName, childColumns, localColumns, childRowClass):
        self.childTables.append( _TableRelationship(childTableName, localColumns, childColumns, childRowClass) )

class _TableRelationship:
    """(Internal)
    
    A foreign key relationship between two tables.
    """
    def __init__(self, childTableName,
                 parentColumns,
                 childColumns,
                 childRowClass):
        self.childTableName = childTableName            
        self.parentColumns = parentColumns
        self.childColumns = childColumns
        self.childRowClass = childRowClass
