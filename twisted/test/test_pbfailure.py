# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.trial import unittest

from twisted.spread import pb, flavors
from twisted.internet import reactor, defer
from twisted.python import log, failure

##
# test exceptions
##
class PoopError(Exception):
    pass


class FailError(Exception):
    pass


class DieError(Exception):
    pass


class TimeoutError(Exception):
    pass


#class JellyError(flavors.Jellyable, pb.Error): pass
class JellyError(flavors.Jellyable, pb.Error, pb.RemoteCopy):
    pass


class SecurityError(pb.Error, pb.RemoteCopy):
    pass

pb.setUnjellyableForClass(JellyError, JellyError)
pb.setUnjellyableForClass(SecurityError, SecurityError)
pb.globalSecurity.allowInstancesOf(SecurityError)


####
# server-side
####
class SimpleRoot(pb.Root):
    def remote_poop(self):
        return defer.fail(failure.Failure(PoopError("Someone threw poopie at me!")))

    def remote_fail(self):
        raise FailError("I'm a complete failure! :(")

    def remote_die(self):
        raise DieError("*gack*")

    def remote_jelly(self):
        self.raiseJelly()

    def remote_security(self):
        self.raiseSecurity()

    def remote_deferredJelly(self):
        d = defer.Deferred()
        d.addCallback(self.raiseJelly)
        d.callback(None)
        return d

    def remote_deferredSecurity(self):
        d = defer.Deferred()
        d.addCallback(self.raiseSecurity)
        d.callback(None)
        return d

    def raiseJelly(self, results=None):
        raise JellyError("I'm jellyable!")

    def raiseSecurity(self, results=None):
        raise SecurityError("I'm secure!")


class PBConnTestCase(unittest.TestCase):
    unsafeTracebacks = 0

    def setUp(self):
        self._setUpServer()
        self._setUpClient()

    def _setUpServer(self):
        self.serverFactory = pb.PBServerFactory(SimpleRoot())
        self.serverFactory.unsafeTracebacks = self.unsafeTracebacks
        self.serverPort = reactor.listenTCP(0, self.serverFactory, interface="127.0.0.1")

    def _setUpClient(self):
        portNo = self.serverPort.getHost().port
        self.clientFactory = pb.PBClientFactory()
        self.clientConnector = reactor.connectTCP("127.0.0.1", portNo, self.clientFactory)

    def tearDown(self):
        return defer.gatherResults([
            self._tearDownServer(),
            self._tearDownClient()])

    def _tearDownServer(self):
        return defer.maybeDeferred(self.serverPort.stopListening)

    def _tearDownClient(self):
        self.clientConnector.disconnect()
        return defer.succeed(None)



