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

from twisted.internet import defer

import os
import weakref

from twisted.python import log

from twisted.persisted.styles import instance, instancemethod

try:
    True, False
except NameError:
    True, False = 1, 0

class Freezer:
    DELETE = 0
    SAVE = 1
    def __init__(self):
        self.persistentObjects = weakref.WeakKeyDictionary()
        self.dirtySet = {}
        self.cleaning = False
        self.pendingCall = None

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
        from twisted.internet import reactor
        if not self.pendingCall:
            self.pendingCall = reactor.callLater(1.0, self.clean)

    def _dirty(self, obj, dirt=SAVE):
        self.dirtySet[obj] = dirt

    def register(self, obj, repo):
        pr = self.getPersistentReference(obj, repo)
        self.dirty(obj)
        return pr

    def delete(self, obj):
        return self.dirty(obj, Freezer.DELETE)

    def _cleanTime(self):
        self.pendingCall = None
        self.clean()

    def clean(self):
        """Persistence tick.  Clean out the fridge, persist everything that
        wants to be saved.
        """
        #log.msg("cleaning popsicle")
        if self.pendingCall:
            self.pendingCall.cancel()
            self.pendingCall = None
        self.cleaning = True
        savers = {}
        try:
            while self.dirtySet:
                l = self.dirtySet.items()
                self.dirtySet.clear()
                for obj, doSave in l:
                    ent = self.persistentObjects.get(obj)
                    if not ent:
                        continue
                    for saver in ent[1]:
                        savers[saver] = 1
                        try:
                            if doSave:
                                # print 'saving',obj
                                saver.save(obj)
                            else:
                                # print 'deleting',obj
                                saver.delete(obj)
                        except:
                            # TODO: more error handling: backout transactions?
                            # restore state of objects?  what else?
                            log.deferr()
        finally:
            self.cleaning = False
            for saver in savers.keys():
                try:
                    saver.cleaned()
                except:
                    log.deferr()
            

try:
    theFreezer
except NameError:
    # Create the public interface singleton.
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


class PersistentReference:
    """I am a reference to a persistent object.

    The most interesting external interface is __call__: instances of this
    class should generally be treated as zero-argument functions which return
    Deferreds.
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
        """Load my object into memory, and return a Deferred which will fire
        it."""
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
            repo.cache(self.oid, o, finished=0)
            return self.oid
        elif ((self.repo is repo) or
              repo is None and self.repo is theFreezer._savingRepo):
            assert self.oid is not None, "inconsistent state of p-ref"
            return self.oid
        else:
            # I don't belong to this repo, but I _do_ belong to someone else.
            return None
        ### assert False, "wrong repository!"
