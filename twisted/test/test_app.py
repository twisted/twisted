# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Test cases for twisted.internet.app.
"""

from twisted.trial import unittest, util
from twisted.internet import app, protocol, error
from twisted.internet.defer import succeed, fail, SUCCESS, FAILURE
from twisted.python import log
import warnings

class AppTestCase(unittest.TestCase):
    suppress = [util.suppress(message='twisted.internet.app is deprecated',
                              category=DeprecationWarning)]

    def testListenUnlistenTCP(self):
        a = app.Application("foo")
        f = protocol.ServerFactory()
        a.listenTCP(9999, f)
        a.listenTCP(9998, f)
        self.assertEquals(len(a.tcpPorts), 2)
        a.unlistenTCP(9999)
        self.assertEquals(len(a.tcpPorts), 1)
        a.listenTCP(9999, f, interface='127.0.0.1')
        self.assertEquals(len(a.tcpPorts), 2)
        a.unlistenTCP(9999, '127.0.0.1')
        self.assertEquals(len(a.tcpPorts), 1)
        a.unlistenTCP(9998)
        self.assertEquals(len(a.tcpPorts), 0)

    def testListenUnlistenUDP(self):
        a = app.Application("foo")
        f = protocol.DatagramProtocol()
        a.listenUDP(9999, f)
        a.listenUDP(9998, f)
        self.assertEquals(len(a.udpPorts), 2)
        a.unlistenUDP(9999)
        self.assertEquals(len(a.udpPorts), 1)
        a.listenUDP(9999, f, interface='127.0.0.1')
        self.assertEquals(len(a.udpPorts), 2)
        a.unlistenUDP(9999, '127.0.0.1')
        self.assertEquals(len(a.udpPorts), 1)
        a.unlistenUDP(9998)
        self.assertEquals(len(a.udpPorts), 0)

    def testListenUnlistenUNIX(self):
        a = app.Application("foo")
        f = protocol.ServerFactory()
        a.listenUNIX("xxx", f)
        self.assertEquals(len(a.unixPorts), 1)
        a.unlistenUNIX("xxx")
        self.assertEquals(len(a.unixPorts), 0)

    def testIllegalUnlistens(self):
        a = app.Application("foo")

        self.assertRaises(error.NotListeningError, a.unlistenTCP, 1010)
        self.assertRaises(error.NotListeningError, a.unlistenUNIX, '1010')
        self.assertRaises(error.NotListeningError, a.unlistenSSL, 1010)
        self.assertRaises(error.NotListeningError, a.unlistenUDP, 1010)

class ServiceTestCase(unittest.TestCase):

    def testRegisterService(self):
        a = app.Application("foo")
        svc = app.ApplicationService("service", a)
        self.assertEquals(a.getServiceNamed("service"), svc)
        self.assertEquals(a, svc.serviceParent)
    testRegisterService.suppress = [util.suppress(message='twisted.internet.app is deprecated',
                                                  category=DeprecationWarning)]

class StopError(Exception): pass

class StoppingService(app.ApplicationService):

    def __init__(self, name, succeed):
        app.ApplicationService.__init__(self, name)
        self.succeed = succeed

    def stopService(self):
        if self.succeed:
            return succeed("yay!")
        else:
            return fail(StopError('boo'))

class StoppingServiceII(app.ApplicationService):
    def stopService(self):
        # The default stopService returns None.
        return None # return app.ApplicationService.stopService(self)

class MultiServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.callbackRan = 0

    def testDeferredStopService(self):
        ms = app.MultiService("MultiService")
        self.s1 = StoppingService("testService", 0)
        self.s2 = StoppingService("testService2", 1)
        ms.addService(self.s1)
        ms.addService(self.s2)
        ms.stopService().addCallback(self.woohoo)
        log.flushErrors (StopError)

    def woohoo(self, res):
        self.callbackRan = 1
        self.assertEqual(res[self.s1][0], 0)
        self.assertEqual(res[self.s2][0], 1)

    def testStopServiceNone(self):
        """MultiService.stopService returns Deferred when service returns None.
        """
        ms = app.MultiService("MultiService")
        self.s1 = StoppingServiceII("testService")
        ms.addService(self.s1)
        d = ms.stopService()
        d.addCallback(self.cb_nonetest)
        log.flushErrors (StopError)

    def cb_nonetest(self, res):
        self.callbackRan = 1
        self.assertEqual((SUCCESS, None), res[self.s1])

    def testEmptyStopService(self):
        """MutliService.stopService returns Deferred when empty."""
        ms = app.MultiService("MultiService")
        d = ms.stopService()
        d.addCallback(self.cb_emptytest)

    def cb_emptytest(self, res):
        self.callbackRan = 1
        self.assertEqual(len(res), 0)

    def tearDown(self):
        log.flushErrors (StopError)
        self.failUnless(self.callbackRan, "Callback was never run.")
