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


class Entity:
    """Default class for database objects. Knows how to save itself back to the db.
    Should use a class derived from this class for each database table. Objects of these
    classes are constructed by the object loader.
    """
    columns = []     # list of column names and types for the table I came from
    keyColumns = []  # list of key columns to identify instances in the db
    tableName = ""
    updateSQL = ""
    insertSQL = ""
    deleteSQL = ""
    
    def updateEntity(self):
        """update my contents to the database.
        """
        args = []
        
        # build update attributes
        for column, type, typeid in self.columns:
            found = 0
            # be sure not to update key columns            
            for keyColumn, type in self.keyColumns:
                if column == keyColumn:
                    found = 1
            if found:
                continue
            args.append(self.__dict__[column])
            
        # build where clause
        for keyColumn, type in self.keyColumns:
            args.append( self.__dict__[keyColumn])

        sql = self.updateSQL % tuple(args)
        return self.augmentation.runOperation(sql)

    def insertEntity(self):
        """insert a new row for this object instance.
        """
        args = []

        # build values
        for column, type, typeid in self.columns:
            args.append(self.__dict__[column])

        sql = self.insertSQL % tuple(args)
        return self.augmentation.runOperation(sql)

    def deleteEntity(self):
        """delete the row for this object from the database.
        """
        args = []

        # build where clause
        for keyColumn, type in self.keyColumns:
            args.append( self.__dict__[keyColumn])

        sql = self.deleteSQL % tuple(args)
        return self.augmentation.runOperation(sql)


def buildEntityClass(aug, entityClass, tableName, columns, keyColumns):
    """construct all the SQL for database operations on <tableName> and
    populate the class <entityClass> with that info.
    """

    if entityClass.tableName and entityClass.tableName != tableName:
        raise ("ERROR: class %s has already had SQL generated for table %s." % (repr(entityClass), tableName) )
    
    entityClass.tableName = tableName
    entityClass.columns = columns
    entityClass.keyColumns = keyColumns
    entityClass.augmentation = aug

    entityClass.updateSQL = buildUpdateSQL(tableName, columns, keyColumns)
    entityClass.insertSQL = buildInsertSQL(tableName, columns)
    entityClass.deleteSQL = buildDeleteSQL(tableName, keyColumns)


def buildUpdateSQL(tableName, columns, keyColumns):
    """build the SQL to update objects of <entityClass> to the database. This 
    populates the class attributes used when doing updates.
    """
    sql = "UPDATE %s SET" % tableName
    # build update attributes
    first = 1        
    for column, type, typeid in columns:
        found = 0
        # be sure not to update key columns
        for keyColumn, ktype in keyColumns:
            #print "column", column, keyColumn
            if column == keyColumn:
                found = 1
        if found:
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

