import string
import time

class DBError(Exception):
    pass


class RowObject:
    """I represent a row in a table in a relational database. My class is "populated"
    by a DBReflector object. After I am populated, instances of me
    are able to interact with a particular database table.

    You should use a class derived from this class for each database table.

    enterprise.Augentation.loadObjectsFrom() is used to create sets of instance of objects
    of this class from database tables.

    Once created, the "key column" attributes cannot be changed.
    """

    ### Class Attributes populated by the DBReflector
    
    dbColumns = []     # list of column names and types for the table I came from
    dbKeyColumns = []  # list of key columns to identify instances in the db
    tableName = ""
    selectSQL = ""
    updateSQL = ""
    insertSQL = ""
    deleteSQL = ""
    populated = 0    # set on the class when the class is "populated" with SQL
    dirty = 0        # set on an instance then the instance is out-of-sync with the database

    ### Class Attributes that users must supply

    rowColumns = []  # list of the columns in the table with the correct case.
                     # this will be used to create member variables.

    def assignKeyAttr(self, attrName, value):
        """assign to a key attribute.. this cannot be done through normal means
        to protect changing keys of db objects.
        """
        found = 0
        for keyColumn, type in self.dbKeyColumns:
            if keyColumn == attrName:
                found = 1
        if not found:
            raise DBError("%s is not a key columns." % attrName)
        self.__dict__[attrName] = value

    def findAttribute(self, attrName):
        """find an attribute by caseless name
        """
        for attr in self.__dict__.keys():
            if string.lower(attr) == string.lower(attrName):
                return self.__dict__[attr]
        raise DBError("Unable to find attribute %s" % attrName)
    
    def updateRow(self):
        """update my contents to the database.
        """
        if not self.populated:
            raise ("ERROR: class %s has not been populated" % repr(self.__class__) )
        args = []
        # build update attributes
        for column, type, typeid in self.dbColumns:
            if getKeyColumn(self.__class__, column):
                continue
            args.append(self.findAttribute(column))
        # build where clause
        for keyColumn, type in self.dbKeyColumns:
            args.append( self.findAttribute(keyColumn))

        sql = self.updateSQL % tuple(args)
        self.setDirty(0)
        return self.augmentation.runOperation(sql)

    def insertRow(self):
        """insert a new row for this object instance.
        """
        if not self.populated:
            raise DBError("class %s has not been populated" % repr(self.__class__) )     
        args = []
        # build values
        for column, type, typeid in self.dbColumns:
            args.append(self.findAttribute(column))

        sql = self.insertSQL % tuple(args)
        self.setDirty(0)        

        return self.augmentation.runOperation(sql)

    def deleteRow(self):
        """delete the row for this object from the database.
        """
        if not self.populated:
            raise DBError("class %s has not been populated" % repr(self.__class__) )                    
        args = []
        # build where clause
        for keyColumn, type in self.dbKeyColumns:
            args.append(self.findAttribute(keyColumn))

        sql = self.deleteSQL % tuple(args)
        return self.augmentation.runOperation(sql)

    def selectRow(self):
        """load this rows current values from the database.
        """
        if not self.populated:
            raise DBError("class %s has not been populated" % repr(self.__class__) )                    
        args = []
        # build where clause
        for keyColumn, type in self.dbKeyColumns:
            args.append(self.findAttribute(keyColumn))

        sql = self.selectSQL % tuple(args)
        return self.augmentation.runQuery(sql).addCallback(self.gotSelectData)

    def gotSelectData(self, data):
        if len(data) > 1:
            raise DBError("ERROR: select data included more than one row!")
        if len(data) == 0:
            raise DBError("ERROR: select data was empty")
        actualPos = 0
        for i in range(0, len(self.dbColumns)):
            if not getKeyColumn(self.__class__, self.dbColumns[i][0] ):            
                setattr(self, self.dbColumns[i][0], data[0][actualPos] )
                actualPos = actualPos + 1
        self.setDirty(0)
        return self

    def setDirty(self, flag):
        """must use this to set dirty... or dirty flag gets set.
        """
        self.__dict__["dirty"] = flag
        
    def __setattr__(self, name, value):
        """special setattr so prevent changing of key values.
        """
        # build where clause
        if getKeyColumn(self.__class__, name):
            raise DBError("cannot assign to key column attribute <%s> of RowObject class" % name)

        if name in self.rowColumns:
            if value != self.__dict__.get(name,None):
                self.__dict__["dirty"] = 1  # no longer in sync with database
            
        self.__dict__[name] = value


    def createDefaultAttributes(self):
        """populate instance with default attributes. Used when creating a new instance
        NOT from the database.
        """
        for attr in self.rowColumns:
            if getKeyColumn(self.__class__, attr):
                continue
            for column, ctype, typeid in self.dbColumns:
                if string.lower(column) == string.lower(attr):
                    q = dbTypeMap.get(ctype, None)
                    if q == NOQUOTE:
                        setattr(self, attr, 0)
                    else:
                        setattr(self, attr, "")