class PBFailureTest(PBConnTestCase):
    compare = unittest.TestCase.assertEquals


    def _addFailingCallbacks(self, remoteCall, expectedResult, eb):
        remoteCall.addCallbacks(self.success, eb,
                                callbackArgs=(expectedResult,))
        return remoteCall


    def _testImpl(self, method, expected, eb, exc=None):
        rootDeferred = self.clientFactory.getRootObject()
        def gotRootObj(obj):
            failureDeferred = self._addFailingCallbacks(obj.callRemote(method), expected, eb)
            if exc is not None:
                def gotFailure(err):
                    self.assertEquals(len(log.flushErrors(exc)), 1)
                    return err
                failureDeferred.addBoth(gotFailure)
            return failureDeferred
        rootDeferred.addCallback(gotRootObj)
        return rootDeferred


    def testPoopError(self):
        """
        Test that a Deferred returned by a remote method which already has a
        Failure correctly has that error passed back to the calling side.
        """
        return self._testImpl('poop', 42, self.failurePoop, PoopError)


    def testFailureFailure(self):
        """
        Test that a remote method which synchronously raises an exception
        has that exception passed back to the calling side.
        """
        return self._testImpl('fail', 420, self.failureFail, FailError)


    def testDieFailure(self):
        """
        The same as testFailureFailure (it is not clear to me why this
        exists, but I am not deleting it as part of this refactoring.
        -exarkun).
        """
        return self._testImpl('die', 4200, self.failureDie, DieError)


    def testNoSuchFailure(self):
        """
        Test that attempting to call a method which is not defined correctly
        results in an AttributeError on the calling side.
        """
        return self._testImpl('nosuch', 42000, self.failureNoSuch, AttributeError)


    def testJellyFailure(self):
        """
        Test that an exception which is a subclass of L{pb.Error} has more
        information passed across the network to the calling side.
        """
        return self._testImpl('jelly', 43, self.failureJelly)


    def testSecurityFailure(self):
        """
        Test that even if an exception is not explicitly jellyable (by being
        a L{pb.Jellyable} subclass), as long as it is an L{pb.Error}
        subclass it receives the same special treatment.
        """
        return self._testImpl('security', 430, self.failureSecurity)


    def testDeferredJellyFailure(self):
        """
        Test that a Deferred which fails with a L{pb.Error} is treated in
        the same way as a synchronously raised L{pb.Error}.
        """
        return self._testImpl('deferredJelly', 4300, self.failureDeferredJelly, JellyError)


    def testDeferredSecurity(self):
        """
        Test that a Deferred which fails with a L{pb.Error} which is not
        also a L{pb.Jellyable} is treated in the same way as a synchronously
        raised exception of the same type.
        """
        return self._testImpl('deferredSecurity', 43000, self.failureDeferredSecurity, SecurityError)


    def testCopiedFailureLogging(self):
        d = self.clientFactory.getRootObject()

        def connected(rootObj):
            return rootObj.callRemote('die')
        d.addCallback(connected)

        def exception(failure):
            log.err(failure)
            errs = log.flushErrors(DieError)
            self.assertEquals(len(errs), 2)
        d.addErrback(exception)

        return d

    ##
    # callbacks
    ##

    def cleanupLoggedErrors(self, ignored):
        errors = log.flushErrors(PoopError, FailError, DieError,
                                 AttributeError, JellyError, SecurityError)
        self.assertEquals(len(errors), 6)
        return ignored

    def success(self, result, expectedResult):
        self.assertEquals(result, expectedResult)
        return result

    def failurePoop(self, fail):
        fail.trap(PoopError)
        self.compare(fail.traceback, "Traceback unavailable\n")
        return 42

    def failureFail(self, fail):
        fail.trap(FailError)
        self.compare(fail.traceback, "Traceback unavailable\n")
        return 420

    def failureDie(self, fail):
        fail.trap(DieError)
        self.compare(fail.traceback, "Traceback unavailable\n")
        return 4200

    def failureNoSuch(self, fail):
        fail.trap(pb.NoSuchMethod)
        self.compare(fail.traceback, "Traceback unavailable\n")
        return 42000

    def failureJelly(self, fail):
        fail.trap(JellyError)
        self.failIf(isinstance(fail.type, str))
        self.failUnless(isinstance(fail.value, fail.type))
        return 43

    def failureSecurity(self, fail):
        fail.trap(SecurityError)
        self.failIf(isinstance(fail.type, str))
        self.failUnless(isinstance(fail.value, fail.type))
        return 430

    def failureDeferredJelly(self, fail):
        fail.trap(JellyError)
        self.failIf(isinstance(fail.type, str))
        self.failUnless(isinstance(fail.value, fail.type))
        return 4300

    def failureDeferredSecurity(self, fail):
        fail.trap(SecurityError)
        self.failIf(isinstance(fail.type, str))
        self.failUnless(isinstance(fail.value, fail.type))
        return 43000

class PBFailureTestUnsafe(PBFailureTest):

    compare = unittest.TestCase.failIfEquals
    unsafeTracebacks = 1
