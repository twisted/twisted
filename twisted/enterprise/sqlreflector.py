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
import weakref

from twisted.enterprise import adbapi
from twisted.enterprise.util import DBError, getKeyColumn, quote, _TableInfo, _TableRelationship
from twisted.enterprise.row import RowObject

from twisted.enterprise import reflector

class SQLReflector(reflector.Reflector, adbapi.Augmentation):
    """I reflect on a database and load RowObjects from it.

    In order to do this, I interrogate a relational database to
    extract schema information and interface with RowObject class
    objects that can interact with specific tables.  Currently this
    works only with PostgreSQL databases, but this functionality will
    hopefully be extended
    """
    populated = 0
    conditionalLabels = {
        reflector.EQUAL       : "=",
        reflector.LESSTHAN    : "<",
        reflector.GREATERTHAN : ">",
        reflector.LIKE        : "like"
        }
    
    def __init__(self, dbpool, rowClasses, populatedCallback):
        """
        Initialize me against a database.
        """
        adbapi.Augmentation.__init__(self, dbpool)
        reflector.Reflector.__init__(self, rowClasses, populatedCallback)        

    def _really_populate(self):
        self.runInteraction(self._transPopulateSchema).addCallbacks(
            self.populatedCallback)

    def _transPopulateSchema(self, transaction):
        """Used to construct the row classes in a single interaction.
        """
        for rc in self.rowClasses:
            if not issubclass(rc, RowObject):
                raise DBError("Stub class (%s) is not derived from RowObject" % str(rc.rowClass))

            self._populateSchemaFor(transaction, rc)
        self.populated = 1

    def _populateSchemaFor(self, transaction, rc):
        """construct all the SQL for database operations on <tableName> and
        populate the class <rowClass> with that info.
        NOTE: works with Postgresql for now...
        NOTE: 26 - 29 are system column types that you shouldn't use...

        """
        attributes = ("rowColumns", "rowKeyColumns", "rowTableName" )
        for att in attributes:
            if not hasattr(rc, att):
                raise DBError("RowClass must have class variable: %s" % att)
            
        tableInfo = _TableInfo(rc)
        #print "populating: ", tableInfo.rowClass, tableInfo.rowTableName        
        sql = """
          SELECT pg_attribute.attname, pg_type.typname, pg_attribute.atttypid
          FROM pg_class, pg_attribute, pg_type
          WHERE pg_class.oid = pg_attribute.attrelid
          AND pg_attribute.atttypid = pg_type.oid
          AND pg_class.relname = '%s'
          AND pg_attribute.atttypid not in (26,27,28,29)\
        """ % tableInfo.rowTableName

        # get the columns for the table
        try:
            transaction.execute(sql)
        except ValueError, e:
            log.msg("No data trying to populate schema <%s>. [%s] SQL was: '%s'" % (tableInfo.rowTableName,  e, sql))
            raise e
        except:
            log.msg("Unknown ERROR: %s" % sql)
            raise
        columns = transaction.fetchall()

        tableInfo.dbColumns = columns
        tableInfo.updateSQL = self.buildUpdateSQL(tableInfo.rowClass, tableInfo.rowTableName, columns, tableInfo.rowKeyColumns)
        tableInfo.insertSQL = self.buildInsertSQL(tableInfo.rowTableName, columns)
        tableInfo.deleteSQL = self.buildDeleteSQL(tableInfo.rowTableName, tableInfo.rowKeyColumns)

        self.populateSchemaFor(tableInfo)
        
    def loadObjectsFrom(self, tableName, data = None, whereClause = [], parent = None):

        """Load a set of RowObjects from a database.

        Create a set of python objects of <rowClass> from the contents
        of a table populated with appropriate data members. The
        constructor for <rowClass> must take no args. Example to use
        this:

          |  class EmployeeRow(row.RowObject):
          |      pass
          |
          |  def gotEmployees(employees):
          |      for emp in employees:
          |          emp.manager = "fred smith"
          |          manager.updateRow(emp)
          |
          |  reflector.loadObjectsFrom("employee",
          |                          userData,
          |                          "employee_name like 'm%%'"
          |                          ).addCallback(gotEmployees)

        """
        return self.runInteraction(self._objectLoader, tableName, data, whereClause, parent)

    def _objectLoader(self, transaction, tableName, data, whereClause, parent):
        """worker method to load objects from a table. NOTE: works, but needs to be make more readable!
        """
        tableInfo = self.schema[tableName]
        # get the data from the table
        sql = "SELECT "
        first = 1
        for column, type, typeid in tableInfo.dbColumns:
            if first:
                first = 0
            else:
                sql = sql + ","
            sql = sql + " %s" % column
        sql = sql + " FROM %s """ % (tableName)
        if whereClause:
            sql += " WHERE "
            first = 1
            for wItem in whereClause:
                if first:
                    first = 0
                else:
                    sql += " AND "
                (columnName, cond, value) = wItem
                t = self.findTypeFor(tableName, columnName)
                quotedValue = quote(value, t)
                sql += "%s %s %s" % (columnName, self.conditionalLabels[cond], quotedValue)

        transaction.execute(sql)
        rows = transaction.fetchall()
        # construct the objects
        results = []
        for args in rows:
            kw = {}
            for i in range(0,len(args)):
                columnName = tableInfo.dbColumns[i][0]
                for attr in tableInfo.rowClass.rowColumns:
                    if string.lower(attr) == string.lower(columnName):
                        kw[attr] = args[i]
                        break
            # find the row in the cache or add it
            resultObject = self.findInCache(tableInfo.rowClass, kw)
            if not resultObject:
                resultObject = apply(tableInfo.rowFactoryMethod[0], (tableInfo.rowClass, data, kw) )
                self.addToCache(resultObject)                
            results.append(resultObject)

        if self.schema[ tableName ]:
            self.loadChildRows(tableInfo.rowClass, results, transaction, data)

        # NOTE: using the "container" variable as the container is a temporary measure until containment is figured out.
        if parent:
            if hasattr(parent, "container"):
                parent.container.extend(results)
            else:
                setattr(parent, "container", results)
        return results

    def loadChildRows(self, rowClass, rows, transaction, data):
        """Load the child rows for each row in the set.
        """
        for newRow in rows:
            for relationship in self.schema[ rowClass.rowTableName ].childTables:
                whereClause = []
                first = 1
                for i in range(0,len(relationship.childColumns)):
                    value = getattr(newRow, relationship.parentColumns[i][0])
                    #value = quote(getattr(newRow, relationship.parentColumns[i][0]), relationship.parentColumns[i][1])                    

                    whereClause.append( [relationship.childColumns[i][0], reflector.EQUAL, value] )
                    
                self._objectLoader(transaction,
                                   relationship.childTableName,
                                   data,
                                   whereClause,
                                   newRow)

    def findTypeFor(self, tableName, columnName):
        tableInfo = self.schema[tableName]
        for column, type, typeid in tableInfo.dbColumns:
            if column.upper() == columnName.upper():
                return type
            

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
        """build SQL to update my current state.
        """
        args = []
        tableInfo = self.schema[rowObject.rowTableName]
        # build update attributes
        for column, type, typeid in tableInfo.dbColumns:
            if not getKeyColumn(rowObject.__class__, column):
                args.append(rowObject.findAttribute(column))
        # build where clause
        for keyColumn, type in tableInfo.rowKeyColumns:
            args.append( rowObject.findAttribute(keyColumn))

        return self.getTableInfo(rowObject).updateSQL % tuple(args)


    def updateRow(self, rowObject):
        """update my contents to the database.
        """
        sql = self.updateRowSQL(rowObject)
        rowObject.setDirty(0)
        return self.runOperation(sql)

    def insertRowSQL(self, rowObject):
        """build SQL to insert my current state.
        """
        args = []
        tableInfo = self.schema[rowObject.rowTableName]        
        # build values
        for column, type, typeid in tableInfo.dbColumns:
            args.append(rowObject.findAttribute(column))
        return self.getTableInfo(rowObject).insertSQL % tuple(args)

    def insertRow(self, rowObject):
        """insert a new row for this object instance.
        """
        rowObject.setDirty(0)
        sql = self.insertRowSQL(rowObject)
        self.addToCache(rowObject)
        return self.runOperation(sql)

    def deleteRowSQL(self, rowObject):
        """build SQL to delete me from the db.
        """
        args = []
        tableInfo = self.schema[rowObject.rowTableName]        
        # build where clause
        for keyColumn, type in tableInfo.rowKeyColumns:
            args.append(rowObject.findAttribute(keyColumn))

        return self.getTableInfo(rowObject).deleteSQL % tuple(args)

    def deleteRow(self, rowObject):
        """delete the row for this object from the database.
        """
        sql = self.deleteRowSQL(rowObject)
        self.removeFromCache(rowObject)
        return self.runOperation(sql)