class DBReflector:
    """I am a class able to interrogate a relational database to extract
    system schema information and build RowObject class objects that can
    interact with specific tables.

    I manage the construction of these class in a deferred manner. When
    all the specified classes are constructed, the "ready" method is
    called.

    <stubs> is a set of definitions of classes to construct:
       [ (StubClass, args, databaseTableName, KeyColumns) ]

    StubClass is a user-defined class that the constructed class will be
    constructed from. It should be derived from RowObject
       
    """

    def __init__(self, augmentation, stubs):
        self.aug = augmentation
        self.stubs = stubs
        self.rowClasses = {}

    def populate(self):
        """This actually runs the population of the classes. It returns
        a deferred that applications can use to tell when the process
        is complete.
        """
        return self.aug.runInteraction(self.constructClasses)
    
    def constructClasses(self, transaction):
        """Used to construct the row classes in a single interaction.
        """
        for (stubClass, tableName, keyColumns) in self.stubs:
            print "Constructing class %s for table %s" %(repr(stubClass), tableName)
            if not issubclass(stubClass, RowObject):
                raise DBError("Stub class must be derived from RowClass")

            self._populateRowClass(transaction, self.aug, stubClass, tableName, keyColumns)
            self.rowClasses[tableName] = stubClass

    def _populateRowClass(self, transaction, aug, rowClass, tableName, keyColumns):
        """construct all the SQL for database operations on <tableName> and
        populate the class <rowClass> with that info.
        NOTE: works with Postgresql for now...
        NOTE: 26 - 29 are system column types that you shouldn't use...

        """
        #if rowClass.tableName and rowClass.tableName != tableName:
        #    raise ("ERROR: class %s has already had SQL generated for table %s." % (repr(rowClass), tableName) )

        sql = """SELECT pg_attribute.attname, pg_type.typname, pg_attribute.atttypid
        FROM pg_class, pg_attribute, pg_type
        WHERE pg_class.oid = pg_attribute.attrelid
        AND pg_attribute.atttypid = pg_type.oid
        AND pg_class.relname = '%s'
        AND pg_attribute.atttypid not in (26,27,28,29)""" % tableName

        # get the columns for the table
        transaction.execute(sql)
        columns = transaction.fetchall()

        # populate rowClass data
        rowClass.tableName = tableName
        rowClass.dbColumns = columns
        rowClass.dbKeyColumns = keyColumns
        rowClass.augmentation = aug

        rowClass.selectSQL = self.buildSelectSQL(rowClass, tableName, columns, keyColumns)
        rowClass.updateSQL = self.buildUpdateSQL(rowClass, tableName, columns, keyColumns)
        rowClass.insertSQL = self.buildInsertSQL(tableName, columns)
        rowClass.deleteSQL = self.buildDeleteSQL(tableName, keyColumns)
        rowClass.populated = 1
        return rowClass

    def buildSelectSQL(self, rowClass, tableName, columns, keyColumns):
        """build the SQL to select a single row from the database
        for a rowObject.
        """
        sql = "SELECT "
        # build select columns
        first = 1        
        for column, type, typeid in columns:
            if getKeyColumn(rowClass, column):
                continue
            if not first:
                sql = sql + ", "
            sql = sql + "  %s" % (column)
            first = 0

        sql = sql + " FROM %s WHERE " % tableName

        # build where clause
        first = 1
        for keyColumn, type in keyColumns:
            if not first:
                sql = sql + " AND "
            sql = sql + "   %s = %s " % (keyColumn, quote("%s", type) )
            first = 0
        return sql

    def buildUpdateSQL(self, rowClass, tableName, columns, keyColumns):
        """build the SQL to update objects to the database. This
        return SQL that is used to contruct a rowObject class.
        """
        sql = "UPDATE %s SET" % tableName
        # build update attributes
        first = 1        
        for column, type, typeid in columns:
            if getKeyColumn(rowClass, column):
                continue
            if not first:
                sql = sql + ", "
            sql = sql + "  %s = %s" % (column, quote("%s", type))
            first = 0

        # build where clause
        first = 1
        sql = sql + "  WHERE "
        for keyColumn, type in keyColumns:
            if not first:
                sql = sql + " AND "
            sql = sql + "   %s = %s " % (keyColumn, quote("%s", type) )
            first = 0
        #print "Generated SQL:", sql
        return sql

    def buildInsertSQL(self, tableName, columns):
        """Build SQL to insert a new row into the table.
        """
        sql = "INSERT INTO %s (" % tableName
        # build column list
        first = 1
        for column, type, typeid in columns:
            if not first:
                sql = sql + ", "
            sql = sql + column
            first = 0

        sql = sql + " ) VALUES ("

        # build values list
        first = 1
        for column, type, typeid in columns:
            if not first:
                sql = sql + ", "
            sql = sql + quote("%s", type)
            first = 0

        sql = sql + ")"
        return sql

    def buildDeleteSQL(self, tableName, keyColumns):
        """Build the SQL to delete a row from the table.
        """
        sql = "DELETE FROM %s " % tableName
        # build where clause
        first = 1
        sql = sql + "  WHERE "
        for keyColumn, type in keyColumns:
            if not first:
                sql = sql + " AND "
            sql = sql + "   %s = %s " % (keyColumn, quote("%s", type) )
            first = 0
        return sql


