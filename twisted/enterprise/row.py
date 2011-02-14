# -*- test-case-name: twisted.test.test_reflector -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
DEPRECATED.

A (R)elational (O)bject (W)rapper.

This is an extremely thin wrapper.

Maintainer: Dave Peticolas
"""

import warnings

from twisted.enterprise.util import DBError, NOQUOTE, getKeyColumn, dbTypeMap


class RowObject:
    """
    I represent a row in a table in a relational database.

    My class is "populated" by a Reflector object. After I am
    populated, instances of me are able to interact with a particular
    database table.

    You should use a class derived from this class for each database
    table.

    reflector.loadObjectsFrom() is used to create sets of
    instance of objects of this class from database tables.

    Once created, the "key column" attributes cannot be changed.


    Class Attributes that users must supply::

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

    def __init__(self):
        """
        DEPRECATED.
        """
        warnings.warn("twisted.enterprise.row is deprecated since Twisted 8.0",
                      category=DeprecationWarning, stacklevel=2)

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
            if attr.lower() == attrName.lower():
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
                if column.lower(column) == attr.lower():
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


__all__ = ['RowObject']
