
import re
from twisted.trial import unittest

from zope.interface import implements
from twisted.internet import defer
from twisted.application.internet import TCPServer
from twisted.pb import pb, schema
try:
    from twisted.pb import crypto
except ImportError:
    crypto = None
if crypto and not crypto.available:
    crypto = None

class RIMyCryptoTarget(pb.RemoteInterface):
    # method constraints can be declared directly:
    add1 = schema.RemoteMethodSchema(_response=int, a=int, b=int)

    # or through their function definitions:
    def add(a=int, b=int): return int
    #add = schema.callable(add) # the metaclass makes this unnecessary
    # but it could be used for adding options or something
    def join(a=str, b=str, c=int): return str
    def getName(): return str

class Target(pb.Referenceable):
    implements(RIMyCryptoTarget)

    def __init__(self, name=None):
        self.calls = []
        self.name = name
    def getMethodSchema(self, methodname):
        return None
    def remote_add(self, a, b):
        self.calls.append((a,b))
        return a+b
    remote_add1 = remote_add
    def remote_getName(self):
        return self.name
    def remote_disputed(self, a):
        return 24
    def remote_fail(self):
        raise ValueError("you asked me to fail")

class UsefulMixin:
    num_services = 2
    def setUp(self):
        self.services = []
        for i in range(self.num_services):
            s = pb.PBService()
            s.startService()
            self.services.append(s)

    def tearDown(self):
        d = defer.DeferredList([s.stopService() for s in self.services])
        d.addCallback(self._tearDown_1)
        return d
    def _tearDown_1(self, res):
        self.failIf(pb.Listeners)

class TestPersist(UsefulMixin, unittest.TestCase):
    num_services = 2
    def testPersist(self):
        if not crypto:
            raise unittest.SkipTest("crypto not available")
        t1 = Target()
        s1,s2 = self.services
        l1 = s1.listenOn("0")
        port = l1.getPortnum()
        s1.setLocation("localhost:%d" % port)
        public_url = s1.registerReference(t1, "name")
        self.failUnless(public_url.startswith("pb:"))
        d = defer.maybeDeferred(s1.stopService)
        d.addCallback(self._testPersist_1, s1, s2, t1, public_url, port)
        return d
    testPersist.timeout = 5
    def _testPersist_1(self, res, s1, s2, t1, public_url, port):
        self.services.remove(s1)
        s3 = pb.PBService(certData=s1.getCertData())
        s3.startService()
        self.services.append(s3)
        t2 = Target()
        l3 = s3.listenOn("0")
        newport = l3.getPortnum()
        s3.setLocation("localhost:%d" % newport)
        s3.registerReference(t2, "name")
        # now patch the URL to replace the port number
        newurl = re.sub(":%d/" % port, ":%d/" % newport, public_url)
        d = s2.getReference(newurl)
        d.addCallback(lambda rr: rr.callRemote("add", a=1, b=2))
        d.addCallback(self.failUnlessEqual, 3)
        d.addCallback(self._testPersist_2, t1, t2)
        return d
    def _testPersist_2(self, res, t1, t2):
        self.failUnlessEqual(t1.calls, [])
        self.failUnlessEqual(t2.calls, [(1,2)])


class TestListeners(UsefulMixin, unittest.TestCase):
    num_services = 3

    def testListenOn(self):
        s1 = self.services[0]
        l = s1.listenOn("0")
        self.failUnless(isinstance(l, pb.Listener))
        self.failUnlessEqual(len(s1.getListeners()), 1)
        self.failUnlessEqual(len(pb.Listeners), 1)
        s1.stopListeningOn(l)
        self.failUnlessEqual(len(s1.getListeners()), 0)
        self.failUnlessEqual(len(pb.Listeners), 0)


    def testGetPort1(self):
        s1,s2,s3 = self.services
        s1.listenOn("0")
        listeners = s1.getListeners()
        self.failUnlessEqual(len(listeners), 1)
        portnum = listeners[0].getPortnum()
        self.failUnless(portnum) # not 0, not None, must be *something*

    def testGetPort2(self):
        if not crypto:
            raise unittest.SkipTest("crypto not available, shared ports "
                                    "require TubIDs and thus crypto")
        s1,s2,s3 = self.services
        s1.listenOn("0")
        listeners = s1.getListeners()
        self.failUnlessEqual(len(listeners), 1)
        portnum = listeners[0].getPortnum()
        self.failUnless(portnum) # not 0, not None, must be *something*
        s1.listenOn("0") # listen on a second port too
        l2 = s1.getListeners()
        self.failUnlessEqual(len(l2), 2)
        self.failIfEqual(l2[0].getPortnum(), l2[1].getPortnum())

        s2.listenOn(l2[0])
        l3 = s2.getListeners()
        self.failUnlessIdentical(l2[0], l3[0])
        self.failUnlessEqual(l2[0].getPortnum(), l3[0].getPortnum())

    def testShared(self):
        if not crypto:
            raise unittest.SkipTest("crypto not available, shared ports "
                                    "require TubIDs and thus crypto")
        s1,s2,s3 = self.services
        # s1 and s2 will share a Listener
        l1 = s1.listenOn("tcp:0:interface=127.0.0.1")
        s1.setLocation("localhost:%d" % l1.getPortnum())
        s2.listenOn(l1)
        s2.setLocation("localhost:%d" % l1.getPortnum())

        t1 = Target("one")
        t2 = Target("two")
        self.targets = [t1,t2]
        url1 = s1.registerReference(t1, "target")
        url2 = s2.registerReference(t2, "target")
        self.urls = [url1, url2]

        d = s3.getReference(url1)
        d.addCallback(lambda ref: ref.callRemote('add', a=1, b=1))
        d.addCallback(lambda res: s3.getReference(url2))
        d.addCallback(lambda ref: ref.callRemote('add', a=2, b=2))
        d.addCallback(self._testShared_1)
        return d
    testShared.timeout = 5
    def _testShared_1(self, res):
        t1,t2 = self.targets
        self.failUnlessEqual(t1.calls, [(1,1)])
        self.failUnlessEqual(t2.calls, [(2,2)])

    def testSharedTransfer(self):
        if not crypto:
            raise unittest.SkipTest("crypto not available, shared ports "
                                    "require TubIDs and thus crypto")
        s1,s2,s3 = self.services
        # s1 and s2 will share a Listener
        l1 = s1.listenOn("tcp:0:interface=127.0.0.1")
        s1.setLocation("localhost:%d" % l1.getPortnum())
        s2.listenOn(l1)
        s2.setLocation("localhost:%d" % l1.getPortnum())
        self.failUnless(l1.parentTub is s1)
        s1.stopListeningOn(l1)
        self.failUnless(l1.parentTub is s2)
        s3.listenOn(l1)
        self.failUnless(l1.parentTub is s2)
        d = s2.stopService()
        d.addCallback(self._testSharedTransfer_1, l1, s2, s3)
        return d
    testSharedTransfer.timeout = 5
    def _testSharedTransfer_1(self, res, l1, s2, s3):
        self.services.remove(s2)
        self.failUnless(l1.parentTub is s3)

    def testClone(self):
        if not crypto:
            raise unittest.SkipTest("crypto not available, shared ports "
                                    "require TubIDs and thus crypto")
        s1,s2,s3 = self.services
        l1 = s1.listenOn("tcp:0:interface=127.0.0.1")
        s1.setLocation("localhost:%d" % l1.getPortnum())
        s4 = s1.clone()
        s4.startService()
        self.services.append(s4)
        self.failUnlessEqual(s1.getListeners(), s4.getListeners())
