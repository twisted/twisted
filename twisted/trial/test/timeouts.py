from twisted.internet import defer
from twisted.internet import reactor
from twisted.trial import unittest

class TimeoutTests(unittest.TestCase):
    timedOut = None
    
    def test_pass(self):
        d = defer.Deferred()
        reactor.callLater(0, d.callback, 'hoorj!')
        return d
    test_pass.timeout = 2

    def test_passDefault(self):
        # test default timeout
        d = defer.Deferred()
        reactor.callLater(0, d.callback, 'hoorj!')
        return d

    def test_timeout(self):
        return defer.Deferred()
    test_timeout.timeout = 0.1

    def test_timeoutZero(self):
        return defer.Deferred()
    test_timeoutZero.timeout = 0

    def test_expectedFailure(self):
        return defer.Deferred()
    test_expectedFailure.timeout = 0.1
    test_expectedFailure.todo = "i will get it right, eventually"
    
    def test_skip(self):
        return defer.Deferred()
    test_skip.timeout = 0.1
    test_skip.skip = "i will get it right, eventually"

    def test_errorPropagation(self):
        def timedOut(err):
            self.__class__.timedOut = err
            return err
        d = defer.Deferred()
        d.addErrback(timedOut)
        return d
    test_errorPropagation.timeout = 0.1
