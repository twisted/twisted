# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.logger.test._assertionhelpers}.
"""

from twisted.trial.unittest import TestCase
from twisted.logger.test._assertionhelpers import (
    assertLogEvent, assertLogEvents, assertGlobalLogEvent,
    capturingLogEventsFromGlobalLogPublisher,
    capturingLogEventsFrom, assertGlobalLogEvents)
from twisted.logger import (
    Logger, LogLevel, _loggerFor, globalLogPublisher)
from twisted.python.reflect import fullyQualifiedName



class ThingThatLogs(object):
    """
    Simple object that logs events.
    """
    _log = Logger()

    def logInfo(self):
        """
        Log event at log level L{LogLevel.info}.
        """
        self._log.info('INFO: {quote} {obj!r}', obj=self,
                       quote='Twisted is amazing!')


    def logFailure(self):
        """
        Log a captured L{Failure}.
        """
        try:
            1/0
        except:
            self._log.failure('Math is hard!')


    def logEventWithNoFormatString(self):
        """
        Log an event at log level L{LogLevel.info} without
        a format string.
        """
        self._log.info(obj=self)


    def logMultipleEvents(self):
        """
        Log multiple events by calling all the log* methods
        defined so far.
        """
        self.logInfo()
        self.logFailure()
        self.logEventWithNoFormatString()


    def logInfoUsingLoggerFor(self):
        """
        Log an event using L{twisted.logger._loggerFor}.
        """
        _loggerFor(self).info('Info: {quote}, {obj!r}', obj=self,
                              quote='Twisted rules!')


    def logEventWithNoFormatStringUsingLoggerFor(self):
        """
        Log an event at log level L{LogLevel.info} without
        a format string using L{twisted.logger._loggerFor}.
        """
        _loggerFor(self).info(obj=self)


    def logMultipleEventsUsingLoggerFor(self):
        """
        Log multiple events using L{twisted.logger._loggerFor}.
        """
        self.logInfoUsingLoggerFor()
        self.logEventWithNoFormatStringUsingLoggerFor()



class GlobalLogPublisherContextManagerTests(TestCase):
    """
    Tests for L{capturingLogEventsFromGlobalLogPublisher}.
    """
    def setUp(self):
        """
        Sets up an intance of an object that emits log events.
        """
        self.thingThatLogs = ThingThatLogs()


    def test_appendIsNotInGlobalObservers(self):
        """
        Test that list.append is removed as an observer from the
        L{globalLogPublisher} after the test finishes.
        """
        appendObserver = None

        with capturingLogEventsFromGlobalLogPublisher() as events:
            self.assertIn(events.append, globalLogPublisher._observers)
            appendObserver = events.append

        self.assertNotIn(appendObserver, globalLogPublisher._observers)



class AssertGlobalLogEventTests(TestCase):
    """
    Tests for L{twisted.logger.test._assertionhelpers.assertGlobalLogEvent}.
    """
    def setUp(self):
        """
        Sets up an instance of an object that emits log events.
        """
        self.thingThatLogs = ThingThatLogs()


    def test_assertInfoLogEvent(self):
        """
        Test a true condition of L{assertGlobalLogEvent} when some
        log event is emitted.
        """
        with capturingLogEventsFromGlobalLogPublisher() as events:
            self.thingThatLogs.logInfoUsingLoggerFor()

            assertGlobalLogEvent(
                self, events[0], LogLevel.info,
                fullyQualifiedName(ThingThatLogs),
                log_source=self.thingThatLogs,
                log_format='Info: {quote}, {obj!r}', obj=self.thingThatLogs,
                quote='Twisted rules!'
            )


    def test_assertLogEventWithNoFormatString(self):
        """
        Test a true condition of L{assertGlobalLogEvent} when an
        emitted event has no format string, C{log_format}.
        """
        with capturingLogEventsFromGlobalLogPublisher() as events:
            self.thingThatLogs.logEventWithNoFormatStringUsingLoggerFor()

            assertGlobalLogEvent(
                self, events[0], LogLevel.info,
                fullyQualifiedName(ThingThatLogs),
                log_source=self.thingThatLogs,
                obj=self.thingThatLogs
            )


    def test_assertLogEventWithNoSource(self):
        """
        Test a true condition of L{assertGlobalLogEvent} when an emitted
        event has no source object (C{log_source} is L{None}, i.e. the
        L{Logger} that the event was emitted to cannot be accessed
        as an attribute of an instance or class).
        """
        log = Logger()

        with capturingLogEventsFromGlobalLogPublisher() as events:
            log.info(home='Twisted Matrix Labs')

            assertGlobalLogEvent(
                self, events[0], LogLevel.info,
                __name__, home='Twisted Matrix Labs'
            )


    def test_assertGlobalLogEventError(self):
        """
        Test an error with L{assertGlobalLogEvent}.
        """
        with capturingLogEventsFromGlobalLogPublisher() as events:
            self.thingThatLogs.logInfoUsingLoggerFor()

            self.assertRaises(
                self.failureException, assertGlobalLogEvent, self,
                events[0], LogLevel.warn,
                fullyQualifiedName(ThingThatLogs),
                log_source=self.thingThatLogs,
                universalTruth='TWISTED PREVAILS!'
            )



class AssertGlobalLogEventsTests(TestCase):
    """
    Tests for L{twisted.logger.test._assertionhelpers.assertGlobalLogEvents}.
    """
    def setUp(self):
        """
        Sets up an instance of an object that emits log events.
        """
        self.thingThatLogs = ThingThatLogs()


    def test_assertMultipleLogEvents(self):
        """
        Test a true condition of L{assertLogEvents} when multiple
        events are logged.
        """
        log = Logger()

        with capturingLogEventsFromGlobalLogPublisher() as events:
            self.thingThatLogs.logMultipleEventsUsingLoggerFor()
            log.info(home='Twisted Matrix Labs')

            assertGlobalLogEvents(self, events, [
                {
                    'log_level': LogLevel.info,
                    'log_namespace': fullyQualifiedName(ThingThatLogs),
                    'log_source': self.thingThatLogs,
                    'log_format': 'Info: {quote}, {obj!r}',
                    'obj': self.thingThatLogs,
                    'quote': 'Twisted rules!'
                },
                {
                    'log_level': LogLevel.info,
                    'log_namespace': fullyQualifiedName(ThingThatLogs),
                    'log_source': self.thingThatLogs,
                    'obj': self.thingThatLogs
                },
                {
                    'log_level': LogLevel.info,
                    'log_namespace': __name__,
                    'home': 'Twisted Matrix Labs'
                }
            ])


    def test_lenOfActualEventsIsNotEqualToLenOfExpectedEvents(self):
        """
        Test an error of L{assertGlobalLogEvents} when the length of
        C{actualEvents} is not equal to the length of L{expectedEvents}.
        """
        with capturingLogEventsFromGlobalLogPublisher() as events:
            self.thingThatLogs.logMultipleEventsUsingLoggerFor()

            self.assertRaises(
                self.failureException, assertGlobalLogEvents, self, events,
                [
                    {
                        'log_level': LogLevel.info,
                        'log_namespace': fullyQualifiedName(ThingThatLogs),
                        'log_source': self.thingThatLogs,
                        'log_format': 'Info: {quote}, {obj!r}',
                        'obj': self.thingThatLogs,
                        'quote': 'Twisted rules!'
                    }
                ]
            )


    def test_expectedEventsAreNotActualEvents(self):
        """
        Test an error of L{assertGlobalLogEvents} when the expected
        events are not the actual events that have been logged.
        """
        with capturingLogEventsFromGlobalLogPublisher() as events:
            self.thingThatLogs.logInfoUsingLoggerFor()

            self.assertRaises(
                self.failureException, assertGlobalLogEvents, self, events,
                [
                    {
                        'log_level': LogLevel.warn,
                        'log_namespace': 'some.random.Object',
                        'log_source': self.thingThatLogs,
                        'log_format': 'Twisted rocks!',
                        'truth': 'Twisted rules!'
                    }
                ]
            )



class AssertLogEventTests(TestCase):
    """
    Tests for L{twisted.logger.test._assertionhelpers.assertLogEvents}.
    """
    def setUp(self):
        """
        Sets up an instance of an object that emits log events.
        """
        self.thingThatLogs = ThingThatLogs()


    def test_assertInfoLogEvent(self):
        """
        Test a true condition of L{assertLogEvent} when some log event
        is emitted.
        """
        with capturingLogEventsFrom(self.thingThatLogs._log) as events:
            self.thingThatLogs.logInfo()

            assertLogEvent(
                self, events[0], self.thingThatLogs._log, LogLevel.info,
                fullyQualifiedName(ThingThatLogs),
                log_source=self.thingThatLogs,
                log_format='INFO: {quote} {obj!r}', obj=self.thingThatLogs,
                quote='Twisted is amazing!'
            )


    def test_assertFailureLogEvent(self):
        """
        Test a true condition of L{assertLogEvent} when a failure is
        logged using L{Logger.failure}.
        """
        with capturingLogEventsFrom(self.thingThatLogs._log) as events:
            self.thingThatLogs.logFailure()

            assertLogEvent(
                self, events[0], self.thingThatLogs._log,
                LogLevel.critical, fullyQualifiedName(ThingThatLogs),
                log_source=self.thingThatLogs,
                log_format='Math is hard!'
            )


    def test_assertLogEventWithNoFormatString(self):
        """
        Test a true condition of L{assertLogEvent} when an emitted
        event has no format string, C{log_format}.
        """
        with capturingLogEventsFrom(self.thingThatLogs._log) as events:
            self.thingThatLogs.logEventWithNoFormatString()

            assertLogEvent(
                self, events[0], self.thingThatLogs._log, LogLevel.info,
                fullyQualifiedName(ThingThatLogs),
                log_source=self.thingThatLogs,
                obj=self.thingThatLogs
            )


    def test_assertLogEventWithNoSource(self):
        """
        Test a true condition of L{assertLogEvent} when an emitted
        event has no source object (C{log_source} is L{None}, i.e. the
        L{Logger} that the event was emitted to cannot be accessed
        as an attribute of an instance or class).
        """
        log = Logger()

        with capturingLogEventsFrom(log) as events:
            log.info(home='Twisted Matrix Labs')

            assertLogEvent(self, events[0], log, LogLevel.info, __name__,
                           home='Twisted Matrix Labs')


    def test_assertLogEventError(self):
        """
        Test an error with L{assertLogEvent}.
        """
        log = Logger()

        with capturingLogEventsFrom(log) as events:
            log.info('Twisted rocks!')

            self.assertRaises(
                self.failureException, assertLogEvent, self, events[0],
                log, LogLevel.warn, fullyQualifiedName(ThingThatLogs),
                log_source=self.thingThatLogs,
                universalTruth='TWISTED PREVAILS!'
            )



class AssertLogEventsTests(TestCase):
    """
    Tests for L{twisted.logger.test._assertionhelpers.assertLogEvents}.
    """
    def setUp(self):
        """
        Sets up an instance of an object that emits log events.
        """
        self.thingThatLogs = ThingThatLogs()


    def test_assertMultipleLogEvents(self):
        """
        Test a true condition of L{assertLogEvents} when multiple
        events are logged.
        """
        with capturingLogEventsFrom(self.thingThatLogs._log) as events:
            self.thingThatLogs.logMultipleEvents()

            assertLogEvents(self, events, [
                {
                    'log_logger': self.thingThatLogs._log,
                    'log_level': LogLevel.info,
                    'log_namespace': fullyQualifiedName(ThingThatLogs),
                    'log_source': self.thingThatLogs,
                    'obj': self.thingThatLogs,
                    'log_format': 'INFO: {quote} {obj!r}',
                    'quote': 'Twisted is amazing!'
                },
                {
                    'log_logger': self.thingThatLogs._log,
                    'log_level': LogLevel.critical,
                    'log_namespace': fullyQualifiedName(ThingThatLogs),
                    'log_source': self.thingThatLogs,
                    'log_format': 'Math is hard!'
                },
                {
                    'log_logger': self.thingThatLogs._log,
                    'log_level': LogLevel.info,
                    'log_namespace': fullyQualifiedName(ThingThatLogs),
                    'log_source': self.thingThatLogs,
                    'obj': self.thingThatLogs
                },

            ])


    def test_lenOfActualEventsIsNotEqualToLenOfExpectedEvents(self):
        """
        Test an error of L{assertLogEvents} when the length of
        C{actualEvents} is not equal to the length of L{expectedEvents}.
        """
        with capturingLogEventsFrom(self.thingThatLogs._log) as events:
            self.thingThatLogs.logMultipleEvents()

            self.assertRaises(
                self.failureException, assertLogEvents, self, events,
                [
                    {
                        'log_logger': self.thingThatLogs._log,
                        'log_level': LogLevel.info,
                        'log_namespace': fullyQualifiedName(ThingThatLogs),
                        'log_source': self.thingThatLogs,
                        'obj': self.thingThatLogs
                    }
                ]
            )


    def test_expectedEventsAreNotActualEvents(self):
        """
        Test an error of L{assertLogEvents} when the expected events
        are not the actual events that have been logged.
        """
        log = Logger()

        with capturingLogEventsFrom(log) as events:

            log.info('Twisted rocks!')

            self.assertRaises(
                self.failureException, assertLogEvents, self, events,
                [
                    {
                        'log_logger': log, 'log_level': LogLevel.warn,
                        'log_namespace': fullyQualifiedName(ThingThatLogs),
                        'log_source': self.thingThatLogs,
                        'universalTruth': 'TWISTED PREVAILS!'
                    }
                ]
            )
