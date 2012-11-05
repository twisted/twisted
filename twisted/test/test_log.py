# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python.log}.
"""

from __future__ import division, absolute_import, print_function

from twisted.python.compat import _PY3, NativeStringIO as StringIO

import os, sys, time, logging, warnings, calendar


from twisted.trial import unittest

from twisted.python import log, failure


class FakeWarning(Warning):
    """
    A unique L{Warning} subclass used by tests for interactions of
    L{twisted.python.log} with the L{warnings} module.
    """



class LogTest(unittest.SynchronousTestCase):

    def setUp(self):
        self.catcher = []
        self.observer = self.catcher.append
        log.addObserver(self.observer)
        self.addCleanup(log.removeObserver, self.observer)


    def testObservation(self):
        catcher = self.catcher
        log.msg("test", testShouldCatch=True)
        i = catcher.pop()
        self.assertEqual(i["message"][0], "test")
        self.assertEqual(i["testShouldCatch"], True)
        self.assertIn("time", i)
        self.assertEqual(len(catcher), 0)


    def testContext(self):
        catcher = self.catcher
        log.callWithContext({"subsystem": "not the default",
                             "subsubsystem": "a",
                             "other": "c"},
                            log.callWithContext,
                            {"subsubsystem": "b"}, log.msg, "foo", other="d")
        i = catcher.pop()
        self.assertEqual(i['subsubsystem'], 'b')
        self.assertEqual(i['subsystem'], 'not the default')
        self.assertEqual(i['other'], 'd')
        self.assertEqual(i['message'][0], 'foo')

    def testErrors(self):
        for e, ig in [("hello world","hello world"),
                      (KeyError(), KeyError),
                      (failure.Failure(RuntimeError()), RuntimeError)]:
            log.err(e)
            i = self.catcher.pop()
            self.assertEqual(i['isError'], 1)
            self.flushLoggedErrors(ig)

    def testErrorsWithWhy(self):
        for e, ig in [("hello world","hello world"),
                      (KeyError(), KeyError),
                      (failure.Failure(RuntimeError()), RuntimeError)]:
            log.err(e, 'foobar')
            i = self.catcher.pop()
            self.assertEqual(i['isError'], 1)
            self.assertEqual(i['why'], 'foobar')
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
            1 // 0

        for observer in [L1.append, broken, L2.append]:
            log.addObserver(observer)
            self.addCleanup(log.removeObserver, observer)

        for i in range(3):
            # Reset the lists for simpler comparison.
            L1[:] = []
            L2[:] = []

            # Send out the event which will break one of the observers.
            log.msg("Howdy, y'all.")

            # The broken observer should have caused this to be logged.
            excs = self.flushLoggedErrors(ZeroDivisionError)
            del self.catcher[:]
            self.assertEqual(len(excs), 1)

            # Both other observers should have seen the message.
            self.assertEqual(len(L1), 2)
            self.assertEqual(len(L2), 2)

            # The order is slightly wrong here.  The first event should be
            # delivered to all observers; then, errors should be delivered.
            self.assertEqual(L1[1]['message'], ("Howdy, y'all.",))
            self.assertEqual(L2[0]['message'], ("Howdy, y'all.",))


    def test_doubleErrorDoesNotRemoveObserver(self):
        """
        If logging causes an error, make sure that if logging the fact that
        logging failed also causes an error, the log observer is not removed.
        """
        events = []
        errors = []
        publisher = log.LogPublisher()

        class FailingObserver(object):
            calls = 0
            def log(self, msg, **kwargs):
                # First call raises RuntimeError:
                self.calls += 1
                if self.calls < 2:
                    raise RuntimeError("Failure #%s" % (self.calls,))
                else:
                    events.append(msg)

        observer = FailingObserver()
        publisher.addObserver(observer.log)
        self.assertEqual(publisher.observers, [observer.log])

        try:
            # When observer throws, the publisher attempts to log the fact by
            # calling self._err()... which also fails with recursion error:
            oldError = publisher._err

            def failingErr(failure, why, **kwargs):
                errors.append(failure.value)
                raise RuntimeError("Fake recursion error")

            publisher._err = failingErr
            publisher.msg("error in first observer")
        finally:
            publisher._err = oldError
            # Observer should still exist; we do this in finally since before
            # bug was fixed the test would fail due to uncaught exception, so
            # we want failing assert too in that case:
            self.assertEqual(publisher.observers, [observer.log])

        # The next message should succeed:
        publisher.msg("but this should succeed")

        self.assertEqual(observer.calls, 2)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['message'], ("but this should succeed",))
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RuntimeError)


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
        # log.showwarning depends on _oldshowwarning being set, which only
        # happens in startLogging(), which doesn't happen if you're not
        # running under trial. So this test only passes by accident of runner
        # environment.
        if log._oldshowwarning is None:
            raise unittest.SkipTest("Currently this test only runs under trial.")
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


    def test_publisherReportsBrokenObserversPrivately(self):
        """
        Log publisher does not use the global L{log.err} when reporting broken
        observers.
        """
        errors = []
        def logError(eventDict):
            if eventDict.get("isError"):
                errors.append(eventDict["failure"].value)

        def fail(eventDict):
            raise RuntimeError("test_publisherLocalyReportsBrokenObservers")

        publisher = log.LogPublisher()
        publisher.addObserver(logError)
        publisher.addObserver(fail)

        publisher.msg("Hello!")
        self.assertEqual(publisher.observers, [logError, fail])
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RuntimeError)



class FakeFile(list):
    def write(self, bytes):
        self.append(bytes)

    def flush(self):
        pass

class EvilStr:
    def __str__(self):
        1//0

class EvilRepr:
    def __str__(self):
        return "Happy Evil Repr"
    def __repr__(self):
        1//0

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
            if _PY3:
                self._origEncoding = None
                return
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



class LogPublisherTestCase(LogPublisherTestCaseMixin, unittest.SynchronousTestCase):
    def testSingleString(self):
        self.lp.msg("Hello, world.")
        self.assertEqual(len(self.out), 1)


    def testMultipleString(self):
        # Test some stupid behavior that will be deprecated real soon.
        # If you are reading this and trying to learn how the logging
        # system works, *do not use this feature*.
        self.lp.msg("Hello, ", "world.")
        self.assertEqual(len(self.out), 1)


    def test_singleUnicode(self):
        """
        L{log.LogPublisher.msg} does not accept non-ASCII Unicode on Python 2,
        logging an error instead.

        On Python 3, where Unicode is default message type, the message is
        logged normally.
        """
        message = u"Hello, \N{VULGAR FRACTION ONE HALF} world."
        self.lp.msg(message)
        self.assertEqual(len(self.out), 1)
        if _PY3:
            self.assertIn(message, self.out[0])
        else:
            self.assertIn('with str error', self.out[0])
            self.assertIn('UnicodeEncodeError', self.out[0])



class FileObserverTestCase(LogPublisherTestCaseMixin, unittest.SynchronousTestCase):
    """
    Tests for L{log.FileObserver}.
    """

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
        when = calendar.timegm((2001, 2, 3, 4, 5, 6, 7, 8, 0))

        # Pretend to be in US/Eastern for a moment
        self.flo.getTimezoneOffset = lambda when: 18000
        self.assertEqual(self.flo.formatTime(when), '2001-02-02 23:05:06-0500')

        # Okay now we're in Eastern Europe somewhere
        self.flo.getTimezoneOffset = lambda when: -3600
        self.assertEqual(self.flo.formatTime(when), '2001-02-03 05:05:06+0100')

        # And off in the Pacific or someplace like that
        self.flo.getTimezoneOffset = lambda when: -39600
        self.assertEqual(self.flo.formatTime(when), '2001-02-03 15:05:06+1100')

        # One of those weird places with a half-hour offset timezone
        self.flo.getTimezoneOffset = lambda when: 5400
        self.assertEqual(self.flo.formatTime(when), '2001-02-03 02:35:06-0130')

        # Half-hour offset in the other direction
        self.flo.getTimezoneOffset = lambda when: -5400
        self.assertEqual(self.flo.formatTime(when), '2001-02-03 05:35:06+0130')

        # Test an offset which is between 0 and 60 minutes to make sure the
        # sign comes out properly in that case.
        self.flo.getTimezoneOffset = lambda when: 1800
        self.assertEqual(self.flo.formatTime(when), '2001-02-03 03:35:06-0030')

        # Test an offset between 0 and 60 minutes in the other direction.
        self.flo.getTimezoneOffset = lambda when: -1800
        self.assertEqual(self.flo.formatTime(when), '2001-02-03 04:35:06+0030')

        # If a strftime-format string is present on the logger, it should
        # use that instead.  Note we don't assert anything about day, hour
        # or minute because we cannot easily control what time.strftime()
        # thinks the local timezone is.
        self.flo.timeFormat = '%Y %m'
        self.assertEqual(self.flo.formatTime(when), '2001 02')


    def test_loggingAnObjectWithBroken__str__(self):
        #HELLO, MCFLY
        self.lp.msg(EvilStr())
        self.assertEqual(len(self.out), 1)
        # Logging system shouldn't need to crap itself for this trivial case
        self.assertNotIn('UNFORMATTABLE', self.out[0])


    def test_formattingAnObjectWithBroken__str__(self):
        self.lp.msg(format='%(blat)s', blat=EvilStr())
        self.assertEqual(len(self.out), 1)
        self.assertIn('Invalid format string or unformattable object', self.out[0])


    def test_brokenSystem__str__(self):
        self.lp.msg('huh', system=EvilStr())
        self.assertEqual(len(self.out), 1)
        self.assertIn('Invalid format string or unformattable object', self.out[0])


    def test_formattingAnObjectWithBroken__repr__Indirect(self):
        self.lp.msg(format='%(blat)s', blat=[EvilRepr()])
        self.assertEqual(len(self.out), 1)
        self.assertIn('UNFORMATTABLE OBJECT', self.out[0])


    def test_systemWithBroker__repr__Indirect(self):
        self.lp.msg('huh', system=[EvilRepr()])
        self.assertEqual(len(self.out), 1)
        self.assertIn('UNFORMATTABLE OBJECT', self.out[0])


    def test_simpleBrokenFormat(self):
        self.lp.msg(format='hooj %s %s', blat=1)
        self.assertEqual(len(self.out), 1)
        self.assertIn('Invalid format string or unformattable object', self.out[0])


    def test_ridiculousFormat(self):
        self.lp.msg(format=42, blat=1)
        self.assertEqual(len(self.out), 1)
        self.assertIn('Invalid format string or unformattable object', self.out[0])


    def test_evilFormat__repr__And__str__(self):
        self.lp.msg(format=EvilReprStr(), blat=1)
        self.assertEqual(len(self.out), 1)
        self.assertIn('PATHOLOGICAL', self.out[0])


    def test_strangeEventDict(self):
        """
        This kind of eventDict used to fail silently, so test it does.
        """
        self.lp.msg(message='', isError=False)
        self.assertEqual(len(self.out), 0)


    def _startLoggingCleanup(self):
        """
        Cleanup after a startLogging() call that mutates the hell out of some
        global state.
        """
        origShowwarnings = log._oldshowwarning
        self.addCleanup(setattr, log, "_oldshowwarning", origShowwarnings)
        self.addCleanup(setattr, sys, 'stdout', sys.stdout)
        self.addCleanup(setattr, sys, 'stderr', sys.stderr)

    def test_startLogging(self):
        """
        startLogging() installs FileLogObserver and overrides sys.stdout and
        sys.stderr.
        """
        origStdout, origStderr = sys.stdout, sys.stderr
        self._startLoggingCleanup()
        # When done with test, reset stdout and stderr to current values:
        fakeFile = StringIO()
        observer = log.startLogging(fakeFile)
        self.addCleanup(observer.stop)
        log.msg("Hello!")
        self.assertIn("Hello!", fakeFile.getvalue())
        self.assertIsInstance(sys.stdout, log.StdioOnnaStick)
        self.assertEqual(sys.stdout.isError, False)
        encoding = getattr(origStdout, "encoding", None)
        if not encoding:
            encoding = sys.getdefaultencoding()
        self.assertEqual(sys.stdout.encoding, encoding)
        self.assertIsInstance(sys.stderr, log.StdioOnnaStick)
        self.assertEqual(sys.stderr.isError, True)
        encoding = getattr(origStderr, "encoding", None)
        if not encoding:
            encoding = sys.getdefaultencoding()
        self.assertEqual(sys.stderr.encoding, encoding)


    def test_startLoggingTwice(self):
        """
        There are some obscure error conditions that can occur when logging is
        started twice. See http://twistedmatrix.com/trac/ticket/3289 for more
        information.
        """
        self._startLoggingCleanup()
        # The bug is particular to the way that the t.p.log 'global' function
        # handle stdout. If we use our own stream, the error doesn't occur. If
        # we use our own LogPublisher, the error doesn't occur.
        sys.stdout = StringIO()

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


    def test_startLoggingOverridesWarning(self):
        """
        startLogging() overrides global C{warnings.showwarning} such that
        warnings go to Twisted log observers.
        """
        self._startLoggingCleanup()
        # Ugggh, pretend we're starting from newly imported module:
        log._oldshowwarning = None
        fakeFile = StringIO()
        observer = log.startLogging(fakeFile)
        self.addCleanup(observer.stop)
        warnings.warn("hello!")
        output = fakeFile.getvalue()
        self.assertIn("UserWarning: hello!", output)



class PythonLoggingObserverTestCase(unittest.SynchronousTestCase):
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
        self.out.seek(0, 0)
        self.out.truncate()
        self.lp.msg("Foo bar.", logLevel=logging.WARNING)
        self.assertIn("Foo bar.", self.out.getvalue())
        self.assertIn("WARNING", self.out.getvalue())

    def test_strangeEventDict(self):
        """
        Verify that an event dictionary which is not an error and has an empty
        message isn't recorded.
        """
        self.lp.msg(message='', isError=False)
        self.assertEqual(self.out.getvalue(), '')


class PythonLoggingIntegrationTestCase(unittest.SynchronousTestCase):
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
            self.assertEqual(l[0], obs.emit)
            obs.stop()
            self.assertEqual(len(l), 0)
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
            self.assertEqual(len(l), 1)
        finally:
            log.PythonLoggingObserver.emit = oldEmit



class DefaultObserverTestCase(unittest.SynchronousTestCase):
    """
    Test the default observer.
    """

    def test_failureLogger(self):
        """
        The reason argument passed to log.err() appears in the report
        generated by DefaultObserver.
        """
        self.catcher = []
        self.observer = self.catcher.append
        log.addObserver(self.observer)
        self.addCleanup(log.removeObserver, self.observer)

        obs = log.DefaultObserver()
        obs.stderr = StringIO()
        obs.start()
        self.addCleanup(obs.stop)

        reason = "The reason."
        log.err(Exception(), reason)
        errors = self.flushLoggedErrors()

        self.assertIn(reason, obs.stderr.getvalue())
        self.assertEqual(len(errors), 1)



class StdioOnnaStickTestCase(unittest.SynchronousTestCase):
    """
    StdioOnnaStick should act like the normal sys.stdout object.
    """

    def setUp(self):
        self.resultLogs = []
        log.addObserver(self.resultLogs.append)


    def tearDown(self):
        log.removeObserver(self.resultLogs.append)


    def getLogMessages(self):
        return ["".join(d['message']) for d in self.resultLogs]


    def test_write(self):
        """
        Writing to a StdioOnnaStick instance results in Twisted log messages.

        Log messages are generated every time a '\n' is encountered.
        """
        stdio = log.StdioOnnaStick()
        stdio.write("Hello there\nThis is a test")
        self.assertEqual(self.getLogMessages(), ["Hello there"])
        stdio.write("!\n")
        self.assertEqual(self.getLogMessages(), ["Hello there", "This is a test!"])


    def test_metadata(self):
        """
        The log messages written by StdioOnnaStick have printed=1 keyword, and
        by default are not errors.
        """
        stdio = log.StdioOnnaStick()
        stdio.write("hello\n")
        self.assertEqual(self.resultLogs[0]['isError'], False)
        self.assertEqual(self.resultLogs[0]['printed'], True)


    def test_writeLines(self):
        """
        Writing lines to a StdioOnnaStick results in Twisted log messages.
        """
        stdio = log.StdioOnnaStick()
        stdio.writelines(["log 1", "log 2"])
        self.assertEqual(self.getLogMessages(), ["log 1", "log 2"])


    def test_print(self):
        """
        When StdioOnnaStick is set as sys.stdout, prints become log messages.
        """
        oldStdout = sys.stdout
        sys.stdout = log.StdioOnnaStick()
        self.addCleanup(setattr, sys, "stdout", oldStdout)
        print("This", end=" ")
        print("is a test")
        self.assertEqual(self.getLogMessages(), ["This is a test"])


    def test_error(self):
        """
        StdioOnnaStick created with isError=True log messages as errors.
        """
        stdio = log.StdioOnnaStick(isError=True)
        stdio.write("log 1\n")
        self.assertEqual(self.resultLogs[0]['isError'], True)


    def test_unicode(self):
        """
        StdioOnnaStick converts unicode prints to byte strings on Python 2, in
        order to be compatible with the normal stdout/stderr objects.

        On Python 3, the prints are left unmodified.
        """
        unicodeString = u"Hello, \N{VULGAR FRACTION ONE HALF} world."
        stdio = log.StdioOnnaStick(encoding="utf-8")
        self.assertEqual(stdio.encoding, "utf-8")
        stdio.write(unicodeString + u"\n")
        stdio.writelines([u"Also, " + unicodeString])
        oldStdout = sys.stdout
        sys.stdout = stdio
        self.addCleanup(setattr, sys, "stdout", oldStdout)
        # This should go to the log, utf-8 encoded too:
        print(unicodeString)
        if _PY3:
            self.assertEqual(self.getLogMessages(),
                             [unicodeString,
                              u"Also, " + unicodeString,
                              unicodeString])
        else:
            self.assertEqual(self.getLogMessages(),
                             [unicodeString.encode("utf-8"),
                              (u"Also, " + unicodeString).encode("utf-8"),
                              unicodeString.encode("utf-8")])
