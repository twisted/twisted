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

from pyunit import unittest
from twisted.popsicle import mailsicle, freezer

class Dummy:
    __implements__ = mailsicle.IHeaderSaver

    def __init__(self,name):
        self.name = name

    def __repr__(self):
        return '<dummy %r %r>' % (self.name, id(self))

    def setName(self,name):
        self.name = name
        freezer.dirty(self)

    def getContinuations(self):
        return []

    def getItems(self):
        return [("Name",self.name)]

    def descriptiveName(self):
        return "Dummy %s" % self.name

    def getIndexes(self):
        return [('person-name',self.name)]

    def loadItems(self,items):
        self.name = items[2][1]

    def loadContinuations(self, cont):
        pass


from twisted.python import log
import os
import shutil

from twisted.popsicle import freezer, mailsicle, picklesicle
from twisted.internet import defer


class gcall:
    def __init__(self, m, *a, **k):
        self.m = m
        self.a = a
        self.k = k
    def __del__(self):
        self.m(*self.a,**self.k)

class Friend:
    """
    Simple persistence test.
    """
    def __init__(self, name):
        """Initialize with a name.
        """
        self.name = name
        self.friendRefs = []

    def __repr__(self):
        return "<Friend %r>" % self.name

    def addFriend(self, friend):
        self.friendRefs.append(freezer.ref(friend))

    def _cbPrint(self, l):
        # print "Friends!", l
        pass

    def printFriendList(self):
        # TODO: convert to "walkFriendList" to reduce interactive output
        l = []
        for f in self.friendRefs:
            l.append(f())
        dl = defer.DeferredList(l)
        dl.addCallback(self._cbPrint)


class PicklesicleTest(unittest.TestCase):
    def testPickle(self):
        import gc
        ps = picklesicle.Picklesicle("POPSICLE", [Friend])
        bob = Friend("bob")
        alice = Friend("alice")
        bob.addFriend(alice)
        alice.addFriend(bob)
        bob.printFriendList()
        # ps.save(bob) # doesn't work as you'd expect, sadly :-\
        freezer.ref(bob).acquireOID(ps)
        freezer.dirty(bob)
        freezer.clean()
        l = []
        alice._tracker = gcall(l.append, True)
        del alice
        assert l, "Alice not garbage collected."
        assert len(filter(lambda x: isinstance(x, Friend),
                          gc.get_referrers(Friend))) == 1, (
            "More than one friend alive.")
        bob.printFriendList()



class MailsicleTest(unittest.TestCase):
    def testIndexing(self):
        if os.path.exists("BOBJANE_TEST"):
            shutil.rmtree("BOBJANE_TEST")
        ms = mailsicle.Mailsicle("BOBJANE_TEST")
        d1 = Dummy("bob")
        d2 = Dummy("jane")
        freezer.register(d1, ms)
        freezer.register(d2, ms)
        freezer.clean()
        del d1
        del d2
        yy = []
        zz = []
        yy = ms.queryIndex("person-name","bob").fetchNow()
        zz = ms.queryIndex("person-name","bob").fetchNow()
        yy.sort()
        zz.sort()
        # log.err(yy[0])
        self.assertEquals(yy,zz)
        self.assertEquals(len(yy),1)
        yy[0].setName("joe")
        zz = []
        yy = []
        #print 'cleaning pops'
        #print freezer.theFreezer.persistentObjects.items()
        freezer.clean()
        # print 'cleaned'
        ms.queryIndex("person-name","bob").fetch().addCallback(yy.extend)
        ms.queryIndex("person-name","joe").fetch().addCallback(zz.extend)
        self.assertEquals(yy,[])
        self.assertEquals(len(zz),1)
