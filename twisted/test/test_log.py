# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python.log}.
"""

import os, sys, time, logging, warnings
from cStringIO import StringIO

from twisted.trial import unittest

from twisted.python import log, failure


class FakeWarning(Warning):
    """
    A unique L{Warning} subclass used by tests for interactions of
    L{twisted.python.log} with the L{warnings} module.
    """



class LogTest(unittest.TestCase):

    def setUp(self):
        self.catcher = []
        self.observer = self.catcher.append
        log.addObserver(self.observer)
        self.addCleanup(log.removeObserver, self.observer)


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
            self.flushLoggedErrors(ig)

    def testErrorsWithWhy(self):
        for e, ig in [("hello world","hello world"),
                      (KeyError(), KeyError),
                      (failure.Failure(RuntimeError()), RuntimeError)]:
            log.err(e, 'foobar')
            i = self.catcher.pop()
            self.assertEquals(i['isError'], 1)
            self.assertEquals(i['why'], 'foobar')
            self.flushLoggedErrors(ig)


    def test_erroneousErrors(self):
        """
        Exceptions raised by log observers are logged but the observer which
        raised the exception remains registered with the publisher.  These
        exceptions do not prevent the event from being sent to other observers
        registered with the publisher.
        """
        L1 = []
        L2 = []
        def broken(events):
            1 / 0

        for observer in [L1.append, broken, L2.append]:
            log.addObserver(observer)
            self.addCleanup(log.removeObserver, observer)

        for i in xrange(3):
            # Reset the lists for simpler comparison.
            L1[:] = []
            L2[:] = []

            # Send out the event which will break one of the observers.
            log.msg("Howdy, y'all.")

            # The broken observer should have caused this to be logged.  There
            # is a slight bug with LogPublisher - when it logs an error from an
            # observer, it uses the global "err", which is not necessarily
            # associated with it, but which may be associated with a different
            # LogPublisher!  See #3307.
            excs = self.flushLoggedErrors(ZeroDivisionError)
            self.assertEqual(len(excs), 1)

            # Both other observers should have seen the message.
            self.assertEquals(len(L1), 2)
            self.assertEquals(len(L2), 2)

            # The order is slightly wrong here.  The first event should be
            # delivered to all observers; then, errors should be delivered.
            self.assertEquals(L1[1]['message'], ("Howdy, y'all.",))
            self.assertEquals(L2[0]['message'], ("Howdy, y'all.",))


    def test_showwarning(self):
        """
        L{twisted.python.log.showwarning} emits the warning as a message
        to the Twisted logging system.
        """
        publisher = log.LogPublisher()
        publisher.addObserver(self.observer)

        publisher.showwarning(
            FakeWarning("unique warning message"), FakeWarning,
            "warning-filename.py", 27)
        event = self.catcher.pop()
        self.assertEqual(
            event['format'] % event,
            'warning-filename.py:27: twisted.test.test_log.FakeWarning: '
            'unique warning message')
        self.assertEqual(self.catcher, [])

        # Python 2.6 requires that any function used to override the
        # warnings.showwarning API accept a "line" parameter or a
        # deprecation warning is emitted.
        publisher.showwarning(
            FakeWarning("unique warning message"), FakeWarning,
            "warning-filename.py", 27, line=object())
        event = self.catcher.pop()
        self.assertEqual(
            event['format'] % event,
            'warning-filename.py:27: twisted.test.test_log.FakeWarning: '
            'unique warning message')
        self.assertEqual(self.catcher, [])


    def test_warningToFile(self):
        """
        L{twisted.python.log.showwarning} passes warnings with an explicit file
        target on to the underlying Python warning system.
        """
        message = "another unique message"
        category = FakeWarning
        filename = "warning-filename.py"
        lineno = 31

        output = StringIO()
        log.showwarning(message, category, filename, lineno, file=output)

        self.assertEqual(
            output.getvalue(),
            warnings.formatwarning(message, category, filename, lineno))

        # In Python 2.6, warnings.showwarning accepts a "line" argument which
        # gives the source line the warning message is to include.
        if sys.version_info >= (2, 6):
            line = "hello world"
            output = StringIO()
            log.showwarning(message, category, filename, lineno, file=output,
                            line=line)

            self.assertEqual(
                output.getvalue(),
                warnings.formatwarning(message, category, filename, lineno,
                                       line))


class FakeFile(list):
    def write(self, bytes):
        self.append(bytes)

    def flush(self):
        pass

class EvilStr:
    def __str__(self):
        1/0

class EvilRepr:
    def __str__(self):
        return "Happy Evil Repr"
    def __repr__(self):
        1/0

class EvilReprStr(EvilStr, EvilRepr):
    pass

class LogPublisherTestCaseMixin:
    def setUp(self):
        """
        Add a log observer which records log events in C{self.out}.  Also,
        make sure the default string encoding is ASCII so that
        L{testSingleUnicode} can test the behavior of logging unencodable
        unicode messages.
        """
        self.out = FakeFile()
        self.lp = log.LogPublisher()
        self.flo = log.FileLogObserver(self.out)
        self.lp.addObserver(self.flo.emit)

        try:
            str(u'\N{VULGAR FRACTION ONE HALF}')
        except UnicodeEncodeError:
            # This is the behavior we want - don't change anything.
            self._origEncoding = None
        else:
            reload(sys)
            self._origEncoding = sys.getdefaultencoding()
            sys.setdefaultencoding('ascii')


    def tearDown(self):
        """
        Verify that everything written to the fake file C{self.out} was a
        C{str}.  Also, restore the default string encoding to its previous
        setting, if it was modified by L{setUp}.
        """
        for chunk in self.out:
            self.failUnless(isinstance(chunk, str), "%r was not a string" % (chunk,))

        if self._origEncoding is not None:
            sys.setdefaultencoding(self._origEncoding)
            del sys.setdefaultencoding



class LogPublisherTestCase(LogPublisherTestCaseMixin, unittest.TestCase):
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
        self.lp.msg(u"Hello, \N{VULGAR FRACTION ONE HALF} world.")
        self.assertEquals(len(self.out), 1)
        self.assertIn('with str error', self.out[0])
        self.assertIn('UnicodeEncodeError', self.out[0])



class FileObserverTestCase(LogPublisherTestCaseMixin, unittest.TestCase):
    def test_getTimezoneOffset(self):
        """
        Attempt to verify that L{FileLogObserver.getTimezoneOffset} returns
        correct values for the current C{TZ} environment setting.  Do this
        by setting C{TZ} to various well-known values and asserting that the
        reported offset is correct.
        """
        localDaylightTuple = (2006, 6, 30, 0, 0, 0, 4, 181, 1)
        utcDaylightTimestamp = time.mktime(localDaylightTuple)
        localStandardTuple = (2007, 1, 31, 0, 0, 0, 2, 31, 0)
        utcStandardTimestamp = time.mktime(localStandardTuple)

        originalTimezone = os.environ.get('TZ', None)
        try:
            # Test something west of UTC
            os.environ['TZ'] = 'America/New_York'
            time.tzset()
            self.assertEqual(
                self.flo.getTimezoneOffset(utcDaylightTimestamp),
                14400)
            self.assertEqual(
                self.flo.getTimezoneOffset(utcStandardTimestamp),
                18000)

            # Test something east of UTC
            os.environ['TZ'] = 'Europe/Berlin'
            time.tzset()
            self.assertEqual(
                self.flo.getTimezoneOffset(utcDaylightTimestamp),
                -7200)
            self.assertEqual(
                self.flo.getTimezoneOffset(utcStandardTimestamp),
                -3600)

            # Test a timezone that doesn't have DST
            os.environ['TZ'] = 'Africa/Johannesburg'
            time.tzset()
            self.assertEqual(
                self.flo.getTimezoneOffset(utcDaylightTimestamp),
                -7200)
            self.assertEqual(
                self.flo.getTimezoneOffset(utcStandardTimestamp),
                -7200)
        finally:
            if originalTimezone is None:
                del os.environ['TZ']
            else:
                os.environ['TZ'] = originalTimezone
            time.tzset()
    if getattr(time, 'tzset', None) is None:
        test_getTimezoneOffset.skip = (
            "Platform cannot change timezone, cannot verify correct offsets "
            "in well-known timezones.")


    def test_timeFormatting(self):
        """
        Test the method of L{FileLogObserver} which turns a timestamp into a
        human-readable string.
        """
        # There is no function in the time module which converts a UTC time
        # tuple to a timestamp.
        when = time.mktime((2001, 2, 3, 4, 5, 6, 7, 8, 0)) - time.timezone

        # Pretend to be in US/Eastern for a moment
        self.flo.getTimezoneOffset = lambda when: 18000
        self.assertEquals(self.flo.formatTime(when), '2001-02-02 23:05:06-0500')

        # Okay now we're in Eastern Europe somewhere
        self.flo.getTimezoneOffset = lambda when: -3600
        self.assertEquals(self.flo.formatTime(when), '2001-02-03 05:05:06+0100')

        # And off in the Pacific or someplace like that
        self.flo.getTimezoneOffset = lambda when: -39600
        self.assertEquals(self.flo.formatTime(when), '2001-02-03 15:05:06+1100')

        # One of those weird places with a half-hour offset timezone
        self.flo.getTimezoneOffset = lambda when: 5400
        self.assertEquals(self.flo.formatTime(when), '2001-02-03 02:35:06-0130')

        # Half-hour offset in the other direction
        self.flo.getTimezoneOffset = lambda when: -5400
        self.assertEquals(self.flo.formatTime(when), '2001-02-03 05:35:06+0130')

        # Test an offset which is between 0 and 60 minutes to make sure the
        # sign comes out properly in that case.
        self.flo.getTimezoneOffset = lambda when: 1800
        self.assertEquals(self.flo.formatTime(when), '2001-02-03 03:35:06-0030')

        # Test an offset between 0 and 60 minutes in the other direction.
        self.flo.getTimezoneOffset = lambda when: -1800
        self.assertEquals(self.flo.formatTime(when), '2001-02-03 04:35:06+0030')

        # If a strftime-format string is present on the logger, it should
        # use that instead.  Note we don't assert anything about day, hour
        # or minute because we cannot easily control what time.strftime()
        # thinks the local timezone is.
        self.flo.timeFormat = '%Y %m'
        self.assertEquals(self.flo.formatTime(when), '2001 02')


    def test_loggingAnObjectWithBroken__str__(self):
        #HELLO, MCFLY
        self.lp.msg(EvilStr())
        self.assertEquals(len(self.out), 1)
        # Logging system shouldn't need to crap itself for this trivial case
        self.assertNotIn('UNFORMATTABLE', self.out[0])


    def test_formattingAnObjectWithBroken__str__(self):
        self.lp.msg(format='%(blat)s', blat=EvilStr())
        self.assertEquals(len(self.out), 1)
        self.assertIn('Invalid format string or unformattable object', self.out[0])


    def test_brokenSystem__str__(self):
        self.lp.msg('huh', system=EvilStr())
        self.assertEquals(len(self.out), 1)
        self.assertIn('Invalid format string or unformattable object', self.out[0])


    def test_formattingAnObjectWithBroken__repr__Indirect(self):
        self.lp.msg(format='%(blat)s', blat=[EvilRepr()])
        self.assertEquals(len(self.out), 1)
        self.assertIn('UNFORMATTABLE OBJECT', self.out[0])


    def test_systemWithBroker__repr__Indirect(self):
        self.lp.msg('huh', system=[EvilRepr()])
        self.assertEquals(len(self.out), 1)
        self.assertIn('UNFORMATTABLE OBJECT', self.out[0])


    def test_simpleBrokenFormat(self):
        self.lp.msg(format='hooj %s %s', blat=1)
        self.assertEquals(len(self.out), 1)
        self.assertIn('Invalid format string or unformattable object', self.out[0])


    def test_ridiculousFormat(self):
        self.lp.msg(format=42, blat=1)
        self.assertEquals(len(self.out), 1)
        self.assertIn('Invalid format string or unformattable object', self.out[0])


    def test_evilFormat__repr__And__str__(self):
        self.lp.msg(format=EvilReprStr(), blat=1)
        self.assertEquals(len(self.out), 1)
        self.assertIn('PATHOLOGICAL', self.out[0])


    def test_strangeEventDict(self):
        """
        This kind of eventDict used to fail silently, so test it does.
        """
        self.lp.msg(message='', isError=False)
        self.assertEquals(len(self.out), 0)


    def test_startLoggingTwice(self):
        """
        There are some obscure error conditions that can occur when logging is
        started twice. See http://twistedmatrix.com/trac/ticket/3289 for more
        information.
        """
        # The bug is particular to the way that the t.p.log 'global' function
        # handle stdout. If we use our own stream, the error doesn't occur. If
        # we use our own LogPublisher, the error doesn't occur.
        sys.stdout = StringIO()
        self.addCleanup(setattr, sys, 'stdout', sys.__stdout__)

        def showError(eventDict):
            if eventDict['isError']:
                sys.__stdout__.write(eventDict['failure'].getTraceback())

        log.addObserver(showError)
        self.addCleanup(log.removeObserver, showError)
        observer = log.startLogging(sys.stdout)
        self.addCleanup(observer.stop)
        # At this point, we expect that sys.stdout is a StdioOnnaStick object.
        self.assertIsInstance(sys.stdout, log.StdioOnnaStick)
        fakeStdout = sys.stdout
        observer = log.startLogging(sys.stdout)
        self.assertIdentical(sys.stdout, fakeStdout)


class PythonLoggingObserverTestCase(unittest.TestCase):
    """
    Test the bridge with python logging module.
    """
    def setUp(self):
        self.out = StringIO()

        rootLogger = logging.getLogger("")
        self.originalLevel = rootLogger.getEffectiveLevel()
        rootLogger.setLevel(logging.DEBUG)
        self.hdlr = logging.StreamHandler(self.out)
        fmt = logging.Formatter(logging.BASIC_FORMAT)
        self.hdlr.setFormatter(fmt)
        rootLogger.addHandler(self.hdlr)

        self.lp = log.LogPublisher()
        self.obs = log.PythonLoggingObserver()
        self.lp.addObserver(self.obs.emit)

    def tearDown(self):
        rootLogger = logging.getLogger("")
        rootLogger.removeHandler(self.hdlr)
        rootLogger.setLevel(self.originalLevel)
        logging.shutdown()

    def test_singleString(self):
        """
        Test simple output, and default log level.
        """
        self.lp.msg("Hello, world.")
        self.assertIn("Hello, world.", self.out.getvalue())
        self.assertIn("INFO", self.out.getvalue())

    def test_errorString(self):
        """
        Test error output.
        """
        self.lp.msg(failure=failure.Failure(ValueError("That is bad.")), isError=True)
        self.assertIn("ERROR", self.out.getvalue())

    def test_formatString(self):
        """
        Test logging with a format.
        """
        self.lp.msg(format="%(bar)s oo %(foo)s", bar="Hello", foo="world")
        self.assertIn("Hello oo world", self.out.getvalue())

    def test_customLevel(self):
        """
        Test the logLevel keyword for customizing level used.
        """
        self.lp.msg("Spam egg.", logLevel=logging.DEBUG)
        self.assertIn("Spam egg.", self.out.getvalue())
        self.assertIn("DEBUG", self.out.getvalue())
        self.out.reset()
        self.lp.msg("Foo bar.", logLevel=logging.WARNING)
        self.assertIn("Foo bar.", self.out.getvalue())
        self.assertIn("WARNING", self.out.getvalue())

    def test_strangeEventDict(self):
        """
        Verify that an event dictionary which is not an error and has an empty
        message isn't recorded.
        """
        self.lp.msg(message='', isError=False)
        self.assertEquals(self.out.getvalue(), '')


class PythonLoggingIntegrationTestCase(unittest.TestCase):
    """
    Test integration of python logging bridge.
    """
    def test_startStopObserver(self):
        """
        Test that start and stop methods of the observer actually register
        and unregister to the log system.
        """
        oldAddObserver = log.addObserver
        oldRemoveObserver = log.removeObserver
        l = []
        try:
            log.addObserver = l.append
            log.removeObserver = l.remove
            obs = log.PythonLoggingObserver()
            obs.start()
            self.assertEquals(l[0], obs.emit)
            obs.stop()
            self.assertEquals(len(l), 0)
        finally:
            log.addObserver = oldAddObserver
            log.removeObserver = oldRemoveObserver

    def test_inheritance(self):
        """
        Test that we can inherit L{log.PythonLoggingObserver} and use super:
        that's basically a validation that L{log.PythonLoggingObserver} is
        new-style class.
        """
        class MyObserver(log.PythonLoggingObserver):
            def emit(self, eventDict):
                super(MyObserver, self).emit(eventDict)
        obs = MyObserver()
        l = []
        oldEmit = log.PythonLoggingObserver.emit
        try:
            log.PythonLoggingObserver.emit = l.append
            obs.emit('foo')
            self.assertEquals(len(l), 1)
        finally:
            log.PythonLoggingObserver.emit = oldEmit

