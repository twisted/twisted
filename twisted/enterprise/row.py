#NOTE: no imports?!

class RowObject:
    """I represent a row in a table in a relational database. My class is "populated"
    by the buildRowClass method of this module. After I am populated, instances of me
    are able to interact with a particular database table.

    You should use a class derived from this class for each database table.

    enterprise.Augentation.loadObjectsFrom() is used to create sets of instance of objects
    of this class from database tables.

    Once created, the "key column" attributes cannot be changed.
    """
    columns = []     # list of column names and types for the table I came from
    keyColumns = []  # list of key columns to identify instances in the db
    tableName = ""
    selectSQL = ""
    updateSQL = ""
    insertSQL = ""
    deleteSQL = ""
    populated = 0    # set on the class when the class is "populated" with SQL
    insync = 0       # set on an instance then the instance is in-sync with the database

    def __init__(self, *args, **kw):
        """this should accept the key column values as names keywords. These must be key
        arguments as the order is undefined in which the key columns are retrieved from
        the database when keyColumns is populated.
        """
        if not self.populated:
            raise ("ERROR: class %s has not been populated" % repr(self.__class__) )            
        if len(args) != 0:
            raise ("ERROR: you cannot pass non-keyword args to construct a RowObject")        
        if len(kw) != len(self.keyColumns):
            raise ("ERROR: wrong number of key arguments %s" % repr(kw) )

        for key in kw.keys():
            if not getKeyColumn(self.__class__, key):
                raise ("ERROR: wrong key argument: <%s>" % key)
        # set the key attributes
        self.__dict__.update(kw)             
    
    def updateRow(self):
        """update my contents to the database.
        """
        if not self.populated:
            raise ("ERROR: class %s has not been populated" % repr(self.__class__) )
        args = []
        # build update attributes
        for column, type, typeid in self.columns:
            if getKeyColumn(self.__class__, column):
                continue
            args.append(self.__dict__[column])
        # build where clause
        for keyColumn, type in self.keyColumns:
            args.append( self.__dict__[keyColumn])

        sql = self.updateSQL % tuple(args)
        return self.augmentation.runOperation(sql).addCallback(self.setSync)

    def insertRow(self):
        """insert a new row for this object instance.
        """
        if not self.populated:
            raise ("ERROR: class %s has not been populated" % repr(self.__class__) )     
        args = []
        # build values
        for column, type, typeid in self.columns:
            args.append(self.__dict__[column])

        sql = self.insertSQL % tuple(args)
        return self.augmentation.runOperation(sql).addCallback(self.setSync)

    def deleteRow(self):
        """delete the row for this object from the database.
        """
        if not self.populated:
            raise ("ERROR: class %s has not been populated" % repr(self.__class__) )                    
        args = []
        # build where clause
        for keyColumn, type in self.keyColumns:
            args.append( self.__dict__[keyColumn])

        sql = self.deleteSQL % tuple(args)
        return self.augmentation.runOperation(sql)

    def selectRow(self):
        """load this rows current values from the database.
        """
        if not self.populated:
            raise ("ERROR: class %s has not been populated" % repr(self.__class__) )                    
        args = []
        # build where clause
        for keyColumn, type in self.keyColumns:
            args.append( self.__dict__[keyColumn])

        sql = self.selectSQL % tuple(args)
        print "sql=", sql
        return self.augmentation.runQuery(sql).addCallback(self.gotSelectData)

    def gotSelectData(self, data):
        if len(data) > 1:
            raise "ERROR: select data included more than one row!"
        if len(data) == 0:
            raise "ERROR: select data was empty"
        actualPos = 0
        for i in range(0, len(self.columns)):
            if not getKeyColumn(self.__class__, self.columns[i][0] ):            
                setattr(self, self.columns[i][0], data[0][actualPos] )
                actualPos = actualPos + 1
        self.setSync()
        return self
        
        
    def __setattr__(self, name, value):
        """special setattr so prevent changing of key values.
        """
        # build where clause
        if getKeyColumn(self.__class__, name):
            raise ("ERROR: cannot assign to key column attribute <%s> of RowObject class" % name)
        self.__dict__[name] = value
        self.__dict__["insync"] = 0  # no longer in sync with database

    def setSync(self):
        self.insync = 1

def populateRowClass(aug, rowClass, tableName, keyColumns):
    return aug.runInteraction(_populateRowClass, aug, rowClass, tableName, keyColumns)
                   
def _populateRowClass(transaction, aug, rowClass, tableName, keyColumns):
    """construct all the SQL for database operations on <tableName> and
    populate the class <rowClass> with that info.
    NOTE: works with Postgresql for now...
    NOTE: 26 - 29 are system column types that you shouldn't use...
    
    """
    if rowClass.tableName and rowClass.tableName != tableName:
        raise ("ERROR: class %s has already had SQL generated for table %s." % (repr(rowClass), tableName) )

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
    rowClass.columns = columns
    rowClass.keyColumns = keyColumns
    rowClass.augmentation = aug

    rowClass.selectSQL = buildSelectSQL(rowClass, tableName, columns, keyColumns)
    rowClass.updateSQL = buildUpdateSQL(rowClass, tableName, columns, keyColumns)
    rowClass.insertSQL = buildInsertSQL(tableName, columns)
    rowClass.deleteSQL = buildDeleteSQL(tableName, keyColumns)
    rowClass.populated = 1
    return rowClass

def buildSelectSQL(rowClass, tableName, columns, keyColumns):
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
    print "Generated SQL:", sql
    return sql

def buildUpdateSQL(rowClass, tableName, columns, keyColumns):
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

def buildInsertSQL(tableName, columns):
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

def buildDeleteSQL(tableName, keyColumns):
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
    for keyColumn, type in rowClass.keyColumns:
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

