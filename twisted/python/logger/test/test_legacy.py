# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for L{twisted.python.logger._legacy}.
"""

from time import time
import logging as py_logging

from zope.interface.verify import verifyObject, BrokenMethodImplementation

from twisted.trial import unittest

from twisted.python import context
from twisted.python import log as legacyLog
from twisted.python.failure import Failure

from .._levels import LogLevel
from .._observer import ILogObserver
from .._format import formatEvent
from .._legacy import LegacyLogger
from .._legacy import LegacyLogObserverWrapper
from .._legacy import publishToNewObserver

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
        self.assertIdentical(log.addObserver, legacyLog.addObserver)


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
        # Make sure keys that are expected by the logging system are present
        event.setdefault("log_time", time())
        event.setdefault("log_system", "-")

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


    def test_time(self):
        """
        Translate: C{"log_time"} -> C{"time"}
        """
        event = self.forwardAndVerify({})
        self.assertEqual(event["log_time"], event["time"])


    def test_system(self):
        """
        Translate: C{"log_system"} -> C{"system"}
        """
        event = self.forwardAndVerify(dict(log_system="foo"))
        self.assertEquals(event["system"], "foo")


    def test_systemNone(self):
        """
        If C{"log_system"} is C{None}, C{"system"} is C{"-"}.
        """
        event = self.forwardAndVerify(dict(log_system="foo"))
        self.assertEqual(event["system"], "foo")


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
            legacyLog.textFromEventDict(event),
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



class PublishToNewObserverTests(unittest.TestCase):
    """
    Tests for L{publishToNewObserver}.
    """

    def setUp(self):
        self.events = []
        self.observer = self.events.append


    def legacyEvent(self, *message, **kw):
        """
        Return a basic old-style event as would be created by L{legacyLog.msg}.

        @param message: a message event value in the legacy event format

        @param kw: additional event values in the legacy event format

        @return: a legacy event
        """
        event = (context.get(legacyLog.ILogContext) or {}).copy()
        event.update(kw)
        event["message"] = message
        event["time"] = time()
        return event


    def test_observed(self):
        """
        The observer should get called exactly once.
        """
        publishToNewObserver(self.observer, self.legacyEvent(), lambda e: u"")

        self.assertEquals(len(self.events), 1)


    def test_time(self):
        """
        The C{"time"} key should get copied to C{"log_time"}.
        """
        publishToNewObserver(self.observer, self.legacyEvent(), lambda e: u"")

        self.assertEquals(
            self.events[0]["log_time"], self.events[0]["time"]
        )


    def test_message(self):
        """
        An adapted old-style event should format as text in the same way as the
        given C{textFromEventDict} callable would format it.
        """
        def textFromEventDict(event):
            return "".join(reversed(" ".join(event["message"])))

        event = self.legacyEvent("Hello,", "world!")
        text = textFromEventDict(event)

        publishToNewObserver(self.observer, event, textFromEventDict)

        self.assertEquals(formatEvent(self.events[0]), text)


    def test_defaultLogLevel(self):
        """
        Adapted event should have log level of L{LogLevel.info}.
        """
        publishToNewObserver(self.observer, self.legacyEvent(), lambda e: u"")

        self.assertEquals(self.events[0]["log_level"], LogLevel.info)


    def test_isError(self):
        """
        If C{"isError"} is set to C{1} on the legacy event, the C{"log_level"}
        key should get set to L{LogLevel.critical}.
        """
        publishToNewObserver(
            self.observer, self.legacyEvent(isError=1), lambda e: u""
        )

        self.assertEquals(self.events[0]["log_level"], LogLevel.critical)


    def test_stdlibLogLevel(self):
        """
        If C{"logLevel"} is set to a standard library logging level on the
        legacy event, the C{"log_level"} key should get set to the
        corresponding level.
        """
        publishToNewObserver(
            self.observer,
            self.legacyEvent(logLevel=py_logging.WARNING),
            lambda e: u""
        )

        self.assertEquals(self.events[0]["log_level"], LogLevel.warn)


    def test_defaultNamespace(self):
        """
        Adapted event should have a namespace of C{"log_legacy"}.
        """
        publishToNewObserver(self.observer, self.legacyEvent(), lambda e: u"")

        self.assertEquals(self.events[0]["log_namespace"], "log_legacy")


    def test_system(self):
        """
        The C{"system"} key should get copied to C{"log_system"}.
        """
        publishToNewObserver(self.observer, self.legacyEvent(), lambda e: u"")

        self.assertEquals(
            self.events[0]["log_system"], self.events[0]["system"]
        )
