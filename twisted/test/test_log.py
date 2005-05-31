# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#

import sys

from twisted.trial import unittest

from twisted.python import log
from twisted.python import failure

class LogTest(unittest.TestCase):

    def setUp(self):
        self.catcher = []
        log.addObserver(self.catcher.append)

    def tearDown(self):
        log.removeObserver(self.catcher.append)

    def testObservation(self):
        catcher = self.catcher
        log.msg("test", testShouldCatch=True)
        i = catcher.pop()
        self.assertEquals(i["message"][0], "test")
        self.assertEquals(i["testShouldCatch"], True)
        self.failUnless(i.has_key("time"))
        self.assertEquals(len(catcher), 0)

    def testContext(self):
        catcher = self.catcher
        log.callWithContext({"subsystem": "not the default",
                             "subsubsystem": "a",
                             "other": "c"},
                            log.callWithContext,
                            {"subsubsystem": "b"}, log.msg, "foo", other="d")
        i = catcher.pop()
        self.assertEquals(i['subsubsystem'], 'b')
        self.assertEquals(i['subsystem'], 'not the default')
        self.assertEquals(i['other'], 'd')
        self.assertEquals(i['message'][0], 'foo')

    def testErrors(self):
        for e, ig in [("hello world","hello world"),
                      (KeyError(), KeyError),
                      (failure.Failure(RuntimeError()), RuntimeError)]:
            log.err(e)
            i = self.catcher.pop()
            self.assertEquals(i['isError'], 1)
            log.flushErrors(ig)

    def testErroneousErrors(self):
        L1 = []
        L2 = []
        log.addObserver(lambda events: events['isError'] or L1.append(events))
        log.addObserver(lambda events: 1/0)
        log.addObserver(lambda events: events['isError'] or L2.append(events))
        log.msg("Howdy, y'all.")

        excs = [f.type for f in log.flushErrors(ZeroDivisionError)]
        self.assertEquals([ZeroDivisionError], excs)

        self.assertEquals(len(L1), 2)
        self.assertEquals(len(L2), 2)

        self.assertEquals(L1[1]['message'], ("Howdy, y'all.",))
        self.assertEquals(L2[0]['message'], ("Howdy, y'all.",))

        # The observer has been removed, there should be no exception
        log.msg("Howdy, y'all.")

        self.assertEquals(len(L1), 3)
        self.assertEquals(len(L2), 3)
        self.assertEquals(L1[2]['message'], ("Howdy, y'all.",))
        self.assertEquals(L2[2]['message'], ("Howdy, y'all.",))


class FakeFile(list):
    def write(self, bytes):
        self.append(bytes)

    def flush(self):
        pass


class LogPublisherTestCase(unittest.TestCase):
    def setUpClass(self):
        # Fuck you Python.
        reload(sys)
        self._origEncoding = sys.getdefaultencoding()
        sys.setdefaultencoding('ascii')

    def tearDownClass(self):
        sys.setdefaultencoding(self._origEncoding)
        # Fuck you very much.
        del sys.setdefaultencoding

    def setUp(self):
        self.out = FakeFile()
        self.lp = log.LogPublisher()
        self.flo = log.FileLogObserver(self.out)
        self.lp.addObserver(self.flo.emit)

    def tearDown(self):
        for chunk in self.out:
            self.failUnless(isinstance(chunk, str), "%r was not a string" % (chunk,))

    def testSingleString(self):
        self.lp.msg("Hello, world.")
        self.assertEquals(len(self.out), 1)

    def testMultipleString(self):
        # Test some stupid behavior that will be deprecated real soon.
        # If you are reading this and trying to learn how the logging
        # system works, *do not use this feature*.
        self.lp.msg("Hello, ", "world.")
        self.assertEquals(len(self.out), 1)

    def testSingleUnicode(self):
        self.assertRaises(
            UnicodeError,
            self.lp.msg, u"Hello, \N{VULGAR FRACTION ONE HALF} world.")
        self.assertEquals(len(self.out), 0)
