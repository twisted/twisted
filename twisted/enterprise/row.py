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

"""
A (R)elational (O)bject (W)rapper.

This is an extremely thin wrapper.
"""

# System Imports

import string
import time

# Twisted Imports

from twisted.python import log

# Sibling Imports

import adbapi

class DBError(Exception):
    pass


class RowObject:
    """I represent a row in a table in a relational database.

    My class is "populated" by a DBReflector object. After I am
    populated, instances of me are able to interact with a particular
    database table.

    You should use a class derived from this class for each database
    table.

    enterprise.Augentation.loadObjectsFrom() is used to create sets of
    instance of objects of this class from database tables.

    Once created, the "key column" attributes cannot be changed.
    """

    ### Class Attributes populated by the DBReflector

    dbColumns = []     # list of column names and types for the table I came from
    dbKeyColumns = []  # list of key columns to identify instances in the db
    tableName = ""
    populated = 0    # set on the class when the class is "populated" with SQL
    dirty = 0        # set on an instance then the instance is out-of-sync with the database

    ### Class Attributes that users must supply

    rowColumns = []  # list of the columns in the table with the correct case.
                     # this will be used to create member variables.

    def assignKeyAttr(self, attrName, value):
        """Assign to a key attribute.

        This cannot be done through normal means to protect changing
        keys of db objects.
        """
        found = 0
        for keyColumn, type in self.dbKeyColumns:
            if keyColumn == attrName:
                found = 1
        if not found:
            raise DBError("%s is not a key columns." % attrName)
        self.__dict__[attrName] = value

    def findAttribute(self, attrName):
        """Find an attribute by caseless name.
        """
        for attr in self.rowColumns:
            if string.lower(attr) == string.lower(attrName):
                return getattr(self, attr)
        raise DBError("Unable to find attribute %s" % attrName)


    def __setattr__(self, name, value):
        """Special setattr to prevent changing of key values.
        """
        # build where clause
        if getKeyColumn(self.__class__, name):
            raise DBError("cannot assign value <%s> to key column attribute <%s> of RowObject class" % (value,name))

        if name in self.rowColumns:
            if value != self.__dict__.get(name,None) and not self.dirty:
                ##print "dirtying %s for %s" % (self.objectType.name, name)
                self.setDirty(1)

        self.__dict__[name] = value


    def createDefaultAttributes(self):
        """Populate instance with default attributes.

        This is used when creating a new instance NOT from the
        database.
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


    def setDirty(self, flag):
        """Use this to set the 'dirty' flag.

        (note: this avoids infinite recursion in __setattr__, and
        prevents the 'dirty' flag )
        """
        self.__dict__["dirty"] = flag



def defaultFactoryMethod(rowClass, data, kw):
    """Used by loadObjects to create rowObject instances.
    """
    newObject = rowClass()
    newObject.__dict__.update(kw)
    return newObject


class _TableInfo:
    """(Internal)

    A collection of attributes related to a class / table union.
    """
    def __init__(self,
                 rowClass,
                 tableName,
                 dbColumns,
                 dbKeyColumns,
                 selectSQL,
                 updateSQL,
                 insertSQL,
                 deleteSQL):
        "Initialize me."
        self.rowClass = rowClass
        self.tableName = tableName
        self.dbColumns = dbColumns
        self.dbKeyColumns = dbKeyColumns
        self.selectSQL = selectSQL
        self.updateSQL = updateSQL
        self.insertSQL = insertSQL
        self.deleteSQL = deleteSQL

class DBReflector(adbapi.Augmentation):
    """I reflect on a database and load RowObjects from it.

    In order to do this, I interrogate a relational database to
    extract schema information and interface with RowObject class
    objects that can interact with specific tables.  Currently this
    works only with PostgreSQL databases, but this functionality will
    hopefully be extended
    """
    populated = 0

    def __init__(self, dbpool, stubs, populatedCallback):
        """
        Initialize me against a database.

        Arguments:

          * dbpool: a database pool.

          * stubs: a set of definitions of classes to construct, of
            the form [ (StubClass, args, databaseTableName,
            KeyColumns) ]

            Each StubClass is a user-defined class that the
            constructed class will be constructed from.  It should be
            derived from RowObject.

        """

        adbapi.Augmentation.__init__(self, dbpool)
        self.stubs = stubs
        self.rowClasses = {}
        self.populatedCallback = populatedCallback
        self._populate()

    def loadObjectsFrom(self, tableName, keyColumns, data, rowClass,
                        whereClause = "1 = 1",
                        factoryMethod = defaultFactoryMethod):
        """Load a set of RowObjects from a database.

        Create a set of python objects of <rowClass> from the contents
        of a table populated with appropriate data members. The
        constructor for <rowClass> must take no args. Example to use
        this::

            class EmployeeRow(row.RowObject):
                pass

            def gotEmployees(employees):
                for emp in employees:
                    emp.manager = "fred smith"
                    manager.updateRow(emp)

            manager.loadObjectsFrom("employee",
                                    ["employee_name", "varchar"],
                                    userData,
                                    employeeFactory,
                                    EmployeeRow,
                                    "employee_name like 'm%%'"
                                    ).addCallback(gotEmployees)

        NOTE: this functionality is experimental. be careful.
        """
        return self.runInteraction(self._objectLoader, tableName, keyColumns,
                                   data, rowClass, whereClause, factoryMethod)

    def _objectLoader(self, transaction, tableName, keyColumns, data, rowClass, whereClause, factoryMethod):
        """worker method to load objects from a table.
        """
        # get the data from the table
        sql = 'SELECT '
        first = 1
        for column, typeid, type in rowClass.dbColumns:
            if first:
                first = 0
            else:
                sql = sql + ","
            sql = sql + " %s" % column
        sql = sql + " FROM %s WHERE %s""" % (tableName, whereClause)
        transaction.execute(sql)
        rows = transaction.fetchall()
        # construct the objects
        results = []
        for args in rows:
            kw = {}
            for i in range(0,len(args)):
                columnName = rowClass.dbColumns[i][0]
                for attr in rowClass.rowColumns:
                    if string.lower(attr) == string.lower(columnName):
                        kw[attr] = args[i]
                        break
            resultObject = apply(factoryMethod, (rowClass, data, kw) )
            results.append(resultObject)

        #print "RESULTS", results
        return results

    def _populate(self):
        """
        """
        self.runInteraction(self._transPopulateClasses).addCallbacks(self.populatedCallback).arm()

    def _transPopulateClasses(self, transaction):
        """Used to construct the row classes in a single interaction.
        """
        for (stubClass, tableName, keyColumns) in self.stubs:
            # log.msg( "retrieving class %s for table %s" %(repr(stubClass), tableName))
            if not issubclass(stubClass, RowObject):
                raise DBError("Stub class must be derived from RowClass")

            self._populateRowClass(transaction, stubClass, tableName, keyColumns)
        self.populated = 1

    def _populateRowClass(self, transaction, rowClass, tableName, keyColumns):
        """construct all the SQL for database operations on <tableName> and
        populate the class <rowClass> with that info.
        NOTE: works with Postgresql for now...
        NOTE: 26 - 29 are system column types that you shouldn't use...

        """
        sql = """
          SELECT pg_attribute.attname, pg_type.typname, pg_attribute.atttypid
          FROM pg_class, pg_attribute, pg_type
          WHERE pg_class.oid = pg_attribute.attrelid
          AND pg_attribute.atttypid = pg_type.oid
          AND pg_class.relname = '%s'
          AND pg_attribute.atttypid not in (26,27,28,29)\
        """ % tableName

        # get the columns for the table
        try:
            transaction.execute(sql)
        except ValueError, e:
            print "No data trying to populate rowclass <%s>. [%s] SQL was: '%s'" % (tableName,  e, sql)
            raise e
        except:
            print "unknow ERROR!", sql
            raise
        columns = transaction.fetchall()

        # populate rowClass data

        # TODO: peek at 'dbColumns' and 'dbKeyColumns' and make sure
        # they're the same if the class is already populated

        rowClass.tableName = tableName
        rowClass.dbColumns = columns
        rowClass.dbKeyColumns = keyColumns
        rowClass.populated = 1

        self.rowClasses[str(rowClass)] = _TableInfo(
            rowClass,
            tableName,
            columns,
            keyColumns,
            self.buildSelectSQL(rowClass, tableName, columns, keyColumns),
            self.buildUpdateSQL(rowClass, tableName, columns, keyColumns),
            self.buildInsertSQL(tableName, columns),
            self.buildDeleteSQL(tableName, keyColumns))
        return rowClass

    def __setstate__(self, state):
        self.__dict__ = state
        self._populate()

    def getTableInfo(self, rowObject):
        """Get a TableInfo record about a particular instance.

        Arguments:

          * rowObject: a RowObject instance of a class previously
            registered with me.

        This record contains various information about the instance's
        class as registered with this reflector.

        Raises:

          * twisted.enterprise.row.DBError: raised if this class was
            not previously registered.
        """
        try:
            return self.rowClasses[str(rowObject.__class__)]
        except KeyError:
            raise DBError("class %s was not registered with %s" % (
                rowObject.__class__, self))

    def buildSelectSQL(self, rowClass, tableName, columns, keyColumns):
        """(Internal) Build SQL to select a row for an existing rowObject.
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
        """(Internal) Build SQL to update a RowObject.

        Returns: SQL that is used to contruct a rowObject class.
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
        """(Internal) Build SQL to insert a new row.

        Returns: SQL that is used to insert a new row for a rowObject
        instance not created from the database.
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


    def updateRowSQL(self, rowObject):
        # was RowObject.buildUpdateSQL
        """build SQL to update my current state.
        """
        args = []
        # build update attributes
        for column, type, typeid in rowObject.dbColumns:
            if not getKeyColumn(rowObject.__class__, column):
                args.append(rowObject.findAttribute(column))
        # build where clause
        for keyColumn, type in rowObject.dbKeyColumns:
            args.append( rowObject.findAttribute(keyColumn))
        return self.getTableInfo(rowObject).updateSQL % tuple(args)


    def updateRow(self, rowObject):
        # was RowObject.updateRow
        """update my contents to the database.
        """
        sql = self.updateRowSQL(rowObject)
        rowObject.setDirty(0)
        return self.runOperation(sql)

    def insertRowSQL(self, rowObject):
        """build SQL to insert my current state.
        """
        args = []
        # build values
        for column, type, typeid in rowObject.dbColumns:
            args.append(rowObject.findAttribute(column))
        return self.getTableInfo(rowObject).insertSQL % tuple(args)

    def insertRow(self, rowObject):
        """insert a new row for this object instance.
        """
        rowObject.setDirty(0)
        sql = self.insertRowSQL(rowObject)
        return self.runOperation(sql)

    def deleteRowSQL(self, rowObject):
        """build SQL to delete me from the db.
        """
        args = []
        # build where clause
        for keyColumn, type in rowObject.dbKeyColumns:
            args.append(rowObject.findAttribute(keyColumn))

        return self.getTableInfo(rowObject).deleteSQL % tuple(args)

    def deleteRow(self, rowObject):
        """delete the row for this object from the database.
        """
        sql = self.deleteRowSQL(rowObject)
        return self.runOperation(sql)

    def selectRowSQL(self, rowObject):
        args = []
        # build where clause
        for keyColumn, type in rowObject.dbKeyColumns:
            args.append(rowObject.findAttribute(keyColumn))
        return self.getTableInfo(rowObject).selectSQL % tuple(args)

    def selectRow(self, rowObject):
        """load this rows current values from the database.
        """
        sql = self.selectRowSQL(rowObject)
        return self.runQuery(sql).addCallback(self._cbSelectData, rowObject)

    def _cbSelectData(self, data, rowObject):
        if len(data) > 1:
            raise DBError("select data included more than one row")
        if len(data) == 0:
            raise DBError("select data was empty")
        actualPos = 0
        for i in range(0, len(rowObject.dbColumns)):
            if not getKeyColumn(rowObject.__class__, rowObject.dbColumns[i][0] ):
                for col in rowObject.rowColumns:
                    if string.lower(col) == string.lower(rowObject.dbColumns[i][0]):
                        setattr(rowObject, col, data[0][actualPos] )
                actualPos = actualPos + 1
        rowObject.setDirty(0)
        return rowObject




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


class StatementBatch:
    """A keep a set of SQL statements to be executed in a single batch.
    """
    def __init__(self):
        self.statements = []

    def addStatement(self, statement):
        self.statements.append(statement)

    def batchSQL(self):
        batchSQL =  string.join(self.statements,";\n")
        self.statements = []
        return batchSQL

    def getSize(self):
        return len(self.statements)

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
        if string.lower(name) == keyColumn:
            return name
    return None

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
