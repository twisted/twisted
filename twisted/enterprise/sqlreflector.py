# -*- test-case-name: twisted.test.test_reflector -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.enterprise import reflector
from twisted.enterprise.util import DBError, getKeyColumn, quote, safe
from twisted.enterprise.util import _TableInfo
from twisted.enterprise.row import RowObject

from twisted.python import reflect

class SQLReflector(reflector.Reflector):
    """
    DEPRECATED.
    
    I reflect on a database and load RowObjects from it.

    In order to do this, I interrogate a relational database to
    extract schema information and interface with RowObject class
    objects that can interact with specific tables. 
    """
    populated = 0
    conditionalLabels = {
        reflector.EQUAL       : "=",
        reflector.LESSTHAN    : "<",
        reflector.GREATERTHAN : ">",
        reflector.LIKE        : "like"
        }

    def __init__(self, dbpool, rowClasses):
        """Initialize me against a database.
        """
        reflector.Reflector.__init__(self, rowClasses)
        self.dbpool = dbpool

    def _populate(self):
        self._transPopulateSchema()

    def _transPopulateSchema(self):
        """Used to construct the row classes in a single interaction.
        """
        for rc in self.rowClasses:
            if not issubclass(rc, RowObject):
                raise DBError("Stub class (%s) is not derived from RowObject" % reflect.qual(rc.rowClass))

            self._populateSchemaFor(rc)
        self.populated = 1

    def _populateSchemaFor(self, rc):
        """Construct all the SQL templates for database operations on
        <tableName> and populate the class <rowClass> with that info.
        """
        attributes = ("rowColumns", "rowKeyColumns", "rowTableName" )
        for att in attributes:
            if not hasattr(rc, att):
                raise DBError("RowClass %s must have class variable: %s" % (rc, att))

        tableInfo = _TableInfo(rc)
        tableInfo.updateSQL = self.buildUpdateSQL(tableInfo)
        tableInfo.insertSQL = self.buildInsertSQL(tableInfo)
        tableInfo.deleteSQL = self.buildDeleteSQL(tableInfo)
        self.populateSchemaFor(tableInfo)

    def escape_string(self, text):
        """Escape a string for use in an SQL statement. The default
        implementation escapes ' with '' and \ with \\. Redefine this
        function in a subclass if your database server uses different
        escaping rules.
        """
        return safe(text)

    def quote_value(self, value, type):
        """Format a value for use in an SQL statement.

        @param value: a value to format as data in SQL.
        @param type: a key in util.dbTypeMap.
        """
        return quote(value, type, string_escaper=self.escape_string)

    def loadObjectsFrom(self, tableName, parentRow=None, data=None,
                        whereClause=None, forceChildren=0):
        """Load a set of RowObjects from a database.

        Create a set of python objects of <rowClass> from the contents
        of a table populated with appropriate data members.
        Example::

          |  class EmployeeRow(row.RowObject):
          |      pass
          |
          |  def gotEmployees(employees):
          |      for emp in employees:
          |          emp.manager = "fred smith"
          |          manager.updateRow(emp)
          |
          |  reflector.loadObjectsFrom("employee",
          |                          data = userData,
          |                          whereClause = [("manager" , EQUAL, "fred smith")]
          |                          ).addCallback(gotEmployees)

        NOTE: the objects and all children should be loaded in a single transaction.
        NOTE: can specify a parentRow _OR_ a whereClause.

        """
        if parentRow and whereClause:
            raise DBError("Must specify one of parentRow _OR_ whereClause")
        if parentRow:
            info = self.getTableInfo(parentRow)
            relationship = info.getRelationshipFor(tableName)
            whereClause = self.buildWhereClause(relationship, parentRow)
        elif whereClause:
            pass
        else:
            whereClause = []
        return self.dbpool.runInteraction(self._rowLoader, tableName,
                                          parentRow, data, whereClause,
                                          forceChildren)

    def _rowLoader(self, transaction, tableName, parentRow, data,
                   whereClause, forceChildren):
        """immediate loading of rowobjects from the table with the whereClause.
        """
        tableInfo = self.schema[tableName]
        # Build the SQL for the query
        sql = "SELECT "
        first = 1
        for column, type in tableInfo.rowColumns:
            if first:
                first = 0
            else:
                sql = sql + ","
            sql = sql + " %s" % column
        sql = sql + " FROM %s " % (tableName)
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
                quotedValue = self.quote_value(value, t)
                sql += "%s %s %s" % (columnName, self.conditionalLabels[cond],
                                     quotedValue)

        # execute the query
        transaction.execute(sql)
        rows = transaction.fetchall()

        # construct the row objects
        results = []
        newRows = []
        for args in rows:
            kw = {}
            for i in range(0,len(args)):
                ColumnName = tableInfo.rowColumns[i][0].lower()
                for attr, type in tableInfo.rowClass.rowColumns:
                    if attr.lower() == ColumnName:
                        kw[attr] = args[i]
                        break
            # find the row in the cache or add it
            resultObject = self.findInCache(tableInfo.rowClass, kw)
            if not resultObject:
                meth = tableInfo.rowFactoryMethod[0]
                resultObject = meth(tableInfo.rowClass, data, kw)
                self.addToCache(resultObject)
                newRows.append(resultObject)
            results.append(resultObject)

        # add these rows to the parentRow if required
        if parentRow:
            self.addToParent(parentRow, newRows, tableName)

        # load children or each of these rows if required
        for relationship in tableInfo.relationships:
            if not forceChildren and not relationship.autoLoad:
                continue
            for row in results:
                # build where clause
                childWhereClause = self.buildWhereClause(relationship, row)
                # load the children immediately, but do nothing with them
                self._rowLoader(transaction,
                                relationship.childRowClass.rowTableName,
                                row, data, childWhereClause, forceChildren)

        return results

    def findTypeFor(self, tableName, columnName):
        tableInfo = self.schema[tableName]
        columnName = columnName.lower()
        for column, type in tableInfo.rowColumns:
            if column.lower() == columnName:
                return type

    def buildUpdateSQL(self, tableInfo):
        """(Internal) Build SQL template to update a RowObject.

        Returns: SQL that is used to contruct a rowObject class.
        """
        sql = "UPDATE %s SET" % tableInfo.rowTableName
        # build update attributes
        first = 1
        for column, type in tableInfo.rowColumns:
            if getKeyColumn(tableInfo.rowClass, column):
                continue
            if not first:
                sql = sql + ", "
            sql = sql + " %s = %s" % (column, "%s")
            first = 0

        # build where clause
        first = 1
        sql = sql + " WHERE "
        for keyColumn, type in tableInfo.rowKeyColumns:
            if not first:
                sql = sql + " AND "
            sql = sql + " %s = %s " % (keyColumn, "%s")
            first = 0
        return sql

    def buildInsertSQL(self, tableInfo):
        """(Internal) Build SQL template to insert a new row.

        Returns: SQL that is used to insert a new row for a rowObject
        instance not created from the database.
        """
        sql = "INSERT INTO %s (" % tableInfo.rowTableName
        # build column list
        first = 1
        for column, type in tableInfo.rowColumns:
            if not first:
                sql = sql + ", "
            sql = sql + column
            first = 0

        sql = sql + " ) VALUES ("

        # build values list
        first = 1
        for column, type in tableInfo.rowColumns:
            if not first:
                sql = sql + ", "
            sql = sql + "%s"
            first = 0

        sql = sql + ")"
        return sql

    def buildDeleteSQL(self, tableInfo):
        """Build the SQL template to delete a row from the table.
        """
        sql = "DELETE FROM %s " % tableInfo.rowTableName
        # build where clause
        first = 1
        sql = sql + " WHERE "
        for keyColumn, type in tableInfo.rowKeyColumns:
            if not first:
                sql = sql + " AND "
            sql = sql + " %s = %s " % (keyColumn, "%s")
            first = 0
        return sql

    def updateRowSQL(self, rowObject):
        """Build SQL to update the contents of rowObject.
        """
        args = []
        tableInfo = self.schema[rowObject.rowTableName]
        # build update attributes
        for column, type in tableInfo.rowColumns:
            if not getKeyColumn(rowObject.__class__, column):
                args.append(self.quote_value(rowObject.findAttribute(column),
                                             type))
        # build where clause
        for keyColumn, type in tableInfo.rowKeyColumns:
            args.append(self.quote_value(rowObject.findAttribute(keyColumn),
                                         type))

        return self.getTableInfo(rowObject).updateSQL % tuple(args)

    def updateRow(self, rowObject):
        """Update the contents of rowObject to the database.
        """
        sql = self.updateRowSQL(rowObject)
        rowObject.setDirty(0)
        return self.dbpool.runOperation(sql)

    def insertRowSQL(self, rowObject):
        """Build SQL to insert the contents of rowObject.
        """
        args = []
        tableInfo = self.schema[rowObject.rowTableName]        
        # build values
        for column, type in tableInfo.rowColumns:
            args.append(self.quote_value(rowObject.findAttribute(column),type))
        return self.getTableInfo(rowObject).insertSQL % tuple(args)

    def insertRow(self, rowObject):
        """Insert a new row for rowObject.
        """
        rowObject.setDirty(0)
        sql = self.insertRowSQL(rowObject)
        return self.dbpool.runOperation(sql)

    def deleteRowSQL(self, rowObject):
        """Build SQL to delete rowObject from the database.
        """
        args = []
        tableInfo = self.schema[rowObject.rowTableName]        
        # build where clause
        for keyColumn, type in tableInfo.rowKeyColumns:
            args.append(self.quote_value(rowObject.findAttribute(keyColumn),
                                         type))

        return self.getTableInfo(rowObject).deleteSQL % tuple(args)

    def deleteRow(self, rowObject):
        """Delete the row for rowObject from the database.
        """
        sql = self.deleteRowSQL(rowObject)
        self.removeFromCache(rowObject)
        return self.dbpool.runOperation(sql)


__all__ = ['SQLReflector']
