# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2003 Matthew W. Lefkowitz
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
from twisted.trial import unittest
from twisted.application import service
from twisted.persisted import sob
from twisted.python import components
import copy

class TestService(unittest.TestCase):

    def testName(self):
        s = service.Service()
        s.setName("hello")
        self.failUnlessEqual(s.name, "hello")

    def testParent(self):
        s = service.Service()
        p = service.MultiService()
        s.setServiceParent(p)
        self.failUnlessEqual(list(p), [s])
        self.failUnlessEqual(s.parent, p)

    def testNamedChild(self):
        s = service.Service()
        p = service.MultiService()
        s.setName("hello")
        s.setServiceParent(p)
        self.failUnlessEqual(list(p), [s])
        self.failUnlessEqual(s.parent, p)
        self.failUnlessEqual(p.getServiceNamed("hello"), s)

    def testDoublyNamedChild(self):
        s = service.Service()
        p = service.MultiService()
        s.setName("hello")
        s.setServiceParent(p)
        self.failUnlessRaises(RuntimeError, s.setName, "lala")

    def testDuplicateNamedChild(self):
        s = service.Service()
        p = service.MultiService()
        s.setName("hello")
        s.setServiceParent(p)
        s = service.Service()
        s.setName("hello")
        self.failUnlessRaises(RuntimeError, s.setServiceParent, p)

    def testDisowning(self):
        s = service.Service()
        p = service.MultiService()
        s.setServiceParent(p)
        self.failUnlessEqual(list(p), [s])
        self.failUnlessEqual(s.parent, p)
        s.disownServiceParent()
        self.failUnlessEqual(list(p), [])
        self.failUnlessEqual(s.parent, None)

    def testRunning(self):
        s = service.Service()
        self.assert_(not s.running)
        s.startService()
        self.assert_(s.running)
        s.stopService()
        self.assert_(not s.running)

    def testRunningChildren(self):
        s = service.Service()
        p = service.MultiService()
        s.setServiceParent(p)
        self.assert_(not s.running)
        self.assert_(not p.running)
        p.startService()
        self.assert_(s.running)
        self.assert_(p.running)
        p.stopService()
        self.assert_(not s.running)
        self.assert_(not p.running)

    def testAddingIntoRunning(self):
        p = service.MultiService()
        p.startService()
        s = service.Service()
        self.assert_(not s.running)
        s.setServiceParent(p)
        self.assert_(s.running)
        s.disownServiceParent()
        self.assert_(not s.running)

    def testPrivileged(self):
        s = service.Service()
        def pss():
            s.privilegedStarted = 1
        s.privilegedStartService = pss
        s1 = service.Service()
        p = service.MultiService()
        s.setServiceParent(p)
        s1.setServiceParent(p)
        p.privilegedStartService()
        self.assert_(s.privilegedStarted)

    def testCopying(self):
        s = service.Service()
        s.startService()
        s1 = copy.copy(s)
        self.assert_(not s1.running)
        self.assert_(s.running)
 
        
class TestProcess(unittest.TestCase):

    def testID(self):
        p = service.Process(5, 6)
        self.assertEqual(p.uid, 5)
        self.assertEqual(p.gid, 6)

    def testDefaults(self):
        p = service.Process(5)
        self.assertEqual(p.uid, 5)
        self.assertEqual(p.gid, 0)
        p = service.Process(gid=5)
        self.assertEqual(p.uid, 0)
        self.assertEqual(p.gid, 5)
        p = service.Process()
        self.assertEqual(p.uid, 0)
        self.assertEqual(p.gid, 0)

    def testProcessName(self):
        p = service.Process()
        self.assertEqual(p.processName, None)
        p.processName = 'hello'
        self.assertEqual(p.processName, 'hello')


class TestInterfaces(unittest.TestCase):

    def testService(self):
        self.assert_(components.implements(service.Service(),
                                           service.IService))

    def testMultiService(self):
        self.assert_(components.implements(service.MultiService(),
                                           service.IService))
        self.assert_(components.implements(service.MultiService(),
                                           service.IServiceCollection))

    def testProcess(self):
        self.assert_(components.implements(service.Process(),
                                           service.IProcess))


class TestApplication(unittest.TestCase):

    def testConstructor(self):
        service.Application("hello")
        service.Application("hello", 5)
        service.Application("hello", 5, 6)

    def testProcessComponent(self):
        a = service.Application("hello")
        self.assertEqual(service.IProcess(a).uid, 0)
        self.assertEqual(service.IProcess(a).gid, 0)
        a = service.Application("hello", 5)
        self.assertEqual(service.IProcess(a).uid, 5)
        self.assertEqual(service.IProcess(a).gid, 0)
        a = service.Application("hello", 5, 6)
        self.assertEqual(service.IProcess(a).uid, 5)
        self.assertEqual(service.IProcess(a).gid, 6)

    def testServiceComponent(self):
        a = service.Application("hello")
        self.assert_(service.IService(a) is service.IServiceCollection(a))
        self.assertEqual(service.IService(a).name, "hello")
        self.assertEqual(service.IService(a).parent, None)

    def testPersistableComponent(self):
        a = service.Application("hello")
        p = sob.IPersistable(a)
        self.assertEqual(p.style, 'pickle')
        self.assertEqual(p.name, 'hello')
        self.assert_(p.original is a)
