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

    | CREATE TABLE journalinfo
    | (
    |   commandIndex int
    | );
    | INSERT INTO journalinfo VALUES (0);

"""

from __future__ import nested_scopes

# twisted imports
from twisted.enterprise import row, adbapi
from twisted.internet import defer

# sibling imports
import base


# constants for command list
INSERT, DELETE, UPDATE = range(3)


class RowJournal(base.Journal):
    """Journal that stores data 'snapshot' in using twisted.enterprise.row.

    Use this as the reflector instead of the original reflector.

    It may block on creation, if it has to run recovery.
    """

    def __init__(self, log, journaledService, reflector):
        self.reflector = reflector
        self.commands = []
        self.syncing = 0
        base.Journal.__init__(self, log, journaledService)
    
    def updateRow(self, obj):
        """Mark on object for updating when sync()ing."""
        self.commands.append((UPDATE, obj))

    def insertRow(self, obj):
        """Mark on object for inserting when sync()ing."""
        self.commands.append((INSERT, obj))

    def deleteRow(self, obj):
        """Mark on object for deleting when sync()ing."""
        self.commands.append((DELETE, obj))

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
        comandMap = {INSERT : self.reflector.insertRowSQL,
                     UPDATE : self.reflector.updateRowSQL,
                     DELETE : self.reflector.deleteRowSQL}
        sqlCommands = []
        for kind, obj in self.commands:
            sqlCommands.append(comandMap[kind](obj))
        self.commands = []
        if sqlCommands:
            self.syncing = 1
            d = self.reflector.dbpool.runInteraction(self._sync, self.latestIndex, sqlCommands)
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
