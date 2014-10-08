# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for L{twisted.logger._legacy}.
"""

import logging as py_logging

from zope.interface.verify import verifyObject, BrokenMethodImplementation

from twisted.trial import unittest

from twisted.python import log as twistedLogging
from twisted.python.failure import Failure
from twisted.python.log import LogPublisher as OldLogPublisher

from .._levels import LogLevel
from .._observer import ILogObserver
from .._legacy import LegacyLogger
from .._legacy import LegacyLogObserverWrapper
from .._format import formatEvent

from .test_logger import TestLogger



class TestLegacyLogger(LegacyLogger):
    """
    L{LegacyLogger} which uses a L{TestLogger} as its logger.
    """

    def __init__(self, logger=TestLogger()):
        LegacyLogger.__init__(self, logger=logger)



class LegacyLoggerTests(unittest.TestCase):
    """
    Tests for L{LegacyLogger}.
    """

    def test_namespace_default(self):
        """
        Default namespace is module name.
        """
        log = TestLegacyLogger(logger=None)
        self.assertEquals(log.newStyleLogger.namespace, __name__)


    def test_passThroughAttributes(self):
        """
        C{__getattribute__} on L{LegacyLogger} is passing through to Twisted's
        logging module.
        """
        log = TestLegacyLogger()

        # Not passed through
        self.assertIn("API-compatible", log.msg.__doc__)
        self.assertIn("API-compatible", log.err.__doc__)

        # Passed through
        self.assertIdentical(log.addObserver, twistedLogging.addObserver)


    def test_legacy_msg(self):
        """
        Test LegacyLogger's log.msg()
        """
        log = TestLegacyLogger()

        message = "Hi, there."
        kwargs = {"foo": "bar", "obj": object()}

        log.msg(message, **kwargs)

        self.assertIdentical(log.newStyleLogger.emitted["level"],
                             LogLevel.info)
        self.assertEquals(log.newStyleLogger.emitted["format"], message)

        for key, value in kwargs.items():
            self.assertIdentical(log.newStyleLogger.emitted["kwargs"][key],
                                 value)

        log.msg(foo="")

        self.assertIdentical(log.newStyleLogger.emitted["level"],
                             LogLevel.info)
        self.assertIdentical(log.newStyleLogger.emitted["format"], None)


    def test_legacy_err_implicit(self):
        """
        Test LegacyLogger's log.err() capturing the in-flight exception.
        """
        log = TestLegacyLogger()

        exception = RuntimeError("Oh me, oh my.")
        kwargs = {"foo": "bar", "obj": object()}

        try:
            raise exception
        except RuntimeError:
            log.err(**kwargs)

        self.legacy_err(log, kwargs, None, exception)


    def test_legacy_err_exception(self):
        """
        Test LegacyLogger's log.err() with a given exception.
        """
        log = TestLegacyLogger()

        exception = RuntimeError("Oh me, oh my.")
        kwargs = {"foo": "bar", "obj": object()}
        why = "Because I said so."

        try:
            raise exception
        except RuntimeError as e:
            log.err(e, why, **kwargs)

        self.legacy_err(log, kwargs, why, exception)


    def test_legacy_err_failure(self):
        """
        Test LegacyLogger's log.err() with a given L{Failure}.
        """
        log = TestLegacyLogger()

        exception = RuntimeError("Oh me, oh my.")
        kwargs = {"foo": "bar", "obj": object()}
        why = "Because I said so."

        try:
            raise exception
        except RuntimeError:
            log.err(Failure(), why, **kwargs)

        self.legacy_err(log, kwargs, why, exception)


    def test_legacy_err_bogus(self):
        """
        Test LegacyLogger's log.err() with a bogus argument.
        """
        log = TestLegacyLogger()

        exception = RuntimeError("Oh me, oh my.")
        kwargs = {"foo": "bar", "obj": object()}
        why = "Because I said so."
        bogus = object()

        try:
            raise exception
        except RuntimeError:
            log.err(bogus, why, **kwargs)

        errors = self.flushLoggedErrors(exception.__class__)
        self.assertEquals(len(errors), 0)

        self.assertIdentical(
            log.newStyleLogger.emitted["level"],
            LogLevel.critical
        )
        self.assertEquals(log.newStyleLogger.emitted["format"], repr(bogus))
        self.assertIdentical(
            log.newStyleLogger.emitted["kwargs"]["why"],
            why
        )

        for key, value in kwargs.items():
            self.assertIdentical(
                log.newStyleLogger.emitted["kwargs"][key],
                value
            )


    def legacy_err(self, log, kwargs, why, exception):
        """
        Validate the results of calling the legacy C{err} method.

        @param log: the logger that C{err} was called on.
        @type log: L{TestLegacyLogger}

        @param kwargs: keyword arguments given to C{err}.
        @type kwargs: L{dict}

        @param why: C{why} argument given to C{err}.
        @type why: str

        @param exception: the exception caught when C{err} was called.
        @type exception: L{Exception}
        """
        errors = self.flushLoggedErrors(exception.__class__)
        self.assertEquals(len(errors), 1)

        self.assertIdentical(
            log.newStyleLogger.emitted["level"],
            LogLevel.critical
        )

        if why:
            messagePrefix = "{0}\nTraceback (".format(why)
        else:
            messagePrefix = "Unhandled Error\nTraceback ("

        self.assertTrue(
            log.newStyleLogger.emitted["format"].startswith(
                messagePrefix
            )
        )

        emittedKwargs = log.newStyleLogger.emitted["kwargs"]
        self.assertIdentical(emittedKwargs["failure"].__class__, Failure)
        self.assertIdentical(emittedKwargs["failure"].value, exception)
        self.assertIdentical(emittedKwargs["why"], why)

        for key, value in kwargs.items():
            self.assertIdentical(
                log.newStyleLogger.emitted["kwargs"][key],
                value
            )



class LegacyLogObserverWrapperTests(unittest.TestCase):
    """
    Tests for L{LegacyLogObserverWrapper}.
    """

    def test_interface(self):
        """
        L{LegacyLogObserverWrapper} is an L{ILogObserver}.
        """
        legacyObserver = lambda e: None
        observer = LegacyLogObserverWrapper(legacyObserver)
        try:
            verifyObject(ILogObserver, observer)
        except BrokenMethodImplementation as e:
            self.fail(e)


    def test_repr(self):
        """
        L{LegacyLogObserverWrapper} returns the expected string.
        """
        class LegacyObserver(object):
            def __repr__(self):
                return "<Legacy Observer>"

            def __call__(self):
                return

        observer = LegacyLogObserverWrapper(LegacyObserver())

        self.assertEquals(
            repr(observer),
            "LegacyLogObserverWrapper(<Legacy Observer>)"
        )


    def observe(self, event):
        """
        Send an event to a wrapped legacy observer.

        @param event: an event
        @type event: L{dict}

        @return: the event as observed by the legacy wrapper
        """
        events = []

        legacyObserver = lambda e: events.append(e)
        observer = LegacyLogObserverWrapper(legacyObserver)
        observer(event)
        self.assertEquals(len(events), 1)

        return events[0]


    def forwardAndVerify(self, event):
        """
        Send an event to a wrapped legacy observer and verify that its data is
        preserved.

        @param event: an event
        @type event: L{dict}

        @return: the event as observed by the legacy wrapper
        """
        # Send a copy: don't mutate me, bro
        observed = self.observe(dict(event))

        # Don't expect modifications
        for key, value in event.items():
            self.assertIn(key, observed)
            self.assertEquals(observed[key], value)

        return observed


    def test_forward(self):
        """
        Basic forwarding.
        """
        self.forwardAndVerify(dict(foo=1, bar=2))


    def test_system(self):
        """
        Translate: C{"log_system"} -> C{"system"}
        """
        event = self.forwardAndVerify(dict(log_system="foo"))
        self.assertEquals(event["system"], "foo")


    def test_pythonLogLevel(self):
        """
        Python log level is added.
        """
        event = self.forwardAndVerify(dict(log_level=LogLevel.info))
        self.assertEquals(event["logLevel"], py_logging.INFO)


    def test_message(self):
        """
        C{"message"} key is added.
        """
        event = self.forwardAndVerify(dict())
        self.assertEquals(event["message"], ())


    def test_format(self):
        """
        Formatting is translated properly.
        """
        event = self.forwardAndVerify(
            dict(log_format="Hello, {who}!", who="world")
        )
        self.assertEquals(
            twistedLogging.textFromEventDict(event),
            b"Hello, world!"
        )


    def test_failure(self):
        """
        Failures are handled, including setting isError and why.
        """
        failure = Failure(RuntimeError("nyargh!"))
        why = "oopsie..."
        event = self.forwardAndVerify(dict(
            log_failure=failure,
            log_format=why,
        ))
        self.assertIdentical(event["failure"], failure)
        self.assertTrue(event["isError"])
        self.assertEquals(event["why"], why)



class TestOldLogPublisher(unittest.TestCase):
    """
    L{OldLogPublisher} constructs old-style log events and then adds the
    necessary new-style keys.
    """

    def setUp(self):
        """
        Create an L{OldLogPublisher} and a log observer to catch its output.
        """
        self.events = []
        self.old = OldLogPublisher(self.events.append, self.events.append)


    def test_simple(self):
        """
        Messages with a simple message are translated such that the readable
        message remains the same.
        """
        self.old.msg("Hello world.")
        self.assertEquals(len(self.events), 1)
        self.assertEquals(formatEvent(self.events[0]), "Hello world.")
        self.assertEquals(self.events[0]['log_level'], LogLevel.info)


    def test_errorSetsLevel(self):
        """
        Setting the old-style 'isError' key will result in the emitted message
        acquiring the 'isError' key.
        """
        self.old.msg(isError=True)
        self.assertEquals(len(self.events), 1)
        self.assertEquals(self.events[0]['log_level'], LogLevel.critical)


    def test_oldStyleLogLevel(self):
        """
        Setting the old-style 'logLevel' key will result in the emitted message
        acquiring the new-style 'log_level' key.
        """
        self.old.msg(logLevel=py_logging.WARNING)
        self.assertEquals(len(self.events), 1)
        self.assertEquals(self.events[0]['log_level'], LogLevel.warn)
