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

Maintainer: U{Dave Peticolas<mailto:davep@twistedmatrix.com>}
"""

import string
import warnings

from twisted.enterprise.util import DBError, NOQUOTE, getKeyColumn, dbTypeMap

class RowObject:
    """I represent a row in a table in a relational database.

    My class is "populated" by a Reflector object. After I am
    populated, instances of me are able to interact with a particular
    database table.

    You should use a class derived from this class for each database
    table.

    reflector.loadObjectsFrom() is used to create sets of
    instance of objects of this class from database tables.

    Once created, the "key column" attributes cannot be changed.


    Class Attributes that users must supply:

       rowKeyColumns     # list of key columns in form: [(columnName, typeName)]
       rowTableName      # name of database table
       rowColumns        # list of the columns in the table with the correct
                         # case.this will be used to create member variables.
       rowFactoryMethod  # method to create an instance of this class.
                         # HACK: must be in a list!!! [factoryMethod] (optional)
       rowForeignKeys    # keys to other tables (optional)
                        
    """

    populated = 0    # set on the class when the class is "populated" with SQL
    dirty = 0        # set on an instance when the instance is out-of-sync with the database

    def assignKeyAttr(self, attrName, value):
        """Assign to a key attribute.

        This cannot be done through normal means to protect changing
        keys of db objects.
        """
        found = 0
        for keyColumn, type in self.rowKeyColumns:
            if keyColumn == attrName:
                found = 1
        if not found:
            raise DBError("%s is not a key columns." % attrName)
        self.__dict__[attrName] = value

    def findAttribute(self, attrName):
        """Find an attribute by caseless name.
        """
        for attr, type in self.rowColumns:
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

    def getKeyTuple(self):
        keys = []
        keys.append(self.rowTableName)
        for keyName, keyType in self.rowKeyColumns:
            keys.append( getattr(self, keyName) )
        return tuple(keys)
        

class KeyFactory:
    """I create unique keys to use as primary key columns in database tables.
    I am able to use a specified range. I am deprecated, don't use me.
    (NOTE: not thread safe....)
    """
    def __init__(self, minimum, pool):
        warnings.warn("This is deprecated. Use the underlying database to generate keys, or just roll your own.", DeprecationWarning)
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
    """I keep a set of SQL statements to be executed in a single batch. But I am deprecated so don't use me.
    """
    def __init__(self):
        warnings.warn("This is deprecated. Just use ';'.join(statements)", DeprecationWarning)
        self.statements = []

    def addStatement(self, statement):
        self.statements.append(statement)

    def batchSQL(self):
        batchSQL =  string.join(self.statements,";\n")
        self.statements = []
        return batchSQL

    def getSize(self):
        return len(self.statements)
