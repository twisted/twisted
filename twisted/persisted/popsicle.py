# -*- test-case-name: twisted.test.test_popsicle -*-
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

# 

"""
POPSICLE: 

Persistent Object Partitioning Strategy Involving Concurrent Lightweight Events

GOAL: popsicle is designed to persist objects as close to transparently as
possible.  While complete transparency is impossible with python's semantics,
popsicle strives to preserve three things:

    1. preserve a modicum of referential transparency by using Deferreds for
    all references which cannot be immediately resolved

    2. allow for the use of multiple persistence strategies with the same
    object (e.g.: using ZODB, using a relational database, etc

    3. minimize memory usage by paging unnecessary objects out whenever
    possible, transparently to everything involved (e.g. using Python's normal
    garbage collection mechanisms)


There is a top level persistence manager (the 'freezer') which keeps a weak key
dictionary of {persistent_object: [PersistentReference, [savers]]}

The persistent_object should be 'trained' to expect callable objects that
return Deferreds to populate part of it.  Whenever a persistence mechanism
encounters an ID for a different object that could be loaded...

Each Storage is responsible for its own cache management wrt IDs.

Objects that are dirty should call popsicle.dirty(self) to be added to the
dirty list.  when popsicle.clean() is called, the dirty list will be walked,
notifying all savers for each dirty object.

This module requires Python 2.1, among other things for weak references.

"""

from twisted.internet import defer

import os
import weakref

try:
    from new import instance
    from new import instancemethod
except:
    from org.python.core import PyMethod
    instancemethod = PyMethod

class Freezer:
    DELETE = 0
    SAVE = 1
    def __init__(self):
        self.persistentObjects = weakref.WeakKeyDictionary()
        self.dirtySet = {}
        self.cleaning = False

    def addSaver(self, obj, saver):
        """Add an interested saver to a particular object.
        """
        ent = self.persistentObjects.get(obj)
        if not ent:
            ent = [None, []]
            self.persistentObjects[obj] = ent
        ent[1].append(saver)

    def removeSaver(self, obj, saver):
        ent = self.persistentObjects.get(obj)
        if not ent:
            return
        ent[1].remove(saver)

    def setPersistentReference(self, obj, pref):
        ent = self.persistentObjects.get(obj)
        if not ent:
            ent = [pref, []]
            self.persistentObjects[obj] = ent
        else:
            ent[0] = pref

    def getPersistentReference(self, obj, repo=None):
        ent = self.persistentObjects.get(obj)
        if not ent:
            pr = PersistentReference(None, None, obj)
            self.setPersistentReference(obj, pr)
            ent = self.persistentObjects[obj]
            if repo is not None:
                pr.acquireOID(repo)
        return ent[0]

    def dirty(self, obj, dirt=SAVE):
        if self.cleaning:
            raise RuntimeError("Can't flag an object as dirty while cleaning.")
        self._dirty(obj)

    def _dirty(self, obj, dirt=SAVE):
        self.dirtySet[obj] = dirt

    def register(self, obj, repo):
        self.getPersistentReference(obj, repo)
        self.dirty(obj)

    def delete(self, obj):
        return self.dirty(obj, Freezer.DELETE)

    def clean(self):
        """Persistence tick.  Clean out the fridge, persist everything that
        wants to be saved.
        """
        self.cleaning = True
        try:
            while self.dirtySet:
                l = self.dirtySet.items()
                self.dirtySet.clear()
                for obj, doSave in l:
                    ent = self.persistentObjects.get(obj)
                    if not ent:
                        continue
                    for saver in ent[1]:
                        if doSave:
                            # print 'saving',obj
                            saver.save(obj)
                        else:
                            # print 'deleting',obj
                            saver.delete(obj)
        finally:
            self.cleaning = False

theFreezer = Freezer()

ref = theFreezer.getPersistentReference
clean = theFreezer.clean
dirty = theFreezer.dirty
register = theFreezer.register

class ISaver:
    def save(self, object):
        """Save (and optionally index) the given object.
        """

    def delete(self, object):
        """Remove the given object.
        """

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


class PersistentReference:
    """
    I am a reference to persistent objects.
    """

    # Maintenance notes: there are 2 states for instances of this class.
    # either self.oid and self.repo are set to non-None values, in which case
    # this represents a stored object, or self.obj is set, in which case this
    # represents a value that *wants* to be stored.  In state 2, the object is
    # mutable, so care is taken to cache such objects (see
    # Freezer.getPersistentReference).  However, in state 1, prefs are
    # effectively immutable, so multiple may be instantiated with the same
    # OID/repo pair.
    
    def __init__(self, oid, repo, obj):
        self.oid = oid
        self.repo = repo
        self.obj = obj

    def __call__(self):
        if self.obj is not None:
            return defer.succeed(self.obj)
        return self.repo.loadRef(self)

    def acquireOID(self, repo=None):
        """Take a PersistentReference that isn't really persistent yet, and
        associate it with a repository, give it an OID, and set it dirty.
        This should happen *synchronously during persistence*.
        """
        # TODO: better name for this method!!!
        if self.obj is not None:
            assert self.oid is None, "inconsistent state of p-ref: %s" % self.oid
            if repo is None:
                assert theFreezer._savingRepo is not None, "Calling acquireOID without repo outside of save!"
                repo = theFreezer._savingRepo
            o = self.obj
            self.repo = repo
            self.oid = repo.generateOID(o)
            self.obj = None
            theFreezer.addSaver(o, repo)
            # use internal API to avoid warning: we *really really* want to dirty
            theFreezer._dirty(o)
            return self.oid
        elif ((self.repo is repo) or
              repo is None and self.repo is theFreezer._savingRepo):
            assert self.oid is not None, "inconsistent state of p-ref"
            return self.oid
        else:
            # I don't belong to this repo, but I _do_ belong to someone else.
            return None
        ### assert False, "wrong repository!"

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

