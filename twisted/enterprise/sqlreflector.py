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

from twisted.enterprise import adbapi
from twisted.enterprise.util import DBError, getKeyColumn, quote, _TableInfo, _TableRelationship
from twisted.enterprise.row import RowObject

from twisted.enterprise import reflector
from twisted.python import reflect

class SQLReflector(reflector.Reflector, adbapi.Augmentation):
    """I reflect on a database and load RowObjects from it.

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
    
    def __init__(self, dbpool, rowClasses, populatedCallback=None):
        """
        Initialize me against a database.
        """
        adbapi.Augmentation.__init__(self, dbpool)
        reflector.Reflector.__init__(self, rowClasses, populatedCallback)        

    def _really_populate(self):
        self._transPopulateSchema()
        if self.populatedCallback:
            self.populatedCallback(None)

    def _transPopulateSchema(self):
        """Used to construct the row classes in a single interaction.
        """
        for rc in self.rowClasses:
            if not issubclass(rc, RowObject):
                raise DBError("Stub class (%s) is not derived from RowObject" % reflect.qual(rc.rowClass))

            self._populateSchemaFor(rc)
        self.populated = 1

    def _populateSchemaFor(self, rc):
        """construct all the SQL for database operations on <tableName> and
        populate the class <rowClass> with that info.
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
        
    def loadObjectsFrom(self, tableName, parentRow=None, data=None, whereClause=None, forceChildren=0):
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
        return self.runInteraction(self._rowLoader, tableName, parentRow, data, whereClause, forceChildren)

    
    def _rowLoader(self, transaction, tableName, parentRow, data, whereClause, forceChildren):
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

        # execute the query
        transaction.execute(sql)
        rows = transaction.fetchall()

        # construct the row objects
        results = []
        newRows = []
        for args in rows:
            kw = {}
            for i in range(0,len(args)):
                columnName = tableInfo.rowColumns[i][0]
                for attr, type in tableInfo.rowClass.rowColumns:
                    if string.lower(attr) == string.lower(columnName):
                        kw[attr] = args[i]
                        break
            # find the row in the cache or add it
            resultObject = self.findInCache(tableInfo.rowClass, kw)
            if not resultObject:
                resultObject = apply(tableInfo.rowFactoryMethod[0], (tableInfo.rowClass, data, kw) )
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
                self._rowLoader(transaction, relationship.childRowClass.rowTableName, row, data, childWhereClause, forceChildren)

        return results

        
    def findTypeFor(self, tableName, columnName):
        tableInfo = self.schema[tableName]
        for column, type in tableInfo.rowColumns:
            if column.upper() == columnName.upper():
                return type

    def buildUpdateSQL(self, tableInfo):
        """(Internal) Build SQL to update a RowObject.

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
            sql = sql + "  %s = %s" % (column, quote("%s", type))
            first = 0

        # build where clause
        first = 1
        sql = sql + "  WHERE "
        for keyColumn, type in tableInfo.rowKeyColumns:
            if not first:
                sql = sql + " AND "
            sql = sql + "   %s = %s " % (keyColumn, quote("%s", type) )
            first = 0
        return sql

    def buildInsertSQL(self, tableInfo):
        """(Internal) Build SQL to insert a new row.

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
            sql = sql + quote("%s", type)
            first = 0

        sql = sql + ")"
        return sql

    def buildDeleteSQL(self, tableInfo):
        """Build the SQL to delete a row from the table.
        """
        sql = "DELETE FROM %s " % tableInfo.rowTableName
        # build where clause
        first = 1
        sql = sql + "  WHERE "
        for keyColumn, type in tableInfo.rowKeyColumns:
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
        for column, type in tableInfo.rowColumns:
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
        for column, type in tableInfo.rowColumns:
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

