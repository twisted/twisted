
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

# System Imports
from pyunit import unittest
import cPickle
import cStringIO

# Twisted Imports
from twisted.persisted import styles, marmalade


class VersionTestCase(unittest.TestCase):
    def testNullVersionUpgrade(self):
        global NullVersioned
        class NullVersioned:
            ok = 0
        pkcl = cPickle.dumps(NullVersioned())
        class NullVersioned(styles.Versioned):
            def upgradeToVersion1(self):
                self.ok = 1
        mnv = cPickle.loads(pkcl)
        styles.doUpgrade()
        assert mnv.ok, "initial upgrade not run!"

    def testVersionUpgrade(self):
        global MyVersioned
        class MyVersioned(styles.Versioned):
            persistenceVersion = 2
            v3 = 0
            v4 = 0

            def __init__(self):
                self.somedata = 'xxx'

            def upgradeToVersion3(self):
                self.v3 = self.v3 + 1

            def upgradeToVersion4(self):
                self.v4 = self.v4 + 1
        mv = MyVersioned()
        assert not (mv.v3 or mv.v4), "hasn't been upgraded yet"
        pickl = cPickle.dumps(mv)
        MyVersioned.persistenceVersion = 4
        obj = cPickle.loads(pickl)
        styles.doUpgrade()
        assert obj.v3, "didn't do version 3 upgrade"
        assert obj.v4, "didn't do version 4 upgrade"
        pickl = cPickle.dumps(obj)
        obj = cPickle.loads(pickl)
        styles.doUpgrade()
        assert obj.v3 == 1, "upgraded unnecessarily"
        assert obj.v4 == 1, "upgraded unnecessarily"


class MyEphemeral(styles.Ephemeral):

    def __init__(self, x):
        self.x = x


class EphemeralTestCase(unittest.TestCase):

    def testEphemeral(self):
        o = MyEphemeral(3)
        self.assertEquals(o.__class__, MyEphemeral)
        self.assertEquals(o.x, 3)
        
        pickl = cPickle.dumps(o)
        o = cPickle.loads(pickl)
        
        self.assertEquals(o.__class__, styles.Ephemeral)
        self.assert_(not hasattr(o, 'x'))


class Pickleable:

    def __init__(self, x):
        self.x = x
    
    def getX(self):
        return self.x

class A:
    """
    dummy class
    """
    def amethod(self):
        pass

class B:
    """
    dummy class
    """
    def bmethod(self):
        pass




def funktion():
    pass

class MarmaladeTestCase(unittest.TestCase):
    def testMethodSelfIdentity(self):
        a = A()
        b = B()
        a.bmethod = b.bmethod
        b.a = a
        im_ = marmalade.unjellyFromXML(marmalade.jellyToXML(b)).a.bmethod
        self.assertEquals(im_.im_class, im_.im_self.__class__)

    def testBasicIdentity(self):
        # Anyone wanting to make this datastructure more complex, and thus this
        # test more comprehensive, is welcome to do so.
        dj = marmalade.DOMJellier().jellyToNode
        d = {'hello': 'world', "method": dj}
        l = [1, 2, 3,
             "he\tllo\n\n\"x world!",
             u"goodbye \n\t\u1010 world!",
             1, 1.0, 100 ** 100l, unittest, marmalade.DOMJellier, d,
             funktion
             ]
        t = tuple(l)
        l.append(l)
        l.append(t)
        l.append(t)
        uj = marmalade.unjellyFromXML(marmalade.jellyToXML([l, l]))
        assert uj[0] is uj[1]
        assert uj[1][0:5] == l[0:5]

class PicklingTestCase(unittest.TestCase):
    """Test pickling of extra object types."""
    
    def testModule(self):
        pickl = cPickle.dumps(styles)
        o = cPickle.loads(pickl)
        self.assertEquals(o, styles)
    
    def testClassMethod(self):
        pickl = cPickle.dumps(Pickleable.getX)
        o = cPickle.loads(pickl)
        self.assertEquals(o, Pickleable.getX)
    
    def testInstanceMethod(self):
        obj = Pickleable(4)
        pickl = cPickle.dumps(obj.getX)
        o = cPickle.loads(pickl)
        self.assertEquals(o(), 4)
        self.assertEquals(type(o), type(obj.getX))
    
    def testcStringIO(self):
        f = cStringIO.StringIO()
        f.write("abc")
        pickl = cPickle.dumps(f)
        o = cPickle.loads(pickl)
        self.assertEquals(type(o), type(f))
        self.assertEquals(f.getvalue(), "abc")


testCases = [VersionTestCase, EphemeralTestCase, PicklingTestCase]

