# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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
# 

"""Journal using twisted.enterprise.row RDBMS support.

You're going to need the following table in your database::

    | CREATE TABLE loginfo
    | (
    |   latestIndex int
    | );
    | INSERT INTO loginfo VALUES (0);

"""

from __future__ import nested_scopes

# twisted imports
from twisted.enterprise import row, adbapi
from twisted.internet import defer

# sibling imports
import base


class OrderedDict:
    """Store keys in order they were inserted in."""

    def __init__(self):
        self.keys = []
        self.map = {}

    def __setitem__(self, key, value):
        if self.map.has_key(key):
            self.keys[self.map[key]] = value
        else:
            self.keys.append(key)
            self.map[key] = len(self.keys) - 1

    def __delitem__(self, key):
        i = self.map[key]
        del self.keys[i:i+1]
        del self.map[key]

    def has_key(self, key):
        return self.map.has_key(key)

    def keys(self):
        return self.keys


class RowJournal(base.Journal):
    """Journal that stores data 'snapshot' in using twisted.enterprise.row.

    Use this as the reflector instead of the original reflector.

    It may block on creation, if it has to run recovery.
    """

    def __init__(self, log, journaledService, reflector):
        self.reflector = reflector
        self.dirtyRows = OrderedDict()
        self.insertedRows = OrderedDict()
        self.deletedRows = OrderedDict()
        self.syncing = 0
        base.Journal.__init__(self, log, journaledService)
    
    def updateRow(self, obj):
        """Mark on object for updating when sync()ing."""
        if self.insertedRows.has_key(obj):
            self.insertedRows[obj] = 1
        else:
            self.dirtyRows[obj] = 1

    def insertRow(self, obj):
        """Mark on object for inserting when sync()ing."""
        if self.deletedRows.has_key(obj):
            del self.deletedRows[obj]
            self.dirtyRows[obj] = 1
        else:
            self.insertedRows[obj] = 1

    def deleteRow(self, obj):
        """Mark on object for deleting when sync()ing."""
        if self.insertedRows.has_key(obj):
            del self.insertedRows[obj]
            return
        if self.dirtyRows.has_key(obj):
            del self.dirtyRows[obj]
        self.deletedRows[obj] = 1

    def loadObjectsFrom(self, tableName, parentRow=None, data=None, whereClause=None, forceChildren=0):
        """Flush all objects to the database and then load objects."""
        d = self.sync()
        d.addCallback(lambda result: self.reflector.loadObjectsFrom(
            tableName, parentRow=parentRow, data=data, whereClause=whereClause,
            forceChildren=forceChildren))
        return d

    def sync(self):
        """Commit changes to database."""
        if self.syncing:
            raise ValueError, "sync already in progress"
        commands = []
        for i in self.insertedRows.keys():
            commands.append(self.reflector.insertRowSQL(i))
        for i in self.dirtyRows.keys():
            commands.append(self.reflector.updateRowSQL(i))
        for i in self.deletedRows.keys():
            commands.append(self.reflector.deleteRowSQL(i))
        self.insertedRows.clear()
        self.dirtyRows.clear()
        self.deletedRows.clear()
        if commands:
            self.syncing = 1
            d = self.reflector.dbpool.runInteraction(self._sync, self.latestIndex, commands)
            d.addCallback(self._syncDone)
            return d
        else:
            return defer.succeed(1)

    def _sync(self, txn, index, commands):
        """Do the actual database synchronization."""
        for c in commands:
            txn.execute(c)
        txn.update("UPDATE journalinfo SET commandIndex = %d" % index)
    
    def _syncDone(self, result):
        self.syncing = 0
        return result
    
    def getLastSnapshot(self):
        """Return command index of last snapshot."""
        conn = self.reflector.dbpool.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT commandIndex FROM journalinfo")
        return cursor.fetchall()[0][0]
