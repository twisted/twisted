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

"""

This is code and support for 

"""

# System Imports
import os

# Twisted Imports
from twisted.internet import defer

# Sibling Imports
from twisted.popsicle.repos import DirectoryRepository
from twisted.popsicle.freezer import PersistentReference, ref

class Picklesicle(DirectoryRepository):

    """I am a Repository that uses a directory full of Pickles to save
    everything.  This is the most naive implementation possible of a popsicle
    backend, and useful for reference implementors.
    """

    def __init__(self, dirname, persistentClasses):
        DirectoryRepository.__init__(self, dirname)
        self.persistentClasses = persistentClasses

    def persistentLoad(self, pid):
        sa, oid = pid.split(":")
        if sa == "S": # synchronous reference
            return self.loadOID(oid)
        else:
            return PersistentReference(oid, self, None)

    def loadOID(self, oid):
        
        # maintenance note: when implementing future, truly async loadOID
        # methods, it may be useful to keep a dictionary around of
        # previously-loaded OIDs during recursive loads to make sure that we
        # don't send multiple requests to the DB for the same OID in the same
        # actual request.
        
        import cPickle
        f = open(os.path.join(self.dirname, str(oid)))
        up = cPickle.Unpickler(f)
        up.persistent_load = self.persistentLoad
        obj = up.load()
        # cheating...
        from twisted.persisted.styles import doUpgrade
        doUpgrade()
        return defer.succeed(obj)

    def persistentID(self, obj):
        if isinstance(obj, PersistentReference):
            # It's a persistent reference.  Does it belong to me?
            oid = obj.acquireOID(self)
            if oid is None:
                # it doesn't belong to me, so just give it back as a pickled
                # ref so we can have inter-db links (this really only works for
                # flexible DBs... SQL is going to require all refs point to it)
                # *possibly* we really want a warning here?
                return None
            else:
                # It either belongs to me now (I acquired it during acquireOID)
                # or it belonged to me before.
                return "A:"+str(oid)

        for pclas in self.persistentClasses:
            if isinstance(obj, pclas):
                # it's a persistent class
                oid = ref(obj).acquireOID(self)
                assert oid is not None, "Synchronous foreign database reference!"
                if oid != self._savingOID:
                    return "S:"+str(oid)

    def saveOID(self, oid, obj):
        import cPickle
        f = open(os.path.join(self.dirname, str(oid)), 'wb')
        pl = cPickle.Pickler(f)
        self._savingOID = oid
        pl.persistent_id = self.persistentID
        pl.dump(obj)

