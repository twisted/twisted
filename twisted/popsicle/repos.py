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
# -*- test-case-name: twisted.test.test_popsicle -*-


"""Abstract Repository classes for Popsicle.
"""

# System Imports
import os
import weakref

# Twisted Imports
from twisted.internet import defer
from twisted.persisted.styles import instance

# Sibling Imports
from twisted.popsicle.freezer import theFreezer, ISaver, PersistentReference, ref

class Repository:
    """A data storage that can be loaded from.  A repository of objects.

    I am an abstract class.  Subclass me and implement 'loadOID' and 'saveOID'

    Note that 'Repository' implementations are really open-ended.  This
    implementation strategy is suggested, though, and it is strongly suggested
    that authors of new repositories implement at least the caching shown here.

    However, facilities such as ad-hoc querying are omitted from this
    interface, and should be provided by e.g. an SQL Repository implementation.

    A repository is both a saver and a collection of PersistentReferences.
    """

    __implements__ = ISaver

    _lastOID = 0

    def saveOID(self, oid, obj):
        """
        Return a Deferred which will fire True when the object is saved.
        """
        raise NotImplementedError()


    def __init__(self):
        """Initialize me (set up cache).
        """
        self._cache = weakref.WeakValueDictionary()
        self._revCache = weakref.WeakKeyDictionary()
        self._pRefs = weakref.WeakValueDictionary()

    def load(self, oid):
        """Load an object from cache or by OID. Return a Deferred.

        This method should be called by external objects looking for a
        'starting point' into the repository.
        """
        oid = str(oid)
        if self._pRefs.has_key(oid):
            pRef = self._pRefs[oid]
        else:
            pRef = PersistentReference(str(oid), self, None)
        return pRef()

    def loadNow(self, oid):
        """External API for synchronously loading stuff.

        This should ONLY BE USED by code that is doing the actual
        loading/saving of structured objects.  Application code should always
        make calls through PersistentReference.__call__, otherwise it will not
        work on some back-ends.
        """
        oid = str(oid)
        if self._cache.get(oid):
            return self._cache[oid]
        # this code is copied and subtly changed from _cbLoadedOID.  I wish I
        # could have found a better way to do it, but -- expect bugs here!
        pRef = PersistentReference(oid, self, None)
        pRef.deferred = defer.Deferred()
        try:
            try:
                obj = self.loadOIDNow(oid)
            except:
                pRef.deferred.errback()
                raise
            else:
                theFreezer.setPersistentReference(obj, pRef)
                theFreezer.addSaver(obj, self)
                pRef.deferred.callback(obj)
                self.cache(oid, obj)
                return obj
        finally:
            del pRef.deferred

    def loadOIDNow(self, oid):
        """
        Implement me if you want to implement synchronous loading.
        """
        raise NotImplementedError()

    def loadOID(self, oid):
        """Implement me to return a Deferred if you want to implement asynchronous loading.
        """
        return defer.execute(self.loadOIDNow, oid)

    def createOID(self, oid, klass):
        """Create an instance with an oid and cache it.  This is useful during loading.
        """
        i = instance(klass)
        self.cache(oid, i, 0)
        return i

    def loadRef(self, pRef):
        """
        Synonymous with ref.__call__().
        """
        oid = pRef.oid
        obj = self._cache.get(oid)
        if obj is not None:
            return defer.succeed(obj)
        elif self._pRefs.has_key(oid):
            # have a persistent ref, but no object
            return pRef.deferred
        else:
            # have no persistent ref
            d = defer.Deferred()
            self._pRefs[oid] = pRef
            pRef.deferred = d
            d2 = self.loadOID(oid)
            d2.addCallback(self._cbLoadedOID, oid, pRef)
            return d


    def _cbLoadedOID(self, result, oid, pref):
        theFreezer.setPersistentReference(result, pref)
        theFreezer.addSaver(result, self)
        self.cache(oid, result)
        pref.deferred.callback(result)
        del pref.deferred
        return result


    def generateOID(self, obj):
        """Generate an OID synchronously.

        Necessary for some types of persistence, but 
        """
        self._lastOID += 1
        return self._lastOID

    def cache(self, oid, obj, finished=1):
        """Weakly cache an object for the given OID.

        This means I own it, so also register it with the Freezer as such.
        """
        self._cache[oid] = obj
        self._revCache[obj] = oid

    def getOID(self, obj):
        if self._revCache.has_key(obj):
            return self._revCache[obj]
        else:
            # TODO: if OID generation really needs to be async...
            return ref(obj).acquireOID(self)

    def save(self, obj):
        """
        Save an object...

        If this is the first time I am saving this particular object, I need to
        locate a new unique ID for it.
        """
        theFreezer._savingRepo = self
        try:
            oid = self.getOID(obj)
            val = self.saveOID(oid, obj)
            self.cache(oid, obj)
            return val
        finally:
            theFreezer._savingRepo = None


class DirectoryRepository(Repository):
    def __init__(self, dirname):
        if not os.path.isdir(dirname):
            os.mkdir(dirname)
            fn = os.path.join(dirname,".popsiqnum")
        Repository.__init__(self)
        self.dirname = dirname

    def generateOID(self, obj):
        fn = os.path.join(self.dirname,".popsiqnum")
        try:
            seq = str(int(open(fn).read()) + 1)
        except IOError:
            seq = '0'
        open(fn,'w').write(seq)
        return seq