class KeyFactory:
    """I create unique keys to use as primary key columns in database tables.
    I am able to use a specified range.
    (NOTE: not thread safe....)
    """
    def __init__(self, minimum, pool):
        self.min = minimum
        self.pool = minimum + pool
        self.current = self.min

    def getNextKey(self):
        next = self.current + 1
        self.current = next
        if self.current >= self.pool:
            raise "Key factory key pool exceeded."
        return next
        
    
NOQUOTE = 1
USEQUOTE = 2

dbTypeMap = {
    "bool": NOQUOTE,    
    "int2": NOQUOTE,
    "int4": NOQUOTE,
    "float8": NOQUOTE,
    "char": USEQUOTE,
    "varchar": USEQUOTE,
    "text": USEQUOTE,
    "timestamp": USEQUOTE
    }


### Utility functions

def getKeyColumn(rowClass, name):
    for keyColumn, type in rowClass.dbKeyColumns:
        if name == keyColumn:
            return name
    return None

def safe(text):
    """Make a string safe to include in an SQL statement
    """
    return text.replace("'", "''")


def quote(value, typeCode):
    """Add quotes for text types and no quotes for integer types.
    NOTE: uses Postgresql type codes..
    """
    q = dbTypeMap.get(typeCode, None)
    if not q:
        raise ("Type %s not known" % typeCode)
    if q == NOQUOTE:
        return value
    elif q == USEQUOTE:
        return "'%s'" % safe(value)

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
